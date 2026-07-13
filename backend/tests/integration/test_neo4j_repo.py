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


async def test_relation_round_trips_its_edge_uid_handle(graph: tuple[Neo4jRepo, UUID]) -> None:
    """The §4 surrogate handle (ADR 0011) is stored as an edge property and read back verbatim."""
    repo, project_id = graph
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    mill = GraphEntity(type="Location", canonical_name_pl="Młyn", project_id=project_id)
    await repo.create_entity(janek)
    await repo.create_entity(mill)
    handle = uuid4()
    relation = GraphRelation(
        type="LIVES_IN", subject_id=janek.id, object_id=mill.id, confidence=0.9, edge_uid=handle
    )
    await repo.create_relation(relation)

    stored = await repo.get_relation(project_id, relation.id)
    assert stored is not None
    assert stored.edge_uid == handle


async def test_create_relation_coalesces_and_never_overwrites_an_existing_handle(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """`ON CREATE SET` (no `ON MATCH`) *is* the coalesce rule (DM-S5-3): a MERGE that matches an
    existing edge sets nothing, so a duplicate/retried write with a *different* `edge_uid` leaves
    the original handle untouched — the handle is stable identity, not overwritable per-write."""
    repo, project_id = graph
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    mill = GraphEntity(type="Location", canonical_name_pl="Młyn", project_id=project_id)
    await repo.create_entity(janek)
    await repo.create_entity(mill)
    original = uuid4()
    edge = GraphRelation(
        type="LIVES_IN", subject_id=janek.id, object_id=mill.id, confidence=0.9, edge_uid=original
    )
    await repo.create_relation(edge)
    # a duplicate write of the *same content edge* (same id) carrying a fresh handle …
    await repo.create_relation(edge.model_copy(update={"edge_uid": uuid4()}))

    stored = await repo.get_relation(project_id, edge.id)
    assert stored is not None
    assert stored.edge_uid == original  # … does not overwrite the first handle


async def test_a_legacy_edge_written_without_a_handle_reads_back_none(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """Mint-forward, no backfill (DM-S5-3): an edge written with no `edge_uid` round-trips to
    `None`, so the model default must not fabricate a handle on read."""
    repo, project_id = graph
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    mill = GraphEntity(type="Location", canonical_name_pl="Młyn", project_id=project_id)
    await repo.create_entity(janek)
    await repo.create_entity(mill)
    edge = GraphRelation(type="LIVES_IN", subject_id=janek.id, object_id=mill.id, confidence=0.9)
    await repo.create_relation(edge)

    stored = await repo.get_relation(project_id, edge.id)
    assert stored is not None
    assert stored.edge_uid is None


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


async def test_update_entity_overwrites_editable_fields(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """The human-edit mutator (M4.S3a): re-SET an existing node's display + properties fields and
    read the new state back, including clearing one canonical name to `None`."""
    repo, project_id = graph
    entity = GraphEntity(
        type="Character",
        canonical_name_pl="Janek",
        canonical_name_en="Johnny",
        aliases=["młynarczyk"],
        properties={"age": 23},
        project_id=project_id,
    )
    await repo.create_entity(entity)

    edited = entity.model_copy(
        update={
            "type": "Deity",
            "canonical_name_en": None,  # cleared — Neo4j drops the property
            "aliases": ["the miller", "Jan"],
            "properties": {"role": "priestess", "married": True},
        }
    )
    await repo.update_entity(edited)

    assert await repo.get_entity(entity.id) == edited


async def test_update_entity_missing_node_is_a_noop(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """`MATCH`-not-`MERGE`: updating an absent id writes nothing (no resurrection)."""
    repo, project_id = graph
    ghost = GraphEntity(type="Character", canonical_name_pl="Nobody", project_id=project_id)
    await repo.update_entity(ghost)
    assert await repo.get_entity(ghost.id) is None


async def test_delete_relation_removes_the_edge(graph: tuple[Neo4jRepo, UUID]) -> None:
    """The human relation-remove path (M4.S3a): delete one edge by id; a re-delete is idempotent."""
    repo, project_id = graph
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=project_id)
    await repo.create_entity(janek)
    await repo.create_entity(maria)
    edge = GraphRelation(type="LOVES", subject_id=janek.id, object_id=maria.id, confidence=0.9)
    await repo.create_relation(edge)
    assert await repo.get_relations(project_id) == [edge]

    await repo.delete_relation(edge.id)
    assert await repo.get_relations(project_id) == []
    await repo.delete_relation(edge.id)  # idempotent re-delete
    assert await repo.get_relations(project_id) == []


async def test_delete_entity_removes_node_and_incident_edges(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """The merge-of-B / whole-entity delete path (M4.S3b, DM-S3b-5): `DETACH DELETE` drops the node
    *and* every edge touching it, leaving an unrelated edge intact; a re-delete is idempotent."""
    repo, project_id = graph
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    maria = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=project_id)
    garret = GraphEntity(type="Character", canonical_name_pl="Garret", project_id=project_id)
    for entity in (janek, maria, garret):
        await repo.create_entity(entity)
    incident = GraphRelation(type="LOVES", subject_id=janek.id, object_id=maria.id, confidence=0.9)
    unrelated = GraphRelation(
        type="KNOWS", subject_id=maria.id, object_id=garret.id, confidence=0.8
    )
    await repo.create_relation(incident)
    await repo.create_relation(unrelated)

    await repo.delete_entity(janek.id)

    assert await repo.get_entity(janek.id) is None
    # the incident edge is gone with the node; the unrelated edge survives
    assert [r.id for r in await repo.get_relations(project_id)] == [unrelated.id]
    assert await repo.count_entities(project_id) == 2

    await repo.delete_entity(janek.id)  # idempotent re-delete (missing node is a no-op)
    assert await repo.count_entities(project_id) == 2


async def test_manual_self_loop_relation_is_written(graph: tuple[Neo4jRepo, UUID]) -> None:
    """A *manual* self-loop (subject == object) is intentional and is written (DM-S3a-3) —
    unlike the extraction path, which drops self-loops as merge artifacts."""
    repo, project_id = graph
    sole = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    await repo.create_entity(sole)
    loop = GraphRelation(
        type="TALKS_TO_SELF", subject_id=sole.id, object_id=sole.id, confidence=1.0
    )
    await repo.create_relation(loop)
    assert await repo.get_relations(project_id) == [loop]


async def test_list_type_vocabulary_counts_distinct_types(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """S6a type vocabulary: distinct `e.type` labels with node counts, project-scoped.

    Casing/synonym variants stay distinct labels (INV-4 — nothing auto-collapses); the
    synonym self-join is what proposes merging them.
    """
    repo, project_id = graph
    for type_ in ("PERSON", "PERSON", "Person", "LOCATION"):
        await repo.create_entity(
            GraphEntity(type=type_, canonical_name_pl="x", project_id=project_id)
        )
    # A node in another project must not leak into the count.
    other_project = uuid4()
    await repo.create_entity(
        GraphEntity(type="PERSON", canonical_name_pl="y", project_id=other_project)
    )
    try:
        vocab = await repo.list_type_vocabulary(project_id)
        counts = {lc.label: lc.count for lc in vocab}
        assert counts == {"PERSON": 2, "Person": 1, "LOCATION": 1}
        # Ordered by count desc — the dominant label leads.
        assert vocab[0].label == "PERSON"
    finally:
        await repo.delete_project_graph(other_project)


async def test_list_type_vocabulary_excludes_null_type_nodes(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """A legacy/malformed node with no `type` property is filtered, not surfaced as a null label.

    `create_entity` always sets `type`, so this manufactures the malformed node with raw Cypher;
    without the `WHERE e.type IS NOT NULL` guard the read would emit `LabelCount(label=None)` and
    the downstream normalise/encode would crash on `None`.
    """
    repo, project_id = graph
    await repo.create_entity(
        GraphEntity(type="PERSON", canonical_name_pl="A", project_id=project_id)
    )
    await repo._driver.execute_query(
        "CREATE (e:Entity {id: $id, project_id: $pid})",
        id=str(uuid4()),
        pid=str(project_id),
    )
    vocab = await repo.list_type_vocabulary(project_id)
    assert [lc.label for lc in vocab] == ["PERSON"]


async def test_list_predicate_vocabulary_counts_distinct_predicates(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """S6a predicate vocabulary: distinct `type(r)` names with edge counts, project-scoped."""
    repo, project_id = graph
    a = GraphEntity(type="Character", canonical_name_pl="A", project_id=project_id)
    b = GraphEntity(type="Character", canonical_name_pl="B", project_id=project_id)
    c = GraphEntity(type="Character", canonical_name_pl="C", project_id=project_id)
    for entity in (a, b, c):
        await repo.create_entity(entity)
    edges = [
        GraphRelation(type="PASSENGER_ON", subject_id=a.id, object_id=b.id, confidence=0.9),
        GraphRelation(type="PASSENGER_ON", subject_id=a.id, object_id=c.id, confidence=0.9),
        GraphRelation(type="ON_SHIP", subject_id=b.id, object_id=c.id, confidence=0.9),
    ]
    for edge in edges:
        await repo.create_relation(edge)

    vocab = await repo.list_predicate_vocabulary(project_id)
    counts = {lc.label: lc.count for lc in vocab}
    assert counts == {"PASSENGER_ON": 2, "ON_SHIP": 1}
    assert vocab[0].label == "PASSENGER_ON"  # count desc


async def test_vocabularies_empty_for_a_project_with_no_graph(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    repo, project_id = graph
    assert await repo.list_type_vocabulary(project_id) == []
    assert await repo.list_predicate_vocabulary(project_id) == []


async def test_get_neighbourhood_excludes_cross_project_neighbour(
    graph: tuple[Neo4jRepo, UUID],
) -> None:
    """Defense-in-depth (§6.4): the neighbourhood is scoped to the focal node's own project, so a
    stray cross-project edge never surfaces another project's node in the side panel."""
    repo, project_id = graph
    other_project = uuid4()
    janek = GraphEntity(type="Character", canonical_name_pl="Janek", project_id=project_id)
    same = GraphEntity(type="Character", canonical_name_pl="Maria", project_id=project_id)
    foreign = GraphEntity(type="Character", canonical_name_pl="Obcy", project_id=other_project)
    in_project_edge = GraphRelation(
        type="KNOWS", subject_id=janek.id, object_id=same.id, confidence=0.9
    )
    cross_project_edge = GraphRelation(
        type="KNOWS", subject_id=janek.id, object_id=foreign.id, confidence=0.9
    )
    try:
        for entity in (janek, same, foreign):
            await repo.create_entity(entity)
        for relation in (in_project_edge, cross_project_edge):
            await repo.create_relation(relation)

        pairs = await repo.get_neighbourhood(janek.id)

        neighbour_ids = {neighbour.id for _, neighbour in pairs}
        assert neighbour_ids == {same.id}  # foreign neighbour excluded
    finally:
        await repo.delete_project_graph(other_project)  # the fixture only cleans `project_id`
