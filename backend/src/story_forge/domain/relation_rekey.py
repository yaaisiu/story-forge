"""Pure planning for an atomic edge re-key — edit-predicate and/or re-target (Graph-quality
S5b-be, DM-S5-2/3).

Because `relation_edge_id` is `uuid5` of the resolved (subject, predicate, object) triple
(`domain/candidates.py`), changing any of the three **re-keys** the edge: the new predicate/
endpoint is, identity-wise, a *new* edge, not an in-place update. So a re-key is modelled — like a
merge's edge re-point (`domain/entity_merge.py`) — as delete-old + create-new. The one identity
that must survive the re-key is the surrogate handle `edge_uid` (§4, ADR 0011, INV-10): the caller
passes the handle to carry and it rides the new edge across the change.

Pure — no store, no I/O. The fold-vs-repoint distinction is kept pure by passing in whether an
edge already exists at the new id (the caller's read), exactly as `plan_merge` takes the survivor's
existing edge ids. `EntityEditService.retarget_relation` drives the graph/Postgres writes from this
plan.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.graph import GraphRelation


@dataclass(frozen=True)
class RelationRekeyPlan:
    """The store-free plan for one re-key. `kind`:

    - ``noop`` — the new (subject, predicate, object) equals the old, so the content id is
      unchanged; nothing to write (``new_edge`` is ``None``).
    - ``repoint`` — the id changed and no edge exists at the new id: delete the old edge, create
      ``new_edge`` (carrying the preserved ``edge_uid``).
    - ``fold`` — an edge already exists at the new id (a MERGE-collision): delete the old edge and
      MERGE onto the survivor. The surviving edge keeps its *own* handle; the folded (old) edge's
      handle rides the caller's before-image so undo un-folds it (DM-S5-3 survivor rule).
    """

    kind: Literal["noop", "repoint", "fold"]
    new_edge: GraphRelation | None


def plan_relation_rekey(
    old_edge: GraphRelation,
    *,
    new_predicate: str,
    new_subject_id: UUID,
    new_object_id: UUID,
    edge_uid: UUID,
    collision_exists: bool,
) -> RelationRekeyPlan:
    """Plan an atomic edge re-key. Pure — no store, no side effects.

    ``edge_uid`` is the handle to carry: the old edge's, or a freshly-minted one when the old edge
    is a legacy handle-less edge (the caller decides — minting is impure). A resulting self-loop is
    *allowed* (a manual self-loop is intentional, unlike a merge's discarded self-loop), so there is
    no discard branch. ``collision_exists`` (an edge is already committed at the new id) is resolved
    by the caller's read to keep this function store-free.
    """
    new_id = relation_edge_id(new_subject_id, new_predicate, new_object_id)
    if new_id == old_edge.id:
        return RelationRekeyPlan(kind="noop", new_edge=None)
    new_edge = old_edge.model_copy(
        update={
            "id": new_id,
            "type": new_predicate,
            "subject_id": new_subject_id,
            "object_id": new_object_id,
            "edge_uid": edge_uid,
        }
    )
    return RelationRekeyPlan(kind="fold" if collision_exists else "repoint", new_edge=new_edge)
