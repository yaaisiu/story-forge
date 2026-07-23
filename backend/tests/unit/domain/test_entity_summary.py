"""Unit tests for the reader tooltip's graph-derived relation summary (S7, spec §3.5).

The tooltip shows up to three of an entity's relations, ordered so the *structurally
significant* links surface first: by the neighbour's connection count, most-connected first
(spec §3.5). These tests encode that ordering, its tiebreaks, the fail-closed posture
inherited from `domain/neighbourhood.py` (self-loops and dangling endpoints are omitted,
never rendered into the void), and the overflow count.
"""

from __future__ import annotations

from uuid import UUID

from story_forge.domain.entity_summary import summarise_relations
from story_forge.domain.graph import GraphRelation

BRONISLAW = UUID("00000000-0000-4000-8000-000000000001")
OAKHAVEN = UUID("00000000-0000-4000-8000-000000000002")
JANEK = UUID("00000000-0000-4000-8000-000000000003")
AMULET = UUID("00000000-0000-4000-8000-000000000004")
GHOST = UUID("00000000-0000-4000-8000-0000000000ee")

NAMES = {
    BRONISLAW: "Bronisław",
    OAKHAVEN: "Oakhaven",
    JANEK: "Janek",
    AMULET: "Amulet",
}


def _rel(subject: UUID, predicate: str, obj: UUID) -> GraphRelation:
    return GraphRelation(type=predicate, subject_id=subject, object_id=obj, confidence=0.9)


def test_entity_with_no_relations_is_absent_from_the_summary_map() -> None:
    summaries = summarise_relations([], NAMES)
    assert BRONISLAW not in summaries


def test_a_single_relation_renders_with_its_direction_predicate_and_neighbour_name() -> None:
    summaries = summarise_relations([_rel(BRONISLAW, "LIVES_IN", OAKHAVEN)], NAMES)

    assert len(summaries[BRONISLAW].lines) == 1
    line = summaries[BRONISLAW].lines[0]
    assert line.direction == "out"
    assert line.predicate == "LIVES_IN"
    assert line.neighbour_name == "Oakhaven"
    assert summaries[BRONISLAW].overflow == 0


def test_the_relation_is_mirrored_onto_the_neighbour_with_the_opposite_direction() -> None:
    summaries = summarise_relations([_rel(BRONISLAW, "LIVES_IN", OAKHAVEN)], NAMES)

    mirrored = summaries[OAKHAVEN].lines[0]
    assert mirrored.direction == "in"
    assert mirrored.predicate == "LIVES_IN"
    assert mirrored.neighbour_name == "Bronisław"


def test_lines_are_ordered_by_the_neighbours_connection_count_most_connected_first() -> None:
    # Oakhaven is a hub (3 edges), Janek middling (2), Amulet a leaf (1) — so Bronisław's
    # tooltip should lead with Oakhaven even though ties would sort the predicates otherwise.
    relations = [
        _rel(BRONISLAW, "CARRIES", AMULET),
        _rel(BRONISLAW, "BROTHER_OF", JANEK),
        _rel(BRONISLAW, "LIVES_IN", OAKHAVEN),
        # Padding that raises the neighbours' degrees without touching Bronisław.
        _rel(JANEK, "LIVES_IN", OAKHAVEN),
        _rel(AMULET, "KEPT_IN", OAKHAVEN),
    ]

    lines = summarise_relations(relations, NAMES)[BRONISLAW].lines

    assert [line.neighbour_name for line in lines] == ["Oakhaven", "Janek", "Amulet"]


def test_equal_degree_neighbours_tiebreak_on_predicate_then_name() -> None:
    # Janek and Amulet both have degree 1 here, so the predicate decides the order.
    relations = [
        _rel(BRONISLAW, "CARRIES", AMULET),
        _rel(BRONISLAW, "BROTHER_OF", JANEK),
    ]

    lines = summarise_relations(relations, NAMES)[BRONISLAW].lines

    assert [line.predicate for line in lines] == ["BROTHER_OF", "CARRIES"]


def test_only_the_first_three_are_kept_and_the_rest_are_counted_as_overflow() -> None:
    extra = UUID("00000000-0000-4000-8000-000000000005")
    names = {**NAMES, extra: "Karczma"}
    relations = [
        _rel(BRONISLAW, "LIVES_IN", OAKHAVEN),
        _rel(BRONISLAW, "BROTHER_OF", JANEK),
        _rel(BRONISLAW, "CARRIES", AMULET),
        _rel(BRONISLAW, "DRINKS_AT", extra),
    ]

    summary = summarise_relations(relations, names)[BRONISLAW]

    assert len(summary.lines) == 3
    assert summary.overflow == 1


def test_the_limit_is_configurable() -> None:
    relations = [
        _rel(BRONISLAW, "LIVES_IN", OAKHAVEN),
        _rel(BRONISLAW, "BROTHER_OF", JANEK),
        _rel(BRONISLAW, "CARRIES", AMULET),
    ]

    summary = summarise_relations(relations, NAMES, limit=1)[BRONISLAW]

    assert len(summary.lines) == 1
    assert summary.overflow == 2


