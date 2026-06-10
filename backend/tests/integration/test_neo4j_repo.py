"""Neo4j graph-write repository against the real compose neo4j service (spec §6.4, §9 M2).

M2.S4 writes every extracted candidate as a *fresh* node — no dedupe, no merge
(INV-8): two identical entities must produce two distinct nodes, exposing the
duplicate problem M3's cascade then solves. These tests pin that contract plus a
plain round-trip of entities and relations.

Isolation: Neo4j Community has no throwaway-database equivalent of the Postgres
fixture, so each test scopes its writes to a unique `project_id` (uuid4) and the
fixture DETACH-DELETEs exactly those nodes on teardown — dev/other data is never
touched (property-based multi-tenancy, §6.4). A failed test leaves only its own
project's nodes behind, removed on the next run's teardown of that id (none, since
ids are fresh) — so cleanup never races other tests.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from uuid import UUID, uuid4

import pytest
import pytest_asyncio

from story_forge.adapters.neo4j_repo import Neo4jRepo
from story_forge.config import settings
from story_forge.domain.graph import GraphEntity, GraphRelation

pytestmark = pytest.mark.integration


@pytest_asyncio.fixture
async def graph() -> AsyncIterator[tuple[Neo4jRepo, UUID]]:
    """A connected repo + a unique `project_id`; teardown deletes that project's graph."""
    repo = await Neo4jRepo.connect(
        uri=settings.neo4j_uri,
        user=settings.neo4j_user,
        password=settings.neo4j_password,
    )
    project_id = uuid4()
    try:
        yield repo, project_id
    finally:
        await repo.delete_project_graph(project_id)
        await repo.close()


async def test_entity_round_trip(graph: tuple[Neo4jRepo, UUID]) -> None:
    repo, project_id = graph
    entity = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        canonical_name_en=None,
        aliases=["Janek z młyna"],
        properties={"role_in_cult": "miller", "age": 23},
        first_seen_paragraph_id=uuid4(),
        project_id=project_id,
    )
    await repo.create_entity(entity)
    assert await repo.get_entity(entity.id) == entity


async def test_no_dedupe_two_identical_entities_make_two_nodes(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """INV-8 (temporary, M2): no merge — identical candidates become distinct nodes."""
    repo, project_id = graph
    para_id = uuid4()

    def janek() -> GraphEntity:
        return GraphEntity(
            type="Character",
            canonical_name_pl="Janek",
            project_id=project_id,
            first_seen_paragraph_id=para_id,
        )

    first, second = janek(), janek()
    await repo.create_entity(first)
    await repo.create_entity(second)

    # Distinct app-side ids, and two physical nodes — not one merged-on-name node.
    assert first.id != second.id
    assert await repo.count_entities(project_id) == 2


async def test_relation_round_trip(graph: tuple[Neo4jRepo, UUID]) -> None:
    repo, project_id = graph
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    mill = GraphEntity(type="Location", canonical_name_pl="Młyn", project_id=project_id)
    await repo.create_entity(janek)
    await repo.create_entity(mill)

    relation = GraphRelation(
        type="LIVES_IN",
        subject_id=janek.id,
        object_id=mill.id,
        confidence=0.9,
        source_paragraph_id=uuid4(),
        properties={"since": "childhood"},
    )
    await repo.create_relation(relation)

    assert await repo.get_relations(project_id) == [relation]
