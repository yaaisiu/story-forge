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
    RelationEdgeNotFound,
    SelfMergeError,
)
from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.entity_edits import EntityEditInvalid, EntityEditPatch
from story_forge.domain.entity_merge import EntityMergeInvalid
from story_forge.domain.graph import GraphEntity, GraphRelation

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
        self.relations[relation.id] = relation
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
    """An in-memory `MentionRepo`: holds `entity_id → [mention_id]` and re-points on merge."""

    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.by_entity: dict[UUID, list[UUID]] = {}
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