def test_a_self_loop_is_dropped_rather_than_rendered_as_a_neighbour() -> None:
    # A merge artifact: an edge whose endpoints are the same entity is never a real
    # "relates to itself" (the posture `build_ego_graph` already takes).
    summaries = summarise_relations([_rel(BRONISLAW, "KNOWS", BRONISLAW)], NAMES)

    assert BRONISLAW not in summaries


def test_an_edge_whose_neighbour_has_no_name_is_omitted_not_rendered_into_the_void() -> None:
    # GHOST is absent from the name map (deleted/merged away) — fail closed.
    summaries = summarise_relations(
        [_rel(BRONISLAW, "LIVES_IN", OAKHAVEN), _rel(BRONISLAW, "KNOWS", GHOST)], NAMES
    )

    assert [line.neighbour_name for line in summaries[BRONISLAW].lines] == ["Oakhaven"]
    assert summaries[BRONISLAW].overflow == 0
    assert GHOST not in summaries


def test_a_dangling_edge_does_not_inflate_a_neighbours_connection_count() -> None:
    # The ghost edges must not make Oakhaven look better-connected than it is, or the
    # ordering would be driven by edges the reader can never see.
    relations = [
        _rel(BRONISLAW, "CARRIES", AMULET),
        _rel(BRONISLAW, "LIVES_IN", OAKHAVEN),
        _rel(GHOST, "HAUNTS", AMULET),
        _rel(GHOST, "HAUNTS", AMULET),
    ]

    lines = summarise_relations(relations, NAMES)[BRONISLAW].lines

    # Both neighbours are degree 1 among *visible* edges, so the predicate tiebreak decides.
    assert [line.predicate for line in lines] == ["CARRIES", "LIVES_IN"]


def test_duplicate_edge_ids_are_counted_once() -> None:
    # `GraphRelation.id` is uuid5 of the (subject, predicate, object) triple, so the same
    # triple read twice is one edge, not two.
    rel = _rel(BRONISLAW, "LIVES_IN", OAKHAVEN)
    duplicate = GraphRelation(
        id=rel.id,
        type=rel.type,
        subject_id=rel.subject_id,
        object_id=rel.object_id,
        confidence=rel.confidence,
    )

    summary = summarise_relations([rel, duplicate], NAMES)[BRONISLAW]

    assert len(summary.lines) == 1
    assert summary.overflow == 0


def test_the_ordering_is_fully_deterministic_regardless_of_input_order() -> None:
    # Same edges, reversed: the tooltip must not reshuffle between reads.
    relations = [
        _rel(BRONISLAW, "CARRIES", AMULET),
        _rel(BRONISLAW, "BROTHER_OF", JANEK),
        _rel(BRONISLAW, "LIVES_IN", OAKHAVEN),
    ]

    forward = summarise_relations(relations, NAMES)[BRONISLAW].lines
    backward = summarise_relations(list(reversed(relations)), NAMES)[BRONISLAW].lines

    assert [line.predicate for line in forward] == [line.predicate for line in backward]


def test_several_edges_to_one_neighbour_collapse_to_a_single_line() -> None:
    # Live Oakhaven check (S7 smoke): ordering by degree alone let the single biggest hub take
    # every slot — "→ CATCHES_ATTENTION_OF Locke / ← CAUGHT Locke / ← DEMANDED_HANDOVER Locke"
    # says one thing three times and hides the entity's other connections. One line per distinct
    # neighbour keeps the tooltip a summary of *who* an entity is connected to.
    relations = [
        _rel(BRONISLAW, "HUNTS", OAKHAVEN),
        _rel(BRONISLAW, "CAUGHT", OAKHAVEN),
        _rel(BRONISLAW, "POINTS_AT", OAKHAVEN),
        _rel(BRONISLAW, "BROTHER_OF", JANEK),
    ]

    summary = summarise_relations(relations, NAMES)[BRONISLAW]

    assert [line.neighbour_name for line in summary.lines] == ["Oakhaven", "Janek"]
    # The kept edge for a neighbour is its alphabetically-first predicate — deterministic.
    assert summary.lines[0].predicate == "CAUGHT"
    assert summary.overflow == 0


def test_overflow_counts_unshown_neighbours_not_unshown_edges() -> None:
    # With one line per neighbour, "+N more" must mean "N more connections", so an entity with
    # many edges to few neighbours doesn't claim a misleading pile of hidden links.
    extra = UUID("00000000-0000-4000-8000-000000000005")
    names = {**NAMES, extra: "Karczma"}
    relations = [
        _rel(BRONISLAW, "HUNTS", OAKHAVEN),
        _rel(BRONISLAW, "CAUGHT", OAKHAVEN),
        _rel(BRONISLAW, "BROTHER_OF", JANEK),
        _rel(BRONISLAW, "CARRIES", AMULET),
        _rel(BRONISLAW, "DRINKS_AT", extra),
    ]

    summary = summarise_relations(relations, names)[BRONISLAW]

    assert len(summary.lines) == 3
    # Four distinct neighbours, three shown → one hidden (not "two hidden edges").
    assert summary.overflow == 1
