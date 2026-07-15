"""Pure planning for a graph-wide predicate rename (Graph-quality S6a-2, DM-NN-4).

Renaming a predicate P→Q re-keys **every** edge bearing P: a predicate *is* the Neo4j relationship
type, and the edge id is `uuid5(subject, predicate, object)` (`domain/candidates.py`), so a new
predicate is a *new* edge, not an in-place update. The per-edge atom already ships as
`plan_relation_rekey` (S5b) — delete-old + create-new, preserve the `edge_uid` handle (§4, INV-10),
fold a MERGE-collision. This module applies that atom **graph-wide in one plan**: the new weight is
*scale*, not mechanism.

Pure — no store, no I/O. The caller (`EntityEditService.rename_predicate`) reads every edge,
resolves each bearing edge's handle (its own, or a freshly-minted one for a legacy handle-less edge
— minting is impure, so it stays in the service), passes them here, then drives the writes from the
returned steps and records one grouped reversible `graph_edits` operation (INV-3).

Correctness note (why a single pre-rename snapshot suffices to classify every step): two *distinct*
edges bearing P differ in (subject, object), so their renamed ids `uuid5(s, Q, o)` also differ — a
rename can never make two bearing edges collide *with each other*. The only folds are onto edges
that already bore Q *before* the rename, present in the snapshot. So `collision_exists` for each
bearing edge is decided purely by membership in the pre-rename id set.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.graph import GraphRelation
from story_forge.domain.relation_rekey import plan_relation_rekey


@dataclass(frozen=True)
class PredicateRenameStep:
    """One edge's re-key within the graph-wide rename. ``kind`` is ``repoint`` (a genuinely new Q
    edge) or ``fold`` (MERGE-collision onto a pre-existing Q edge); ``noop`` steps are dropped (they
    only arise when from == to, i.e. no rename at all), so ``new_edge`` is never ``None``."""

    old_edge: GraphRelation
    kind: Literal["repoint", "fold"]
    new_edge: GraphRelation


@dataclass(frozen=True)
class PredicateRenamePlan:
    """The store-free plan for a graph-wide predicate rename.

    - ``steps`` — one per edge that actually re-keys (bearing edges; empty when from == to).
    - ``renamed_count`` — steps that repoint to a genuinely new Q edge.
    - ``folded_count`` — steps that fold onto a pre-existing Q edge (the reported side-effect,
      "merged N edges", never the goal). ``renamed_count + folded_count`` = edges bearing P.
    """

    steps: tuple[PredicateRenameStep, ...]
    renamed_count: int
    folded_count: int


def plan_predicate_rename(
    edges: Sequence[GraphRelation],
    handles: Mapping[UUID, UUID],
    *,
    from_predicate: str,
    to_predicate: str,
) -> PredicateRenamePlan:
    """Plan a graph-wide rename of every edge bearing ``from_predicate`` to ``to_predicate``.

    ``handles`` maps each bearing edge's id to the ``edge_uid`` to carry (the service resolves it
    up-front). ``edges`` is every current edge in the project; its ids form the pre-rename snapshot
    used to classify folds. Pure — no store, no side effects.

    A blank ``to_predicate`` is rejected here so the guard fires even when zero edges bear P (in
    which case no per-edge `plan_relation_rekey` would run to catch it) — the domain-level non-empty
    rule a predicate gets for free on `GraphRelation` construction.
    """
    if not to_predicate.strip():
        raise ValueError("relation predicate must be a non-empty string")

    existing_ids = {edge.id for edge in edges}
    steps: list[PredicateRenameStep] = []
    renamed = 0
    folded = 0
    for edge in edges:
        if edge.type != from_predicate:
            continue
        new_id = relation_edge_id(edge.subject_id, to_predicate, edge.object_id)
        plan = plan_relation_rekey(
            edge,
            new_predicate=to_predicate,
            new_subject_id=edge.subject_id,
            new_object_id=edge.object_id,
            edge_uid=handles[edge.id],
            collision_exists=new_id in existing_ids,
        )
        if plan.kind == "noop" or plan.new_edge is None:
            continue
        steps.append(PredicateRenameStep(old_edge=edge, kind=plan.kind, new_edge=plan.new_edge))
        if plan.kind == "fold":
            folded += 1
        else:
            renamed += 1

    return PredicateRenamePlan(steps=tuple(steps), renamed_count=renamed, folded_count=folded)
