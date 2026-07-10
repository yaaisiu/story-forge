"""Unit tests for the pure edge re-key planner (`domain/relation_rekey.py`, Graph-quality S5b-be).

The first failing test of S5b-be: given a committed edge and a new predicate and/or new endpoint,
plus the `edge_uid` handle to carry and whether an edge already exists at the new content id,
produce the store-free plan — no-op / repoint / fold — with the surrogate handle preserved across
the re-key (DM-S5-2/3, INV-10). Pure — no store, no I/O — so the identity rules (content id
re-keys on any triple change; `edge_uid` survives; the fold survivor rule) are unit-tested without
a database. `EntityEditService.retarget_relation` drives the Neo4j/Postgres writes from this plan.
"""

from __future__ import annotations

from uuid import uuid4

from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.graph import GraphRelation
from story_forge.domain.relation_rekey import plan_relation_rekey


def _edge(
    subject_id: object, predicate: str, object_id: object, **overrides: object
) -> GraphRelation:
    base: dict[str, object] = {
        "id": relation_edge_id(subject_id, predicate, object_id),  # type: ignore[arg-type]
        "type": predicate,
        "subject_id": subject_id,
        "object_id": object_id,
        "confidence": 1.0,
        "edge_uid": uuid4(),
    }
    base.update(overrides)
    return GraphRelation(**base)  # type: ignore[arg-type]


def test_noop_when_new_triple_equals_old() -> None:
    subj, obj = uuid4(), uuid4()
    edge = _edge(subj, "LOVES", obj)

    plan = plan_relation_rekey(
        edge,
        new_predicate="LOVES",
        new_subject_id=subj,
        new_object_id=obj,
        edge_uid=edge.edge_uid,  # type: ignore[arg-type]
        collision_exists=False,
    )

    assert plan.kind == "noop"
    assert plan.new_edge is None


def test_repredicate_re_keys_the_id_and_preserves_the_handle() -> None:
    subj, obj = uuid4(), uuid4()
    edge = _edge(subj, "PASSENGER_ON", obj)

    plan = plan_relation_rekey(
        edge,
        new_predicate="ON_SHIP",
        new_subject_id=subj,
        new_object_id=obj,
        edge_uid=edge.edge_uid,  # type: ignore[arg-type]
        collision_exists=False,
    )

    assert plan.kind == "repoint"
    assert plan.new_edge is not None
    # the content id is re-derived from the *new* predicate — a genuinely new edge id …
    assert plan.new_edge.id == relation_edge_id(subj, "ON_SHIP", obj)
    assert plan.new_edge.id != edge.id
    assert plan.new_edge.type == "ON_SHIP"
    # … but the surrogate handle rides across the re-key unchanged (INV-10).
    assert plan.new_edge.edge_uid == edge.edge_uid


def test_retarget_an_endpoint_repoints_and_preserves_the_handle() -> None:
    subj, old_obj, new_obj = uuid4(), uuid4(), uuid4()
    edge = _edge(subj, "OWNS", old_obj)

    plan = plan_relation_rekey(
        edge,
        new_predicate="OWNS",
        new_subject_id=subj,
        new_object_id=new_obj,
        edge_uid=edge.edge_uid,  # type: ignore[arg-type]
        collision_exists=False,
    )

    assert plan.kind == "repoint"
    assert plan.new_edge is not None
    assert plan.new_edge.object_id == new_obj
    assert plan.new_edge.id == relation_edge_id(subj, "OWNS", new_obj)
    assert plan.new_edge.edge_uid == edge.edge_uid


def test_fold_when_an_edge_already_exists_at_the_new_id() -> None:
    # Re-keying onto a triple the graph already has is a MERGE-collision → fold. The plan still
    # produces `new_edge` (the caller MERGEs onto the survivor), but the caller must NOT mint a new
    # survivor handle: the survivor keeps its own, the folded old edge's handle → the before-image.
    subj, obj = uuid4(), uuid4()
    edge = _edge(subj, "PASSENGER_ON", obj)

    plan = plan_relation_rekey(
        edge,
        new_predicate="ON_SHIP",
        new_subject_id=subj,
        new_object_id=obj,
        edge_uid=edge.edge_uid,  # type: ignore[arg-type]
        collision_exists=True,
    )

    assert plan.kind == "fold"
    assert plan.new_edge is not None
    assert plan.new_edge.id == relation_edge_id(subj, "ON_SHIP", obj)


def test_retarget_into_a_self_loop_is_allowed_as_a_repoint() -> None:
    # A merge *discards* a self-loop artifact; a manual re-target INTO a self-loop is intentional
    # (M4.S3a allowed manual self-loops), so it is a normal repoint, not a discard.
    subj, obj = uuid4(), uuid4()
    edge = _edge(subj, "KNOWS", obj)

    plan = plan_relation_rekey(
        edge,
        new_predicate="KNOWS",
        new_subject_id=subj,
        new_object_id=subj,  # re-target the object onto the subject → self-loop
        edge_uid=edge.edge_uid,  # type: ignore[arg-type]
        collision_exists=False,
    )

    assert plan.kind == "repoint"
    assert plan.new_edge is not None
    assert plan.new_edge.subject_id == plan.new_edge.object_id == subj


def test_a_legacy_handle_less_edge_gets_the_minted_handle_on_the_new_edge() -> None:
    # A pre-§4 edge round-trips with edge_uid=None; the service mints a handle and passes it in, so
    # the re-keyed edge carries it going forward (mint-forward, no backfill — DM-S5-3).
    subj, obj = uuid4(), uuid4()
    edge = _edge(subj, "PASSENGER_ON", obj, edge_uid=None)
    minted = uuid4()

    plan = plan_relation_rekey(
        edge,
        new_predicate="ON_SHIP",
        new_subject_id=subj,
        new_object_id=obj,
        edge_uid=minted,
        collision_exists=False,
    )

    assert plan.new_edge is not None
    assert plan.new_edge.edge_uid == minted
