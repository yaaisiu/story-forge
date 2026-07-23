"""Unit tests for the reader tooltip's graph-derived relation summary (S7, spec §3.5).

The tooltip shows up to three of an entity's connections, one line per distinct neighbour,
ordered so the *structurally significant* links surface first: by the neighbour's connection
count — its number of distinct neighbours, **not** its edge count — most-connected first
(spec §3.5). These tests encode that ordering, its tiebreaks, the fail-closed posture inherited
from `domain/neighbourhood.py` (self-loops, unnameable endpoints, and edges the reader can't see
are omitted rather than rendered into the void, and don't inflate anyone's rank), and the
overflow count, which counts unshown neighbours rather than unshown edges.
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

    # Two neighbours, two lines — the three Oakhaven edges collapse to one. Both neighbours are
    # dead ends (one distinct neighbour each), so the predicate tiebreak decides the order: the
    # parallel edges must NOT buy Oakhaven a better rank, which is the bug this pins.
    assert [line.neighbour_name for line in summary.lines] == ["Janek", "Oakhaven"]
    # The kept edge for a neighbour is its alphabetically-first predicate — deterministic.
    assert [line.predicate for line in summary.lines] == ["BROTHER_OF", "CAUGHT"]
    assert summary.overflow == 0


def test_parallel_edges_do_not_outrank_a_genuinely_better_connected_neighbour() -> None:
    # The `/code-review` catch: ranking by incident *edge* count while the display collapses to
    # one line per neighbour let a dead end joined by several parallel edges beat a real hub.
    # Karczma touches only Bronisław (4 parallel edges); Janek touches three different entities.
    extra_a = UUID("00000000-0000-4000-8000-00000000000a")
    extra_b = UUID("00000000-0000-4000-8000-00000000000b")
    karczma = UUID("00000000-0000-4000-8000-000000000005")
    names = {**NAMES, karczma: "Karczma", extra_a: "Postać A", extra_b: "Postać B"}
    relations = [
        _rel(BRONISLAW, "ZZ_A", karczma),
        _rel(BRONISLAW, "ZZ_B", karczma),
        _rel(BRONISLAW, "ZZ_C", karczma),
        _rel(BRONISLAW, "ZZ_D", karczma),
        _rel(BRONISLAW, "AA_KNOWS", JANEK),
        _rel(JANEK, "KNOWS", extra_a),
        _rel(JANEK, "KNOWS", extra_b),
    ]

    lines = summarise_relations(relations, names)[BRONISLAW].lines

    # Janek (3 distinct neighbours) must lead Karczma (1), despite Karczma's 4 parallel edges.
    assert [line.neighbour_name for line in lines] == ["Janek", "Karczma"]


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


def test_an_entity_with_no_canonical_name_is_omitted_not_rendered_blank() -> None:
    # `/code-review` catch: `GraphEntity` permits both canonical names to be None, and the
    # caller's resolver maps that to "" — so a key-presence guard let the edge through and the
    # tooltip rendered "→ KNOWS " with nothing after the predicate.
    nameless = UUID("00000000-0000-4000-8000-00000000000c")
    names = {**NAMES, nameless: ""}
    relations = [_rel(BRONISLAW, "LIVES_IN", OAKHAVEN), _rel(BRONISLAW, "KNOWS", nameless)]

    summaries = summarise_relations(relations, names)

    assert [line.neighbour_name for line in summaries[BRONISLAW].lines] == ["Oakhaven"]
    assert summaries[BRONISLAW].overflow == 0
    assert nameless not in summaries


def test_a_nameless_neighbour_does_not_inflate_another_neighbours_rank() -> None:
    # The nameless node must not count toward degree either, or it could push a real, named
    # connection out of the three-line budget.
    nameless = UUID("00000000-0000-4000-8000-00000000000d")
    names = {**NAMES, nameless: ""}
    relations = [
        _rel(BRONISLAW, "CARRIES", AMULET),
        _rel(BRONISLAW, "LIVES_IN", OAKHAVEN),
        # These would give Oakhaven a degree of 3 if the nameless node counted.
        _rel(OAKHAVEN, "NEAR", nameless),
        _rel(OAKHAVEN, "OVER", nameless),
    ]

    lines = summarise_relations(relations, names)[BRONISLAW].lines

    # Both real neighbours are degree 1, so the predicate tiebreak decides — not Oakhaven's
    # phantom connections.
    assert [line.predicate for line in lines] == ["CARRIES", "LIVES_IN"]


def test_only_narrows_which_entities_get_a_summary_without_changing_the_ranking() -> None:
    # The reader catalogues only entities that appear in the prose, so building the rest is
    # discarded work — but the *ranking* must still see the whole graph, or a neighbour's
    # significance would depend on which subset happens to be displayed.
    relations = [
        _rel(BRONISLAW, "CARRIES", AMULET),
        _rel(BRONISLAW, "LIVES_IN", OAKHAVEN),
        # These make Oakhaven a hub; Oakhaven itself is not in `only`.
        _rel(OAKHAVEN, "HOLDS", JANEK),
        _rel(OAKHAVEN, "NEAR", AMULET),
    ]

    summaries = summarise_relations(relations, NAMES, only={BRONISLAW})

    assert set(summaries) == {BRONISLAW}
    # Oakhaven still leads on its whole-graph degree (3) over Amulet (2), even though Oakhaven
    # got no summary of its own.
    assert [line.neighbour_name for line in summaries[BRONISLAW].lines] == ["Oakhaven", "Amulet"]
