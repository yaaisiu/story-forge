"""Unit tests for `EntityEditService` (`agents/entity_edit.py`) with faked collaborators.

No DB, no network: a fake graph + a fake evidence log record their writes in a shared event log,
so the tests pin the **contract** — the TOCTOU/tenancy guard, the validated field merge, the
write *order* (graph mutation before evidence, INV-3/DM-S3a-2), the no-op skip, the manual
self-loop, and the duplicate-add collision flag (DM-S3a-3) — not a real Neo4j/Postgres.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from story_forge.agents.entity_edit import (
    EntityEditService,
    EntityNotFound,
    MentionNotFound,
    RelationEdgeNotFound,
    SelfMergeError,
)
from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.entity_edits import EntityEditInvalid, EntityEditPatch
from story_forge.domain.entity_merge import EntityMergeInvalid
from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.graph_undo import RecreateRelation, invert_operation
from story_forge.domain.models import EntityMention, MentionSuppression

PROJECT = uuid4()
OTHER_PROJECT = uuid4()


class FakeGraph:
    """An in-memory `EntityGraphEditor` recording the order of writes in `events`."""

    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.entities: dict[UUID, GraphEntity] = {}
        self.relations: dict[UUID, GraphRelation] = {}
        self._events = events

    async def get_entity(self, entity_id: UUID) -> GraphEntity | None:
        return self.entities.get(entity_id)

    async def create_entity(self, entity: GraphEntity) -> None:
        self.entities.setdefault(entity.id, entity)  # MERGE ... ON CREATE: no clobber
        self._events.append(("create_entity", entity.id))

    async def update_entity(self, entity: GraphEntity) -> None:
        self.entities[entity.id] = entity
        self._events.append(("update_entity", entity.id))

    async def get_relation(self, project_id: UUID, edge_id: UUID) -> GraphRelation | None:
        relation = self.relations.get(edge_id)
        if relation is None:
            return None
        subject = self.entities.get(relation.subject_id)
        object_ = self.entities.get(relation.object_id)
        if subject is None or object_ is None:
            return None
        if subject.project_id != project_id or object_.project_id != project_id:
            return None
        return relation

    async def create_relation(self, relation: GraphRelation) -> None:
        # MERGE ... ON CREATE SET: an edge already at this id is not clobbered (the coalesce that
        # keeps a fold survivor's own `edge_uid` — DM-S5-3), mirroring `create_entity` above.
        self.relations.setdefault(relation.id, relation)
        self._events.append(("create_relation", relation.id))

    async def delete_relation(self, edge_id: UUID) -> None:
        self.relations.pop(edge_id, None)
        self._events.append(("delete_relation", edge_id))

    async def get_neighbourhood(self, entity_id: UUID) -> list[tuple[GraphRelation, GraphEntity]]:
        pairs: list[tuple[GraphRelation, GraphEntity]] = []
        for relation in self.relations.values():
            far_id = relation.object_id if relation.subject_id == entity_id else relation.subject_id
            if entity_id in (relation.subject_id, relation.object_id) and far_id in self.entities:
                pairs.append((relation, self.entities[far_id]))
        return pairs

    async def delete_entity(self, entity_id: UUID) -> None:
        self.entities.pop(entity_id, None)
        self.relations = {
            eid: r
            for eid, r in self.relations.items()
            if entity_id not in (r.subject_id, r.object_id)
        }
        self._events.append(("delete_entity", entity_id))


class FakeEvidence:
    """An in-memory `EditEvidenceRepo` recording each row in `events` and keeping the rows."""

    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.rows: list[object] = []
        self.operations: list[list[object]] = []
        self._events = events

    async def record_edit(self, edit: object) -> None:
        self.rows.append(edit)
        self._events.append(("record_edit", getattr(edit, "op", None)))

    async def record_operation(self, edits: object) -> None:
        rows = list(edits)  # type: ignore[call-overload]
        self.operations.append(rows)
        self._events.append(("record_operation", len(rows)))

    async def latest_live_operation(self, project_id: UUID) -> list[object] | None:
        return None

    async def mark_operation_undone(self, op_key: UUID, *, undone_at: object) -> None:
        self._events.append(("mark_operation_undone", op_key))

    async def is_operation_undone(self, operation_id: UUID) -> bool:
        return False  # no prior undone op in these unit tests → merge stays at generation 0


class FakeMentions:
    """An in-memory `MentionRepo`: holds `entity_id → [mention_id]` and re-points on merge, plus
    the M4.S3c manual-correction state (`mentions` by id, `suppressions` by id) so the tag/un-tag/
    boundary ops and their undo round-trips can be asserted against real stored state."""

    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.by_entity: dict[UUID, list[UUID]] = {}
        self.mentions: dict[UUID, EntityMention] = {}
        self.suppressions: dict[UUID, MentionSuppression] = {}
        self._events = events

    async def repoint_mentions(self, from_entity_id: UUID, to_entity_id: UUID) -> list[UUID]:
        moved = self.by_entity.pop(from_entity_id, [])
        self.by_entity.setdefault(to_entity_id, []).extend(moved)
        self._events.append(("repoint_mentions", len(moved)))
        return moved

    async def reassign_mentions(self, mention_ids: list[UUID], to_entity_id: UUID) -> None:
        self.by_entity.setdefault(to_entity_id, []).extend(mention_ids)

    async def mentions_for_entity(self, entity_id: UUID) -> list[object]:
        return []

    async def delete_mentions_for_entity(self, entity_id: UUID) -> None:
        self.by_entity.pop(entity_id, None)

    async def restore_mentions(self, mentions: list[object]) -> None:
        self._events.append(("restore_mentions", len(mentions)))

    # M4.S3c manual-correction mutators (id-keyed; insert is ON CONFLICT DO NOTHING idempotent):
    async def add_mention(self, mention: EntityMention) -> None:
        self.mentions.setdefault(mention.id, mention)
        self._events.append(("add_mention", mention.id))

    async def get_mention(self, mention_id: UUID) -> EntityMention | None:
        return self.mentions.get(mention_id)

    async def update_mention_span(self, mention_id: UUID, span_start: int, span_end: int) -> None:
        current = self.mentions[mention_id]
        self.mentions[mention_id] = current.model_copy(
            update={"span_start": span_start, "span_end": span_end}
        )
        self._events.append(("update_mention_span", mention_id))

    async def delete_mention(self, mention_id: UUID) -> None:
        self.mentions.pop(mention_id, None)
        self._events.append(("delete_mention", mention_id))

    async def add_suppression(self, suppression: MentionSuppression) -> None:
        self.suppressions.setdefault(suppression.id, suppression)
        self._events.append(("add_suppression", suppression.id))

    async def delete_suppression(self, suppression_id: UUID) -> None:
        self.suppressions.pop(suppression_id, None)
        self._events.append(("delete_suppression", suppression_id))


def _service() -> tuple[
    EntityEditService, FakeGraph, FakeEvidence, FakeMentions, list[tuple[str, object]]
]:
    events: list[tuple[str, object]] = []
    graph = FakeGraph(events)
    evidence = FakeEvidence(events)
    mentions = FakeMentions(events)
    return EntityEditService(graph, evidence, mentions), graph, evidence, mentions, events


def _entity(project_id: UUID = PROJECT, **overrides: object) -> GraphEntity:
    base: dict[str, object] = {
        "type": "Character",
        "canonical_name_pl": "Janek",
        "aliases": [],
        "properties": {"age": 23},
        "project_id": project_id,
    }
    base.update(overrides)
    return GraphEntity(**base)  # type: ignore[arg-type]


async def test_edit_entity_writes_graph_then_evidence_with_field_diff() -> None:
    service, graph, evidence, _mentions, events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek

    result = await service.edit_entity(PROJECT, janek.id, EntityEditPatch(type="Deity"))

    assert result.type == "Deity"
    assert graph.entities[janek.id].type == "Deity"
    # graph mutation precedes the evidence row (INV-3/DM-S3a-2 ordering)
    assert events == [("update_entity", janek.id), ("record_edit", "edit_fields")]
    row = evidence.rows[0]
    assert row.before == {"type": "Character"}  # type: ignore[attr-defined]
    assert row.after == {"type": "Deity"}  # type: ignore[attr-defined]


async def test_edit_entity_noop_writes_nothing() -> None:
    service, graph, evidence, _mentions, events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek

    await service.edit_entity(PROJECT, janek.id, EntityEditPatch())

    assert events == []
    assert evidence.rows == []


async def test_edit_entity_invalid_patch_writes_nothing() -> None:
    service, graph, _evidence, _mentions, events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek

    with pytest.raises(EntityEditInvalid):
        await service.edit_entity(PROJECT, janek.id, EntityEditPatch(type="  "))
    assert events == []  # rejected before any write


async def test_edit_entity_missing_or_cross_project_is_not_found() -> None:
    service, graph, _evidence, _mentions, _events = _service()
    with pytest.raises(EntityNotFound):
        await service.edit_entity(PROJECT, uuid4(), EntityEditPatch(type="Deity"))

    foreign = _entity(project_id=OTHER_PROJECT)
    graph.entities[foreign.id] = foreign
    with pytest.raises(EntityNotFound):
        await service.edit_entity(PROJECT, foreign.id, EntityEditPatch(type="Deity"))


async def test_add_relation_writes_edge_then_evidence_and_flags_no_collision() -> None:
    service, graph, evidence, _mentions, events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria

    result = await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)

    assert result.edge_id == relation_edge_id(janek.id, "LOVES", maria.id)
    assert result.merged_into_existing is False
    assert events == [("create_relation", result.edge_id), ("record_edit", "add_relation")]
    assert evidence.rows[0].after == {  # type: ignore[attr-defined]
        "subject_id": str(janek.id),
        "predicate": "LOVES",
        "object_id": str(maria.id),
        "merged_into_existing": False,  # the add created a new edge (so undo deletes it)
    }


async def test_add_relation_duplicate_flags_collision() -> None:
    service, graph, _evidence, _mentions, _events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria

    await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)
    second = await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)

    assert second.merged_into_existing is True


async def test_add_relation_allows_self_loop() -> None:
    service, graph, _evidence, _mentions, _events = _service()
    sole = _entity()
    graph.entities[sole.id] = sole

    result = await service.add_relation(PROJECT, sole.id, "TALKS_TO_SELF", sole.id)

    assert result.edge_id in graph.relations


async def test_add_relation_missing_endpoint_is_not_found() -> None:
    service, graph, _evidence, _mentions, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek
    with pytest.raises(EntityNotFound):
        await service.add_relation(PROJECT, janek.id, "LOVES", uuid4())


async def test_remove_relation_records_before_image_then_deletes() -> None:
    service, graph, evidence, _mentions, events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria
    add = await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)
    events.clear()

    await service.remove_relation(PROJECT, add.edge_id)

    assert add.edge_id not in graph.relations
    assert events == [("delete_relation", add.edge_id), ("record_edit", "remove_relation")]
    # the before-image is the full edge snapshot (so undo restores its exact confidence/properties)
    before = evidence.rows[-1].before  # type: ignore[attr-defined]
    assert before["id"] == str(add.edge_id)
    assert before["type"] == "LOVES"
    assert before["subject_id"] == str(janek.id)
    assert before["object_id"] == str(maria.id)
    assert before["confidence"] == 1.0


async def test_remove_relation_missing_edge_is_not_found() -> None:
    service, _graph, _evidence, _mentions, _events = _service()
    with pytest.raises(RelationEdgeNotFound):
        await service.remove_relation(PROJECT, uuid4())


# --- retarget: atomic edit-predicate / re-target (Graph-quality S5b-be) -----


async def test_retarget_repredicates_atomically_and_preserves_the_handle() -> None:
    service, graph, evidence, _mentions, events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria
    add = await service.add_relation(PROJECT, janek.id, "PASSENGER_ON", maria.id)
    handle = graph.relations[add.edge_id].edge_uid  # minted forward on add
    events.clear()

    result = await service.retarget_relation(PROJECT, add.edge_id, predicate="ON_SHIP")

    # the content id re-keyed, the old edge is gone, the new one carries the SAME handle (INV-10)
    new_id = relation_edge_id(janek.id, "ON_SHIP", maria.id)
    assert result.edge_id == new_id
    assert result.merged_into_existing is False
    assert add.edge_id not in graph.relations
    assert graph.relations[new_id].type == "ON_SHIP"
    assert graph.relations[new_id].edge_uid == handle
    # graph-first, evidence-last (INV-3): delete old → create new → record the grouped op
    assert events == [
        ("delete_relation", add.edge_id),
        ("create_relation", new_id),
        ("record_operation", 1),
    ]
    (rows,) = evidence.operations
    (row,) = rows
    assert row.op_kind == "retarget" and row.op == "repoint_relation"  # type: ignore[attr-defined]
    assert row.before["edge_uid"] == str(handle)  # type: ignore[attr-defined]


async def test_retarget_re_targets_an_endpoint() -> None:
    service, graph, _evidence, _mentions, _events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    zofia = _entity(canonical_name_pl="Zofia")
    for e in (janek, maria, zofia):
        graph.entities[e.id] = e
    add = await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)

    result = await service.retarget_relation(PROJECT, add.edge_id, object_id=zofia.id)

    assert result.edge_id == relation_edge_id(janek.id, "LOVES", zofia.id)
    assert graph.relations[result.edge_id].object_id == zofia.id
    assert add.edge_id not in graph.relations


async def test_retarget_folds_onto_an_existing_edge_and_survivor_keeps_its_handle() -> None:
    service, graph, evidence, _mentions, events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria
    doomed = await service.add_relation(PROJECT, janek.id, "PASSENGER_ON", maria.id)
    survivor = await service.add_relation(PROJECT, janek.id, "ON_SHIP", maria.id)
    survivor_handle = graph.relations[survivor.edge_id].edge_uid
    events.clear()

    # re-predicate the doomed edge onto the survivor's triple → MERGE-collision → fold
    result = await service.retarget_relation(PROJECT, doomed.edge_id, predicate="ON_SHIP")

    assert result.edge_id == survivor.edge_id
    assert result.merged_into_existing is True
    assert doomed.edge_id not in graph.relations
    # the survivor edge is untouched and keeps its OWN handle (ON-CREATE coalesce, DM-S5-3)
    assert graph.relations[survivor.edge_id].edge_uid == survivor_handle
    (rows,) = evidence.operations
    assert rows[0].op == "fold_relation"  # type: ignore[attr-defined]


async def test_retarget_noop_when_nothing_changes_writes_nothing() -> None:
    service, graph, evidence, _mentions, events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria
    add = await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)
    events.clear()

    result = await service.retarget_relation(PROJECT, add.edge_id, predicate="LOVES")

    assert result.edge_id == add.edge_id
    assert result.merged_into_existing is False
    assert events == []  # idempotent no-op: nothing mutated, no evidence
    assert evidence.operations == []


async def test_retarget_missing_edge_is_not_found() -> None:
    service, _graph, _evidence, _mentions, _events = _service()
    with pytest.raises(RelationEdgeNotFound):
        await service.retarget_relation(PROJECT, uuid4(), predicate="LOVES")


async def test_retarget_onto_a_missing_endpoint_is_not_found() -> None:
    service, graph, _evidence, _mentions, _events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria
    add = await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)
    with pytest.raises(EntityNotFound):
        await service.retarget_relation(PROJECT, add.edge_id, object_id=uuid4())


async def test_undo_retarget_restores_the_old_predicate_and_handle() -> None:
    service, graph, evidence, _mentions, _events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria
    add = await service.add_relation(PROJECT, janek.id, "PASSENGER_ON", maria.id)
    handle = graph.relations[add.edge_id].edge_uid
    new = await service.retarget_relation(PROJECT, add.edge_id, predicate="ON_SHIP")

    await _undo(service, evidence.operations[-1])

    # the new edge is removed and the old one restored — predicate AND handle (INV-3 + INV-10)
    assert new.edge_id not in graph.relations
    restored = graph.relations[add.edge_id]
    assert restored.type == "PASSENGER_ON"
    assert restored.edge_uid == handle


async def test_undo_retarget_fold_restores_the_folded_edge_and_leaves_the_survivor() -> None:
    service, graph, evidence, _mentions, _events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria
    doomed = await service.add_relation(PROJECT, janek.id, "PASSENGER_ON", maria.id)
    survivor = await service.add_relation(PROJECT, janek.id, "ON_SHIP", maria.id)
    await service.retarget_relation(PROJECT, doomed.edge_id, predicate="ON_SHIP")

    await _undo(service, evidence.operations[-1])

    # un-fold recreates the folded edge; the survivor (never created here) is untouched
    assert doomed.edge_id in graph.relations
    assert survivor.edge_id in graph.relations


async def test_every_op_a_retarget_records_is_invertible() -> None:
    # Writer↔inverter contract driven from the REAL rows a re-key emits (the PR-#108 discipline):
    # a repoint and a fold each reuse the merge writer's op strings, so `invert_operation` must
    # reverse them without UndoNotInvertible. Guards the S3b `discard_self_loop` 500 class of bug.
    service, graph, evidence, _mentions, _events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria
    a = await service.add_relation(PROJECT, janek.id, "PASSENGER_ON", maria.id)
    await service.add_relation(PROJECT, janek.id, "ON_SHIP", maria.id)  # fold target
    await service.retarget_relation(PROJECT, a.edge_id, predicate="ON_SHIP")  # fold_relation
    b = await service.add_relation(PROJECT, janek.id, "KNOWS", maria.id)
    await service.retarget_relation(PROJECT, b.edge_id, predicate="ADORES")  # repoint_relation

    for rows in evidence.operations:
        invert_operation(rows)  # type: ignore[arg-type]  # must not raise UndoNotInvertible


# --- merge (M4.S3b) --------------------------------------------------------


async def test_merge_consolidates_repoints_deletes_and_records_grouped_evidence() -> None:
    service, graph, evidence, mentions, events = _service()
    survivor = _entity(canonical_name_pl="Bronisław", aliases=["Bronek"], properties={"age": 40})
    absorbed = _entity(canonical_name_pl="Broniek", aliases=[], properties={"town": "Lwów"})
    bystander = _entity(canonical_name_pl="Maria")
    for e in (survivor, absorbed, bystander):
        graph.entities[e.id] = e
    # B has one incident edge (B → Maria) that must re-point onto A.
    edge = await service.add_relation(PROJECT, absorbed.id, "LOVES", bystander.id)
    mentions.by_entity[absorbed.id] = [uuid4(), uuid4()]
    events.clear()

    summary = await service.merge_entities(PROJECT, absorbed.id, survivor.id, {})

    # consolidation landed on A
    merged = graph.entities[survivor.id]
    assert "Broniek" in merged.aliases  # B's canonical name folded in as an alias
    assert merged.properties == {"age": 40, "town": "Lwów"}  # non-conflicting union
    # B is gone, its edge re-pointed onto A
    assert absorbed.id not in graph.entities
    new_edge_id = relation_edge_id(survivor.id, "LOVES", bystander.id)
    assert new_edge_id in graph.relations
    assert edge.edge_id not in graph.relations
    # mentions moved from B onto A
    assert absorbed.id not in mentions.by_entity
    assert len(mentions.by_entity[survivor.id]) == 2
    assert summary == type(summary)(
        survivor_entity_id=survivor.id,
        repointed_count=1,
        folded_count=0,
        self_loops_dropped=0,
        mentions_repointed=2,
    )
    # write order: fold A + edge swap → move mentions → delete B LAST → evidence
    assert events == [
        ("update_entity", survivor.id),
        ("delete_relation", edge.edge_id),
        ("create_relation", new_edge_id),
        ("repoint_mentions", 2),
        ("delete_entity", absorbed.id),
        ("record_operation", 4),  # consolidate + 1 edge + mention re-point + delete-absorbed
    ]
    # the grouped rows share one operation_id and carry the human-readable description
    (op_rows,) = evidence.operations
    assert len({r.operation_id for r in op_rows}) == 1
    assert all(r.op_kind == "merge" for r in op_rows)
    assert {r.description for r in op_rows} == {"merged Broniek into Bronisław"}
    assert [r.seq for r in op_rows] == [0, 1, 2, 3]


async def test_merge_dedupes_a_self_loop_returned_twice_by_the_neighbourhood() -> None:
    # A real Neo4j undirected neighbourhood query returns a self-loop *twice* (one per
    # orientation); the service must dedupe by edge id so it isn't double-counted / double-logged.
    service, graph, evidence, _mentions, _events = _service()
    survivor = _entity(canonical_name_pl="Bronisław")
    absorbed = _entity(canonical_name_pl="Broniek")
    graph.entities[survivor.id] = survivor
    graph.entities[absorbed.id] = absorbed
    loop = GraphRelation(
        id=relation_edge_id(absorbed.id, "MUTTERS", absorbed.id),
        type="MUTTERS",
        subject_id=absorbed.id,
        object_id=absorbed.id,
        confidence=1.0,
    )
    graph.relations[loop.id] = loop

    # Force the both-orientation double-return the real adapter produces for a self-loop.
    async def _twice(entity_id: UUID) -> list[tuple[GraphRelation, GraphEntity]]:
        if entity_id == absorbed.id:
            return [(loop, absorbed), (loop, absorbed)]
        return []

    graph.get_neighbourhood = _twice  # type: ignore[method-assign]

    summary = await service.merge_entities(PROJECT, absorbed.id, survivor.id, {})

    assert summary.self_loops_dropped == 1  # not 2 — the duplicate was deduped
    (op_rows,) = evidence.operations
    # consolidate + ONE edge row + mention re-point + delete-absorbed (no duplicate edge row)
    assert [r.op for r in op_rows] == [
        "merge_consolidate",
        "discard_self_loop_relation",
        "repoint_mentions",
        "delete_absorbed",
    ]


async def test_every_op_a_self_loop_merge_records_is_invertible() -> None:
    # Writer↔inverter contract: drive `invert_operation` from the REAL rows a merge emits, not a
    # hand-built fixture. A self-loop-dropping merge records a `discard_self_loop_relation` row; the
    # inverter must handle every op the writer produces (no UndoNotInvertible) and recreate the
    # dropped loop. This is the regression for the merge-undo 500 that a fictional fixture masked.
    service, graph, evidence, _mentions, _events = _service()
    survivor = _entity(canonical_name_pl="Bronisław")
    absorbed = _entity(canonical_name_pl="Broniek")
    graph.entities[survivor.id] = survivor
    graph.entities[absorbed.id] = absorbed
    loop = GraphRelation(
        id=relation_edge_id(absorbed.id, "MUTTERS", absorbed.id),
        type="MUTTERS",
        subject_id=absorbed.id,
        object_id=absorbed.id,
        confidence=1.0,
    )
    graph.relations[loop.id] = loop

    async def _twice(entity_id: UUID) -> list[tuple[GraphRelation, GraphEntity]]:
        return [(loop, absorbed), (loop, absorbed)] if entity_id == absorbed.id else []

    graph.get_neighbourhood = _twice  # type: ignore[method-assign]

    await service.merge_entities(PROJECT, absorbed.id, survivor.id, {})
    (op_rows,) = evidence.operations

    plan = invert_operation(op_rows)  # must not raise UndoNotInvertible

    assert RecreateRelation(relation=loop) in plan.actions


async def test_merge_self_is_rejected_before_any_write() -> None:
    service, graph, _evidence, _mentions, events = _service()
    sole = _entity()
    graph.entities[sole.id] = sole
    with pytest.raises(SelfMergeError):
        await service.merge_entities(PROJECT, sole.id, sole.id, {})
    assert events == []


async def test_merge_unresolved_property_conflict_is_rejected() -> None:
    service, graph, _evidence, _mentions, events = _service()
    survivor = _entity(properties={"age": 40})
    absorbed = _entity(canonical_name_pl="Broniek", properties={"age": 41})
    graph.entities[survivor.id] = survivor
    graph.entities[absorbed.id] = absorbed
    with pytest.raises(EntityMergeInvalid):
        await service.merge_entities(PROJECT, absorbed.id, survivor.id, {})
    # plan_merge raises before the Neo4j writes — nothing mutated
    assert ("update_entity", survivor.id) not in events
    assert ("delete_entity", absorbed.id) not in events


async def test_merge_missing_or_cross_project_endpoint_is_not_found() -> None:
    service, graph, _evidence, _mentions, _events = _service()
    survivor = _entity()
    graph.entities[survivor.id] = survivor
    # absorbed missing
    with pytest.raises(EntityNotFound):
        await service.merge_entities(PROJECT, uuid4(), survivor.id, {})
    # target in another project
    foreign = _entity(project_id=OTHER_PROJECT)
    graph.entities[foreign.id] = foreign
    with pytest.raises(EntityNotFound):
        await service.merge_entities(PROJECT, survivor.id, foreign.id, {})


# ── M4.S3c: manual tag / un-tag / change-boundaries (the reader write path) ─────────────────

PARAGRAPH = uuid4()


async def _undo(service: EntityEditService, rows: list[object]) -> None:
    """Drive `invert_operation` from the writer's *real* recorded rows and apply each inverse
    (the PR-#108 producer↔consumer discipline — never a hand-built op-row). Skips the drift read
    (covered by the S3b drift tests); the focus here is invertibility + the apply wiring."""
    plan = invert_operation(rows)  # type: ignore[arg-type]
    for action in plan.actions:
        await service._apply_inverse(action)


# --- Step 6: each op records the right evidence + mutates the store in the right order ---


async def test_tag_existing_inserts_mention_then_records_add_mention() -> None:
    service, graph, evidence, mentions, events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek

    mention_id = await service.tag_existing(PROJECT, PARAGRAPH, janek.id, 0, 5)

    # store mutation precedes the evidence row (INV-3/DM-S3a-2 order)
    assert events == [("add_mention", mention_id), ("record_edit", "add_mention")]
    stored = mentions.mentions[mention_id]
    assert stored.source == "manual" and (stored.span_start, stored.span_end) == (0, 5)
    assert stored.entity_id == janek.id


async def test_tag_existing_is_idempotent_by_deterministic_id() -> None:
    service, graph, _evidence, mentions, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek
    first = await service.tag_existing(PROJECT, PARAGRAPH, janek.id, 0, 5)
    second = await service.tag_existing(PROJECT, PARAGRAPH, janek.id, 0, 5)
    assert first == second  # same span → same id
    assert len(mentions.mentions) == 1


async def test_tag_existing_unknown_entity_is_not_found() -> None:
    service, _graph, _evidence, _mentions, events = _service()
    with pytest.raises(EntityNotFound):
        await service.tag_existing(PROJECT, PARAGRAPH, uuid4(), 0, 5)
    assert events == []  # rejected before any write


async def test_tag_new_entity_creates_node_then_mention_grouped() -> None:
    service, graph, evidence, mentions, events = _service()

    entity_id, mention_id = await service.tag_new_entity(
        PROJECT, PARAGRAPH, "Smaug", "Dragon", "en", 0, 5
    )

    # Neo4j-then-Postgres (OQ-1), evidence last as one grouped op.
    assert events == [
        ("create_entity", entity_id),
        ("add_mention", mention_id),
        ("record_operation", 2),
    ]
    created = graph.entities[entity_id]
    assert created.type == "Dragon" and created.canonical_name_en == "Smaug"
    assert created.canonical_name_pl is None and created.embedding is None  # PoC: no embedding
    rows = evidence.operations[-1]
    ops = [r.op for r in rows]  # type: ignore[attr-defined]
    assert ops == ["create_entity_from_tag", "add_mention"]
    assert all(r.op_kind == "tag_new" for r in rows)  # type: ignore[attr-defined]


async def test_tag_new_entity_fills_pl_slot_for_polish_project() -> None:
    service, graph, _evidence, _mentions, _events = _service()
    entity_id, _ = await service.tag_new_entity(PROJECT, PARAGRAPH, "Smok", "Smok-typ", "pl", 0, 4)
    created = graph.entities[entity_id]
    assert created.canonical_name_pl == "Smok" and created.canonical_name_en is None


async def test_tag_new_entity_blank_name_or_type_rejected() -> None:
    service, _graph, _evidence, _mentions, events = _service()
    with pytest.raises(EntityEditInvalid):
        await service.tag_new_entity(PROJECT, PARAGRAPH, "   ", "Dragon", "en", 0, 5)
    with pytest.raises(EntityEditInvalid):
        await service.tag_new_entity(PROJECT, PARAGRAPH, "Smaug", "  ", "en", 0, 5)
    assert events == []


async def test_suppress_occurrence_not_an_entity_keys_all_entities() -> None:
    service, _graph, evidence, mentions, _events = _service()
    suppression_id = await service.suppress_occurrence(PROJECT, PARAGRAPH, 0, 5, None)
    supp = mentions.suppressions[suppression_id]
    assert supp.entity_id is None and (supp.span_start, supp.span_end) == (0, 5)
    assert evidence.rows[-1].op == "suppress_span"  # type: ignore[attr-defined]
    assert evidence.rows[-1].after["entity_id"] is None  # type: ignore[attr-defined,index]


async def test_suppress_occurrence_not_this_entity_keys_one() -> None:
    service, graph, _evidence, mentions, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek
    suppression_id = await service.suppress_occurrence(PROJECT, PARAGRAPH, 0, 5, janek.id)
    assert mentions.suppressions[suppression_id].entity_id == janek.id


async def test_retag_occurrence_groups_suppress_then_add_mention() -> None:
    service, graph, evidence, mentions, _events = _service()
    wrong = _entity(canonical_name_pl="Janek")
    right = _entity(canonical_name_pl="Maria")
    graph.entities[wrong.id] = wrong
    graph.entities[right.id] = right

    suppression_id, mention_id = await service.retag_occurrence(
        PROJECT, PARAGRAPH, 0, 5, wrong.id, right.id
    )

    rows = evidence.operations[-1]
    assert [r.op for r in rows] == ["suppress_span", "add_mention"]  # type: ignore[attr-defined]
    assert all(r.op_kind == "retag" for r in rows)  # type: ignore[attr-defined]
    assert mentions.suppressions[suppression_id].entity_id == wrong.id  # from-entity hidden
    assert mentions.mentions[mention_id].entity_id == right.id  # to-entity tagged


async def test_change_boundaries_in_place_edits_a_manual_span() -> None:
    service, graph, evidence, mentions, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek
    mention_id = await service.tag_existing(PROJECT, PARAGRAPH, janek.id, 0, 5)

    returned = await service.change_boundaries(
        PROJECT, PARAGRAPH, janek.id, mention_id, 0, 5, 0, 10
    )

    assert returned == mention_id  # edit-in-place keeps identity
    assert (mentions.mentions[mention_id].span_start, mentions.mentions[mention_id].span_end) == (
        0,
        10,
    )
    row = evidence.rows[-1]
    assert row.op == "edit_mention_span"  # type: ignore[attr-defined]
    assert row.before == {"span_start": 0, "span_end": 5}  # type: ignore[attr-defined]
    assert row.after == {"span_start": 0, "span_end": 10}  # type: ignore[attr-defined]


async def test_change_boundaries_materializes_an_auto_hit() -> None:
    service, graph, evidence, mentions, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek

    new_mention_id = await service.change_boundaries(
        PROJECT, PARAGRAPH, janek.id, None, 0, 5, 0, 10
    )

    # a stored manual span at the new offsets + a suppression at the original position, grouped
    rows = evidence.operations[-1]
    assert [r.op for r in rows] == ["add_mention", "suppress_span"]  # type: ignore[attr-defined]
    assert all(r.op_kind == "materialize_boundary" for r in rows)  # type: ignore[attr-defined]
    assert mentions.mentions[new_mention_id].span_start == 0
    assert mentions.mentions[new_mention_id].span_end == 10
    assert any(s.span_start == 0 and s.span_end == 5 for s in mentions.suppressions.values())


async def test_change_boundaries_missing_manual_mention_is_not_found() -> None:
    service, graph, _evidence, _mentions, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek
    with pytest.raises(MentionNotFound):
        await service.change_boundaries(PROJECT, PARAGRAPH, janek.id, uuid4(), 0, 5, 0, 10)


# --- Step 7: undo round-trips, driven from the writer's REAL recorded rows (PR #108) ---


async def test_undo_tag_existing_removes_the_mention() -> None:
    service, graph, evidence, mentions, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek
    mention_id = await service.tag_existing(PROJECT, PARAGRAPH, janek.id, 0, 5)

    await _undo(service, [evidence.rows[-1]])
    assert mention_id not in mentions.mentions


async def test_undo_tag_new_entity_deletes_both_node_and_mention() -> None:
    service, graph, evidence, mentions, _events = _service()
    entity_id, mention_id = await service.tag_new_entity(
        PROJECT, PARAGRAPH, "Smaug", "Dragon", "en", 0, 5
    )

    await _undo(service, evidence.operations[-1])
    assert entity_id not in graph.entities  # node gone
    assert mention_id not in mentions.mentions  # mention gone — one atomic op


async def test_undo_suppress_occurrence_unhides() -> None:
    service, _graph, evidence, mentions, _events = _service()
    suppression_id = await service.suppress_occurrence(PROJECT, PARAGRAPH, 0, 5, None)

    await _undo(service, [evidence.rows[-1]])
    assert suppression_id not in mentions.suppressions


async def test_undo_atomic_retag_restores_original_in_one_step() -> None:
    service, graph, evidence, mentions, _events = _service()
    wrong = _entity(canonical_name_pl="Janek")
    right = _entity(canonical_name_pl="Maria")
    graph.entities[wrong.id] = wrong
    graph.entities[right.id] = right
    suppression_id, mention_id = await service.retag_occurrence(
        PROJECT, PARAGRAPH, 0, 5, wrong.id, right.id
    )

    await _undo(service, evidence.operations[-1])
    # both halves reversed → the original `wrong` search hit reconciles back, `right` tag gone
    assert suppression_id not in mentions.suppressions
    assert mention_id not in mentions.mentions


async def test_undo_materialize_boundary_removes_manual_and_unhides_original() -> None:
    service, graph, evidence, mentions, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek
    new_mention_id = await service.change_boundaries(
        PROJECT, PARAGRAPH, janek.id, None, 0, 5, 0, 10
    )

    await _undo(service, evidence.operations[-1])
    assert new_mention_id not in mentions.mentions  # the materialized span gone
    assert mentions.suppressions == {}  # original position un-hidden → auto hit returns


async def test_undo_edit_in_place_boundary_restores_old_offsets() -> None:
    service, graph, evidence, mentions, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek
    mention_id = await service.tag_existing(PROJECT, PARAGRAPH, janek.id, 0, 5)
    await service.change_boundaries(PROJECT, PARAGRAPH, janek.id, mention_id, 0, 5, 0, 10)

    await _undo(service, [evidence.rows[-1]])  # undo the boundary edit
    restored = mentions.mentions[mention_id]
    assert (restored.span_start, restored.span_end) == (0, 5)


async def test_every_manual_op_a_writer_records_is_invertible() -> None:
    # Enumerate the four S3c op-kinds from their REAL recorded rows; none may raise
    # UndoNotInvertible (the contract test that fails if a writer/inverter pair drifts).
    service, graph, evidence, _mentions, _events = _service()
    a = _entity(canonical_name_pl="Janek")
    b = _entity(canonical_name_pl="Maria")
    graph.entities[a.id] = a
    graph.entities[b.id] = b

    await service.tag_existing(PROJECT, PARAGRAPH, a.id, 0, 5)  # add_mention (singleton)
    await service.suppress_occurrence(PROJECT, PARAGRAPH, 6, 9, None)  # suppress_span (singleton)
    await service.tag_new_entity(PROJECT, PARAGRAPH, "Smaug", "Dragon", "en", 10, 15)  # grouped
    await service.retag_occurrence(PROJECT, PARAGRAPH, 16, 20, a.id, b.id)  # grouped
    await service.change_boundaries(PROJECT, PARAGRAPH, a.id, None, 21, 25, 21, 30)  # grouped

    singletons = [[r] for r in evidence.rows]
    for rows in singletons + evidence.operations:
        invert_operation(rows)  # type: ignore[arg-type]  # must not raise UndoNotInvertible
