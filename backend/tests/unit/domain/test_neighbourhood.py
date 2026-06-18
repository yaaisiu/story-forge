"""Unit tests for the pure 1-hop ego-graph assembly (M4.S2a, spec §3.5 side panel).

`build_ego_graph` takes a focal entity id + the relation edges incident to it (each paired
with the accepted entity on the far end) and returns the focal node's direct neighbours +
the edges touching it, oriented relative to the focal node. Pure, deterministic, no I/O —
the layer the project unit-tests hardest. The Neo4j 1-hop query that feeds it is tested
separately (integration); here we own the *assembly* rules: direction, neighbour de-dup,
self-loop omission, ordering.
"""

from __future__ import annotations

from uuid import uuid4

from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.neighbourhood import build_ego_graph

PROJECT = uuid4()


def _entity(name: str) -> GraphEntity:
    return GraphEntity(type="Character", canonical_name_pl=name, project_id=PROJECT)


def _relation(subject_id: object, object_id: object, predicate: str = "KNOWS") -> GraphRelation:
    return GraphRelation(
        type=predicate,
        subject_id=subject_id,  # type: ignore[arg-type]
        object_id=object_id,  # type: ignore[arg-type]
        confidence=0.9,
    )


def test_empty_neighbourhood() -> None:
    ego = build_ego_graph(uuid4(), [])
    assert ego.neighbours == []
    assert ego.edges == []


def test_outgoing_edge() -> None:
    focal, maria = _entity("Janek"), _entity("Maria")
    rel = _relation(focal.id, maria.id, "LOVES")

    ego = build_ego_graph(focal.id, [(rel, maria)])

    assert [n.entity_id for n in ego.neighbours] == [maria.id]
    assert ego.neighbours[0].canonical_name_pl == "Maria"
    assert len(ego.edges) == 1
    edge = ego.edges[0]
    assert edge.id == rel.id
    assert edge.type == "LOVES"
    assert edge.direction == "out"
    assert edge.neighbour_id == maria.id
    assert edge.confidence == 0.9


def test_incoming_edge() -> None:
    focal, garret = _entity("Janek"), _entity("Garret")
    rel = _relation(garret.id, focal.id, "EMPLOYS")

    ego = build_ego_graph(focal.id, [(rel, garret)])

    assert [n.entity_id for n in ego.neighbours] == [garret.id]
    assert ego.edges[0].direction == "in"
    assert ego.edges[0].neighbour_id == garret.id


def test_two_edges_to_same_neighbour_dedupe_node_keep_both_edges() -> None:
    # "loves" AND "betrays" between the same pair → one neighbour, two distinct edges.
    focal, elara = _entity("Janek"), _entity("Elara")
    loves = _relation(focal.id, elara.id, "LOVES")
    betrays = _relation(focal.id, elara.id, "BETRAYS")

    ego = build_ego_graph(focal.id, [(loves, elara), (betrays, elara)])

    assert [n.entity_id for n in ego.neighbours] == [elara.id]  # de-duped
    assert {e.type for e in ego.edges} == {"LOVES", "BETRAYS"}
    assert {e.id for e in ego.edges} == {loves.id, betrays.id}


def test_self_loop_dropped() -> None:
    # An edge whose endpoints are both the focal entity (a merge artifact) is never a neighbour.
    focal = _entity("Janek")
    loop = _relation(focal.id, focal.id, "KNOWS")

    ego = build_ego_graph(focal.id, [(loop, focal)])

    assert ego.neighbours == []
    assert ego.edges == []


def test_non_incident_edge_skipped() -> None:
    # Defensive: an edge that doesn't actually touch the focal id is omitted, not guessed.
    focal, a, b = _entity("Janek"), _entity("A"), _entity("B")
    stray = _relation(a.id, b.id, "KNOWS")

    ego = build_ego_graph(focal.id, [(stray, b)])

    assert ego.neighbours == []
    assert ego.edges == []


def test_neighbours_sorted_deterministically() -> None:
    focal = _entity("Janek")
    # Insert in non-sorted order; expect a stable, name-then-id ordering out.
    zofia, anna = _entity("Zofia"), _entity("Anna")
    r1 = _relation(focal.id, zofia.id)
    r2 = _relation(focal.id, anna.id)

    ego = build_ego_graph(focal.id, [(r1, zofia), (r2, anna)])

    assert [n.canonical_name_pl for n in ego.neighbours] == ["Anna", "Zofia"]
