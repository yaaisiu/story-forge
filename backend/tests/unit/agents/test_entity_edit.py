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
)
from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.entity_edits import EntityEditInvalid, EntityEditPatch
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


class FakeEvidence:
    """An in-memory `EditEvidenceRepo` recording each row in `events` and keeping the rows."""

    def __init__(self, events: list[tuple[str, object]]) -> None:
        self.rows: list[object] = []
        self._events = events

    async def record_edit(self, edit: object) -> None:
        self.rows.append(edit)
        self._events.append(("record_edit", getattr(edit, "op", None)))


def _service() -> tuple[EntityEditService, FakeGraph, FakeEvidence, list[tuple[str, object]]]:
    events: list[tuple[str, object]] = []
    graph = FakeGraph(events)
    evidence = FakeEvidence(events)
    return EntityEditService(graph, evidence), graph, evidence, events


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
    service, graph, evidence, events = _service()
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
    service, graph, evidence, events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek

    await service.edit_entity(PROJECT, janek.id, EntityEditPatch())

    assert events == []
    assert evidence.rows == []


async def test_edit_entity_invalid_patch_writes_nothing() -> None:
    service, graph, _evidence, events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek

    with pytest.raises(EntityEditInvalid):
        await service.edit_entity(PROJECT, janek.id, EntityEditPatch(type="  "))
    assert events == []  # rejected before any write


async def test_edit_entity_missing_or_cross_project_is_not_found() -> None:
    service, graph, _evidence, _events = _service()
    with pytest.raises(EntityNotFound):
        await service.edit_entity(PROJECT, uuid4(), EntityEditPatch(type="Deity"))

    foreign = _entity(project_id=OTHER_PROJECT)
    graph.entities[foreign.id] = foreign
    with pytest.raises(EntityNotFound):
        await service.edit_entity(PROJECT, foreign.id, EntityEditPatch(type="Deity"))


async def test_add_relation_writes_edge_then_evidence_and_flags_no_collision() -> None:
    service, graph, evidence, events = _service()
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
    }


async def test_add_relation_duplicate_flags_collision() -> None:
    service, graph, _evidence, _events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria

    await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)
    second = await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)

    assert second.merged_into_existing is True


async def test_add_relation_allows_self_loop() -> None:
    service, graph, _evidence, _events = _service()
    sole = _entity()
    graph.entities[sole.id] = sole

    result = await service.add_relation(PROJECT, sole.id, "TALKS_TO_SELF", sole.id)

    assert result.edge_id in graph.relations


async def test_add_relation_missing_endpoint_is_not_found() -> None:
    service, graph, _evidence, _events = _service()
    janek = _entity()
    graph.entities[janek.id] = janek
    with pytest.raises(EntityNotFound):
        await service.add_relation(PROJECT, janek.id, "LOVES", uuid4())


async def test_remove_relation_records_before_image_then_deletes() -> None:
    service, graph, evidence, events = _service()
    janek = _entity()
    maria = _entity(canonical_name_pl="Maria")
    graph.entities[janek.id] = janek
    graph.entities[maria.id] = maria
    add = await service.add_relation(PROJECT, janek.id, "LOVES", maria.id)
    events.clear()

    await service.remove_relation(PROJECT, add.edge_id)

    assert add.edge_id not in graph.relations
    assert events == [("delete_relation", add.edge_id), ("record_edit", "remove_relation")]
    assert evidence.rows[-1].before == {  # type: ignore[attr-defined]
        "subject_id": str(janek.id),
        "predicate": "LOVES",
        "object_id": str(maria.id),
    }


async def test_remove_relation_missing_edge_is_not_found() -> None:
    service, _graph, _evidence, _events = _service()
    with pytest.raises(RelationEdgeNotFound):
        await service.remove_relation(PROJECT, uuid4())
