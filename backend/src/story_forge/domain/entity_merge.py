"""Pure merge-consolidation for entity↔entity merge (M4.S3b, the first graph *re-point* slice).

Given a survivor `GraphEntity` A, an absorbed `GraphEntity` B, B's incident edges, and the
author's resolved property values, produce the consolidated survivor + a deterministic list of
re-point/fold/discard **steps** — or raise `EntityMergeInvalid`. Pure: no store, no I/O, so the
consolidation rules are unit-tested without a database. `EntityEditService.merge_entities`
(`agents/entity_edit.py`) drives the Neo4j/Postgres writes from this plan, then records the
grouped before-image evidence (DM-S3b-1, INV-3).

The resolved decisions this encodes:
- **Aliases union** (DM-S3b-2): A∪B aliases + B's canonical names become A's aliases (de-duped,
  order-preserving); A's own canonical names are never folded back in as aliases.
- **Properties resolved BY HAND** (DM-S3b-2): non-conflicting keys union; where both A and B set
  the *same* key to *different* values, the author must supply the value to keep
  (`resolved_properties`) or the merge is rejected — nothing is silently overwritten.
- **Edge re-point** (DM-S3b-3): every edge incident to B is re-pointed onto A. Because
  `relation_edge_id = uuid5(subject, predicate, object)` is content-addressed, re-pointing an
  endpoint *changes the id* → it is delete-old + create-new, not an in-place update. A re-pointed
  edge whose new id already exists on A **folds** (MERGE-collapse, multiplicity reported, not
  silently lost). An edge that becomes a self-loop after the swap (a B↔A edge, or a B↔B loop) is
  **dropped** as an artifact, consistent with the extraction path.

The fold-vs-repoint distinction depends on A's *live* graph, so it is kept pure by passing in the
survivor's existing edge ids (`existing_target_edge_ids`); the service supplies them from a
neighbourhood read of A.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence, Set
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.graph import GraphEntity, GraphRelation


class EntityMergeInvalid(ValueError):
    """A merge that cannot proceed (→409/400): a self-merge (B is A), or a property conflict the
    author left unresolved. Distinct from FastAPI's request-shape 422 — the request is well-formed,
    the merge itself is semantically invalid."""


@dataclass(frozen=True)
class PropertyConflict:
    """One property key both A and B set to *different* values — the author must pick which to
    keep (DM-S3b-2). Non-conflicting keys (only one side sets it, or both agree) union silently."""

    key: str
    survivor_value: object
    absorbed_value: object


@dataclass(frozen=True)
class EdgeRepoint:
    """One incident edge of B moved onto A. `old_edge` is the edge as it exists today; `new_edge`
    is the same fact with B's endpoint(s) swapped to A and the content-addressed id recomputed.
    `direction` names which endpoint was B (so the orchestration/undo know what it swapped)."""

    old_edge: GraphRelation
    new_edge: GraphRelation
    direction: Literal["subject", "object", "both"]


@dataclass(frozen=True)
class MergeStep:
    """One edge mutation in the plan. `kind`:
    - ``repoint`` — delete the old edge, create the new one on A (no collision);
    - ``fold`` — same, but A already has the new edge id, so the create MERGE-collapses
      (multiplicity lost — reported via `MergePlan.folded_count`);
    - ``discard_self_loop`` — the edge became A↔A after the swap; delete it, create nothing.
    """

    kind: Literal["repoint", "fold", "discard_self_loop"]
    repoint: EdgeRepoint


@dataclass(frozen=True)
class MergePlan:
    """The deterministic, store-free output: the consolidated survivor + the ordered edge steps +
    the counts the merge summary reports back to the author (DM-S3b-3)."""

    survivor: GraphEntity
    steps: tuple[MergeStep, ...]
    repointed_count: int
    folded_count: int
    self_loops_dropped: int


def detect_property_conflicts(
    survivor: GraphEntity, absorbed: GraphEntity
) -> list[PropertyConflict]:
    """The property keys both entities set to *different* values (DM-S3b-2). A key only one side
    sets, or both set equally, is not a conflict — it unions automatically at consolidation. The
    merge endpoint calls this to surface the conflicts the author must resolve before committing."""
    return [
        PropertyConflict(key=key, survivor_value=survivor.properties[key], absorbed_value=value)
        for key, value in absorbed.properties.items()
        if key in survivor.properties and survivor.properties[key] != value
    ]


def _consolidate_aliases(survivor: GraphEntity, absorbed: GraphEntity) -> list[str]:
    """A's aliases, then B's aliases, then B's canonical names — de-duplicated, order-preserving,
    excluding A's own canonical names (a survivor never aliases itself) and `None`."""
    own_canonical = {
        name for name in (survivor.canonical_name_pl, survivor.canonical_name_en) if name
    }
    candidates = [
        *survivor.aliases,
        *absorbed.aliases,
        absorbed.canonical_name_pl,
        absorbed.canonical_name_en,
    ]
    result: list[str] = []
    seen: set[str] = set()
    for name in candidates:
        if name is None or name in own_canonical or name in seen:
            continue
        seen.add(name)
        result.append(name)
    return result


