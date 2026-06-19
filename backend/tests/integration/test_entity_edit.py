"""Integration: the entity-&-relation edit path against real Neo4j + the throwaway Postgres.

`EntityEditService` mutates committed graph state (real `Neo4jRepo`) and records the before→after
evidence (real `PostgresEditStore` on the test DB). These tests pin that the node/edge change
*lands in Neo4j* and that a `graph_edits` row lands *per change* (DM-S3a-2, INV-3). `graph_edits`
has no FK (`target_id` is a soft Neo4j ref), so no project/story tree is needed; the Neo4j side is
scoped to a fresh `project_id` and DETACH-DELETEd on teardown, and the test DB is dropped at session
end.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from dataclasses import dataclass
from uuid import UUID, uuid4

import psycopg
import pytest
import pytest_asyncio
from psycopg.rows import dict_row

from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.adapters.postgres_edit_store import PostgresEditStore
from story_forge.agents.entity_edit import EntityEditService, RelationEdgeNotFound
from story_forge.config import settings
from story_forge.domain.entity_edits import EntityEditPatch
from story_forge.domain.graph import GraphEntity

pytestmark = pytest.mark.integration


@dataclass
class _Live:
    graph: Neo4jRepo
    service: EntityEditService
    project_id: UUID
    conninfo: dict[str, object]


@pytest_asyncio.fixture
async def live(_migrated_test_db: None) -> AsyncIterator[_Live]:
    conninfo = libpq_kwargs(settings.test_database_url)
    graph = await Neo4jRepo.connect(
        uri=settings.neo4j_uri, user=settings.neo4j_user, password=settings.neo4j_password
    )
    project_id = uuid4()
    service = EntityEditService(graph, PostgresEditStore(conninfo))
    try:
        yield _Live(graph, service, project_id, conninfo)
    finally:
        await graph.delete_project_graph(project_id)
        await graph.close()


async def _edits_for(live: _Live, target_id: UUID) -> list[dict[str, object]]:
    async with await psycopg.AsyncConnection.connect(autocommit=True, **live.conninfo) as conn:  # type: ignore[arg-type]
        cur = conn.cursor(row_factory=dict_row)
        await cur.execute(
            "SELECT target_kind, op, before, after FROM graph_edits "
            "WHERE target_id = %s ORDER BY created_at",
            (target_id,),
        )
        return await cur.fetchall()


async def test_edit_entity_updates_node_and_logs_evidence(live: _Live) -> None:
    entity = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        properties={"age": 23},
        project_id=live.project_id,
    )
    await live.graph.create_entity(entity)

    await live.service.edit_entity(
        live.project_id,
        entity.id,
        EntityEditPatch(type="Deity", properties={"role": "priestess"}),
    )

    updated = await live.graph.get_entity(entity.id)
    assert updated is not None
    assert updated.type == "Deity"
    assert updated.properties == {"role": "priestess"}

    edits = await _edits_for(live, entity.id)
    assert len(edits) == 1
    assert edits[0]["target_kind"] == "entity"
    assert edits[0]["op"] == "edit_fields"
    assert edits[0]["before"] == {"type": "Character", "properties": {"age": 23}}
    assert edits[0]["after"] == {"type": "Deity", "properties": {"role": "priestess"}}


async def test_add_then_remove_relation_logs_each_change(live: _Live) -> None:
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=live.project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=live.project_id)
    await live.graph.create_entity(janek)
    await live.graph.create_entity(maria)

    add = await live.service.add_relation(live.project_id, janek.id, "LOVES", maria.id)
    assert add.merged_into_existing is False
    assert [r.id for r in await live.graph.get_relations(live.project_id)] == [add.edge_id]
    add_rows = await _edits_for(live, add.edge_id)
    assert [r["op"] for r in add_rows] == ["add_relation"]
    assert add_rows[0]["target_kind"] == "relation"

    await live.service.remove_relation(live.project_id, add.edge_id)
    assert await live.graph.get_relations(live.project_id) == []
    ops = [r["op"] for r in await _edits_for(live, add.edge_id)]
    assert ops == ["add_relation", "remove_relation"]


async def test_remove_unknown_edge_is_not_found(live: _Live) -> None:
    with pytest.raises(RelationEdgeNotFound):
        await live.service.remove_relation(live.project_id, uuid4())
