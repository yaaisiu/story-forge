"""Unit tests for the pure graph-wide predicate-rename planner (`domain/predicate_rename.py`,
Graph-quality S6a-2, DM-NN-4).

The first failing test of the predicate apply op: given every committed edge, a from/to predicate,
and the `edge_uid` handle to carry per bearing edge, produce a store-free plan — one
`RelationRekeyPlan` per edge bearing the old predicate, plus renamed/folded counts. It reuses the
tested single-edge `plan_relation_rekey` (S5b) per bearing edge, so the identity rules (content id
re-keys on the predicate change; `edge_uid` survives; a MERGE-collision onto a pre-existing target
edge folds) are inherited. Pure — no store, no I/O. `EntityEditService.rename_predicate` drives the
Neo4j/Postgres writes from this plan.

Key correctness fact exercised below: two *distinct* edges bearing P can never re-key to the same
new id (they differ in subject/object, so `uuid5(s, Q, o)` differs too), so the only folds are
against edges that already bore Q *before* the rename — a single pre-rename snapshot of edge ids is
enough to classify every step.
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.graph import GraphRelation
from story_forge.domain.predicate_rename import plan_predicate_rename


def _edge(subject_id: UUID, predicate: str, object_id: UUID, **overrides: object) -> GraphRelation:
    base: dict[str, object] = {
        "id": relation_edge_id(subject_id, predicate, object_id),
        "type": predicate,
        "subject_id": subject_id,
        "object_id": object_id,
        "confidence": 1.0,
        "edge_uid": uuid4(),
    }
    base.update(overrides)
    return GraphRelation(**base)  # type: ignore[arg-type]


def _handles(*edges: GraphRelation) -> dict[UUID, UUID]:
    """The service resolves each bearing edge's handle (its own, or a freshly-minted one for a
    legacy handle-less edge) before calling the planner; mirror that here."""
    return {edge.id: (edge.edge_uid or uuid4()) for edge in edges}


def test_renames_every_bearing_edge_and_leaves_the_rest_untouched() -> None:
    s1, o1, s2, o2, s3, o3 = (uuid4() for _ in range(6))
    p1 = _edge(s1, "PASSENGER_ON", o1)
    p2 = _edge(s2, "PASSENGER_ON", o2)
    other = _edge(s3, "LOVES", o3)

    plan = plan_predicate_rename(
        [p1, p2, other],
        _handles(p1, p2),
        from_predicate="PASSENGER_ON",
        to_predicate="ON_SHIP",
    )

    assert plan.renamed_count == 2
    assert plan.folded_count == 0
    # only the two bearing edges have steps; `other` is untouched (no step).
    stepped_ids = {step.old_edge.id for step in plan.steps}
    assert stepped_ids == {p1.id, p2.id}
    for step in plan.steps:
        assert step.kind == "repoint"
        assert step.new_edge is not None
        assert step.new_edge.type == "ON_SHIP"


def test_handles_ride_across_the_rename() -> None:
    s, o = uuid4(), uuid4()
    edge = _edge(s, "PASSENGER_ON", o)

    plan = plan_predicate_rename(
        [edge],
        _handles(edge),
        from_predicate="PASSENGER_ON",
        to_predicate="ON_SHIP",
    )

    (step,) = plan.steps
    assert step.new_edge is not None
    assert step.new_edge.edge_uid == edge.edge_uid


def test_legacy_handle_less_edge_carries_the_minted_handle() -> None:
    s, o = uuid4(), uuid4()
    edge = _edge(s, "PASSENGER_ON", o, edge_uid=None)
    minted = uuid4()

    plan = plan_predicate_rename(
        [edge],
        {edge.id: minted},
        from_predicate="PASSENGER_ON",
        to_predicate="ON_SHIP",
    )

    (step,) = plan.steps
    assert step.new_edge is not None
    assert step.new_edge.edge_uid == minted


def test_folds_when_the_target_edge_already_exists() -> None:
    # A bearing edge (s, P, o) whose renamed id (s, Q, o) already exists in the graph is a
    # MERGE-collision → fold, counted and reported, never the goal.
    s, o = uuid4(), uuid4()
    bearing = _edge(s, "PASSENGER_ON", o)
    pre_existing_q = _edge(s, "ON_SHIP", o)  # same endpoints, already ON_SHIP

    plan = plan_predicate_rename(
        [bearing, pre_existing_q],
        _handles(bearing),
        from_predicate="PASSENGER_ON",
        to_predicate="ON_SHIP",
    )

    assert plan.folded_count == 1
    assert plan.renamed_count == 0
    (step,) = plan.steps
    assert step.kind == "fold"
    assert step.old_edge.id == bearing.id


def test_two_distinct_bearing_edges_never_collide_with_each_other() -> None:
    # The graph-wide correctness claim: renaming two *different* P-edges cannot make them collide
    # (distinct endpoints → distinct new ids), so with no pre-existing Q edge both repoint, and
    # nothing folds — the pre-rename snapshot alone classifies every step.
    s1, o1, s2, o2 = (uuid4() for _ in range(4))
    p1 = _edge(s1, "PASSENGER_ON", o1)
    p2 = _edge(s2, "PASSENGER_ON", o2)

    plan = plan_predicate_rename(
        [p1, p2],
        _handles(p1, p2),
        from_predicate="PASSENGER_ON",
        to_predicate="ON_SHIP",
    )

    assert plan.renamed_count == 2
    assert plan.folded_count == 0


def test_rename_to_the_same_predicate_is_a_noop() -> None:
    s, o = uuid4(), uuid4()
    edge = _edge(s, "LOVES", o)

    plan = plan_predicate_rename(
        [edge],
        _handles(edge),
        from_predicate="LOVES",
        to_predicate="LOVES",
    )

    assert plan.steps == ()
    assert plan.renamed_count == 0
    assert plan.folded_count == 0


def test_blank_target_predicate_is_rejected() -> None:
    s, o = uuid4(), uuid4()
    edge = _edge(s, "LOVES", o)

    with pytest.raises(ValueError, match="non-empty"):
        plan_predicate_rename(
            [edge],
            _handles(edge),
            from_predicate="LOVES",
            to_predicate="   ",
        )