def _consolidate_properties(
    survivor: GraphEntity,
    absorbed: GraphEntity,
    resolved: Mapping[str, object],
    conflict_keys: Set[str],
) -> dict[str, object]:
    """Union non-conflicting keys (B folds under A, survivor wins a tie); for each *detected
    conflict* the author's `resolved` value wins. Only conflict keys are taken from `resolved` —
    an extraneous key there is ignored, so a merge never silently injects a property neither entity
    had (a merge resolves conflicts; it is not an arbitrary property edit)."""
    merged: dict[str, object] = {**absorbed.properties, **survivor.properties}
    for key in conflict_keys:
        merged[key] = resolved[key]
    return merged


def plan_merge(
    survivor: GraphEntity,
    absorbed: GraphEntity,
    incident_edges: Sequence[GraphRelation],
    *,
    resolved_properties: Mapping[str, object],
    existing_target_edge_ids: Set[UUID],
) -> MergePlan:
    """Plan the merge of `absorbed` (B) into `survivor` (A). Pure — no store, no side effects.

    Raises `EntityMergeInvalid` on a self-merge (B is A) or a property conflict missing from
    `resolved_properties`. `incident_edges` are B's edges (both directions); a fold is detected
    against `existing_target_edge_ids` (A's current edge ids). Steps are ordered by the old edge id
    for stable, replayable output.
    """
    if survivor.id == absorbed.id:
        raise EntityMergeInvalid("cannot merge an entity into itself")

    conflicts = detect_property_conflicts(survivor, absorbed)
    unresolved = [c.key for c in conflicts if c.key not in resolved_properties]
    if unresolved:
        raise EntityMergeInvalid(f"unresolved property conflicts: {sorted(unresolved)}")

    consolidated = survivor.model_copy(
        update={
            "aliases": _consolidate_aliases(survivor, absorbed),
            "properties": _consolidate_properties(
                survivor, absorbed, resolved_properties, {c.key for c in conflicts}
            ),
        }
    )

    steps: list[MergeStep] = []
    repointed = folded = self_loops = 0
    for edge in sorted(incident_edges, key=lambda e: e.id):
        sub_is_b = edge.subject_id == absorbed.id
        obj_is_b = edge.object_id == absorbed.id
        if not (sub_is_b or obj_is_b):
            continue  # defensive: not actually incident to B — leave it untouched
        new_subject = survivor.id if sub_is_b else edge.subject_id
        new_object = survivor.id if obj_is_b else edge.object_id
        direction: Literal["subject", "object", "both"] = (
            "both" if sub_is_b and obj_is_b else "subject" if sub_is_b else "object"
        )
        new_id = relation_edge_id(new_subject, edge.type, new_object)
        new_edge = edge.model_copy(
            update={"id": new_id, "subject_id": new_subject, "object_id": new_object}
        )
        repoint = EdgeRepoint(old_edge=edge, new_edge=new_edge, direction=direction)

        if new_subject == new_object:
            self_loops += 1
            steps.append(MergeStep(kind="discard_self_loop", repoint=repoint))
        elif new_id in existing_target_edge_ids:
            folded += 1
            steps.append(MergeStep(kind="fold", repoint=repoint))
        else:
            repointed += 1
            steps.append(MergeStep(kind="repoint", repoint=repoint))

    return MergePlan(
        survivor=consolidated,
        steps=tuple(steps),
        repointed_count=repointed,
        folded_count=folded,
        self_loops_dropped=self_loops,
    )
