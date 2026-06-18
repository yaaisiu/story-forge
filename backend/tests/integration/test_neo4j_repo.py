"""Neo4j graph-write repository against the real compose neo4j service (spec §6.4, §9 M3).

Under M3 intercept-before-write the graph is written only by the human-accept path, and
`create_entity` is an idempotent **upsert by id** (MERGE on the unique id) — a retried accept
never doubles a node. It is *not* a name-merge: two entities with distinct ids stay distinct
(folding two candidates into one is the human's review act, via `add_alias`). These tests pin
that contract plus a plain round-trip of entities and relations.

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


async def test_same_name_distinct_ids_make_two_nodes(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """The graph never merges on *name*: two same-named entities with distinct ids stay two
    nodes. Deduping them is the human's review act (INV-9), not an automatic graph write."""
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


async def test_create_entity_is_idempotent_by_id(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """The accept-path retry contract: re-creating the *same* id writes no second node.

    `create_entity` MERGEs on the unique id, so a retried human-accept (a crash before the
    candidate's status flip, replayed with the same deterministic id) is a no-op, not a dup.
    """
    repo, project_id = graph
    entity = GraphEntity(type="Character", canonical_name_pl="Mokosz", project_id=project_id)
    await repo.create_entity(entity)
    await repo.create_entity(entity)  # retry — same id

    assert await repo.count_entities(project_id) == 1


async def test_add_alias_folds_a_surface_form_idempotently(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """Accept-merge records the candidate's surface form as an alias of the chosen target.

    Idempotent — a retried accept does not duplicate the alias.
    """
    repo, project_id = graph
    entity = GraphEntity(
        type="Character", canonical_name_pl="Bronisław", aliases=["Bronek"], project_id=project_id
    )
    await repo.create_entity(entity)
    await repo.add_alias(entity.id, "Stary Bronek")
    await repo.add_alias(entity.id, "Stary Bronek")  # retry — no duplicate

    stored = await repo.get_entity(entity.id)
    assert stored is not None
    assert sorted(stored.aliases) == ["Bronek", "Stary Bronek"]


async def test_list_entities_returns_all_of_a_projects_nodes(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """The graph viewer reads every node for a project (spec §3.4) — scoped to it."""
    repo, project_id = graph
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    mill = GraphEntity(type="Location", canonical_name_pl="Młyn", project_id=project_id)
    # A node in a *different* project must not leak into this project's listing.
    other_project = uuid4()
    other = GraphEntity(type="Character", canonical_name_pl="Obcy", project_id=other_project)
    for entity in (janek, mill, other):
        await repo.create_entity(entity)
    try:
        listed = await repo.list_entities(project_id)

        assert {e.id for e in listed} == {janek.id, mill.id}
        assert all(e.project_id == project_id for e in listed)
    finally:
        await repo.delete_project_graph(other_project)  # the fixture only cleans `project_id`


async def test_list_entities_empty_for_a_project_with_no_graph(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    repo, project_id = graph
    assert await repo.list_entities(project_id) == []


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


async def test_get_neighbourhood_returns_incident_edges_both_directions(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """The 1-hop query returns every edge touching the focal node — incoming and outgoing —
    paired with the node on the far end, and ignores edges between other entities."""
    repo, project_id = graph
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=project_id)
    garret = GraphEntity(type="Character", canonical_name_pl="Garret", project_id=project_id)
    elsewhere = GraphEntity(type="Location", canonical_name_pl="Młyn", project_id=project_id)
    for entity in (janek, maria, garret, elsewhere):
        await repo.create_entity(entity)
    out_edge = GraphRelation(type="LOVES", subject_id=janek.id, object_id=maria.id, confidence=0.9)
    in_edge = GraphRelation(
        type="EMPLOYS", subject_id=garret.id, object_id=janek.id, confidence=0.8
    )
    # An edge between two *other* entities — must not appear in Janek's neighbourhood.
    other = GraphRelation(type="NEAR", subject_id=garret.id, object_id=elsewhere.id, confidence=0.7)
    for relation in (out_edge, in_edge, other):
        await repo.create_relation(relation)

    pairs = await repo.get_neighbourhood(janek.id)

    by_edge = {rel.id: (rel, neighbour) for rel, neighbour in pairs}
    assert set(by_edge) == {out_edge.id, in_edge.id}
    assert by_edge[out_edge.id][0] == out_edge
    assert by_edge[out_edge.id][1] == maria  # far end of the outgoing edge
    assert by_edge[in_edge.id][1] == garret  # far end of the incoming edge


async def test_get_neighbourhood_empty_for_unconnected_entity(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    repo, project_id = graph
    lonely = GraphEntity(type="Character", canonical_name_pl="Sam", project_id=project_id)
    await repo.create_entity(lonely)
    assert await repo.get_neighbourhood(lonely.id) == []
