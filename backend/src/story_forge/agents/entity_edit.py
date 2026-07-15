"""EntityEditService — the human edit-handler for committed graph state (M4.S3a, DM-S3a-1/2/3).

The first slice that *edits* already-committed graph objects. It is a new **human-reached** graph
writer alongside the accept handler (`CandidateReviewService`, nodes) and the decide handler
(`RelationReviewService`, staged-relation edges) — the reason INV-9's wording broadens from
"exactly two writers" to "only human-reached handlers — accept, decide, edit" (ADR 0006). The
guarded property is unchanged: no *automated* stage writes the graph; every writer is reached only
from an explicit human action.

Per the owner's build-time call (DM-S3a-3, the synthetic-staged-row path didn't compose — the
decide path resolves endpoints by surface-name-within-a-paragraph, which a hand-picked edge has
neither of), manual relation add/remove write Neo4j **directly** here (`create_relation` reused for
add, `delete_relation` for remove), so the edge-writer set grows under the same INV-9 rewording.

Write order mirrors the accept/decide services — **graph mutation first, evidence row last**
(DM-S3a-2, INV-3). A crash between them leaves the edit applied but unlogged; a retry of the same
edit re-reads the now-updated state, diffs empty, and is a clean no-op — so nothing is double-
applied (the narrow cost is a missed audit row in that window, accepted at PoC for one local author,
last-write-wins — DM-S3a-6).
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol
from uuid import UUID, uuid4, uuid5

from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.entity_edits import (
    EntityEditInvalid,
    EntityEditPatch,
    apply_entity_edit,
    diff_entity,
)
from story_forge.domain.entity_merge import MergeStep, plan_merge
from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.graph_edit import GraphEdit
from story_forge.domain.graph_undo import (
    DeleteEntity,
    DriftCheck,
    InverseAction,
    ReassignMentions,
    RecreateEntity,
    RecreateRelation,
    RemoveMention,
    RemoveRelation,
    RemoveSuppression,
    RestoreEntityFields,
    RestoreMentions,
    RestoreMentionSpan,
    fields_match,
    invert_operation,
)
from story_forge.domain.models import EntityMention, MentionSuppression
from story_forge.domain.predicate_rename import plan_predicate_rename
from story_forge.domain.relation_rekey import plan_relation_rekey

# A manually-asserted edge carries full confidence (a human stated it, not a model).
_MANUAL_CONFIDENCE = 1.0

# Fixed namespace so a merge's `operation_id` and its grouped row ids are a deterministic function
# of the (absorbed, survivor) pair — the basis of the crash-retry idempotency contract (a re-run
# re-derives the same ids, so `ON CONFLICT (id) DO NOTHING` never doubles the evidence). Distinct
# from the accept/relation namespaces in `domain/candidates.py` so the id spaces never collide.
_OP_NS = UUID("a5f0c0de-0000-4000-8000-000000000004")

# Human-readable fallbacks for an S3a singleton edit (no grouped `description`) when the undo
# affordance previews what it will reverse (DM-S3b-1).
_SINGLETON_LABELS = {
    "edit_fields": "an entity edit",
    "add_relation": "a relation add",
    "remove_relation": "a relation removal",
    "add_mention": "a manual tag",
    "suppress_span": "a hidden highlight",
    "edit_mention_span": "a boundary change",
}


class EntityGraphEditor(Protocol):
    """The committed-graph mutators + reads the edit path needs (a `Neo4jRepo`)."""

    async def get_entity(self, entity_id: UUID) -> GraphEntity | None: ...
    async def create_entity(self, entity: GraphEntity) -> None: ...
    async def update_entity(self, entity: GraphEntity) -> None: ...
    async def relabel_entity_type(
        self, project_id: UUID, from_type: str, to_type: str
    ) -> list[UUID]: ...
    async def get_relation(self, project_id: UUID, edge_id: UUID) -> GraphRelation | None: ...
    async def get_relations(self, project_id: UUID) -> list[GraphRelation]: ...
    async def create_relation(self, relation: GraphRelation) -> None: ...
    async def delete_relation(self, edge_id: UUID) -> None: ...
    async def get_neighbourhood(
        self, entity_id: UUID
    ) -> list[tuple[GraphRelation, GraphEntity]]: ...
    async def delete_entity(self, entity_id: UUID) -> None: ...


class EditEvidenceRepo(Protocol):
    """The before→after edit log + the undo read path (a `PostgresEditStore`)."""

    async def record_edit(self, edit: GraphEdit) -> None: ...
    async def record_operation(self, edits: Sequence[GraphEdit]) -> None: ...
    async def latest_live_operation(self, project_id: UUID) -> list[GraphEdit] | None: ...
    async def mark_operation_undone(self, op_key: UUID, *, undone_at: datetime) -> None: ...
    async def is_operation_undone(self, operation_id: UUID) -> bool: ...


class MentionRepo(Protocol):
    """The cross-store mention re-point/snapshot a merge, delete, and undo need (a
    `PostgresMentionStore`), plus the manual tag/un-tag/boundary mutators (M4.S3c)."""

    async def repoint_mentions(self, from_entity_id: UUID, to_entity_id: UUID) -> list[UUID]: ...
    async def reassign_mentions(self, mention_ids: list[UUID], to_entity_id: UUID) -> None: ...
    async def mentions_for_entity(self, entity_id: UUID) -> list[EntityMention]: ...
    async def delete_mentions_for_entity(self, entity_id: UUID) -> None: ...
    async def restore_mentions(self, mentions: list[EntityMention]) -> None: ...
    # M4.S3c manual-correction mutators:
    async def add_mention(self, mention: EntityMention) -> None: ...
    async def get_mention(self, mention_id: UUID) -> EntityMention | None: ...
    async def update_mention_span(
        self, mention_id: UUID, span_start: int, span_end: int
    ) -> None: ...
    async def delete_mention(self, mention_id: UUID) -> None: ...
    async def add_suppression(self, suppression: MentionSuppression) -> None: ...
    async def delete_suppression(self, suppression_id: UUID) -> None: ...


class EntityNotFound(LookupError):
    """No such entity in this project (→404). Covers a stale-tab edit of a node that was merged or
    removed, and the tenancy guard (an entity belonging to another project)."""


class RelationEdgeNotFound(LookupError):
    """No such committed edge in this project (→404) — e.g. a double-remove from two tabs."""


class SelfMergeError(ValueError):
    """A merge whose absorbed and survivor are the same entity (→409) — a no-op that would delete
    the only node. Guarded before any read."""


class MentionNotFound(LookupError):
    """No such mention (→404) — e.g. a change-boundaries on a manual span removed in another tab."""


class NothingToUndo(LookupError):
    """The undo stack is empty for this project (→404) — no live operation to reverse."""


class UndoConflict(RuntimeError):
    """The graph drifted since the operation was recorded (→409): the entity it touched was edited,
    deleted, or re-created in the meantime, so undoing would clobber that newer change (a lost
    update in reverse, ADR 0007 / DM-S3b "but what if" case 5). Refuse rather than silently
    overwrite; the message names what drifted."""


@dataclass(frozen=True)
class RelationEditResult:
    """Outcome of an add — the edge id and whether the MERGE folded onto an edge that already
    existed (the re-predicate / duplicate-add collision the UI warns on, DM-S3a-3)."""

    edge_id: UUID
    merged_into_existing: bool


@dataclass(frozen=True)
class PredicateRenameSummary:
    """Outcome of a graph-wide predicate rename (S6a-2, DM-NN-4) — the counts the normalise-names
    list reports: edges re-keyed to a genuinely new Q edge (`renamed_count`) and edges folded onto a
    pre-existing Q edge (`folded_count`, "merged N edges" — reported, never the goal)."""

    renamed_count: int
    folded_count: int


@dataclass(frozen=True)
class TypeRelabelSummary:
    """Outcome of a graph-wide entity-type relabel (S6a-2, DM-NN-5) — the number of nodes whose
    `type` property was re-set (no fold: nodes sharing a type stay independent)."""

    relabelled_count: int


@dataclass(frozen=True)
class MergeSummary:
    """Outcome of a merge — the survivor's id + the counts the side panel reports to the author
    (re-pointed/folded edges, dropped self-loops, mentions moved; DM-S3b-3)."""

    survivor_entity_id: UUID
    repointed_count: int
    folded_count: int
    self_loops_dropped: int
    mentions_repointed: int


@dataclass(frozen=True)
class DeleteSummary:
    """Outcome of a whole-entity delete — the id removed + the counts the panel reports (DM-S3b-5),
    plus the human-readable `description` the undo affordance will preview."""

    deleted_entity_id: UUID
    edges_removed: int
    mentions_removed: int
    description: str


@dataclass(frozen=True)
class UndoResult:
    """Outcome of an undo (or, with `preview_only`, what *would* be reversed). `applied` is False in
    preview mode. `description` is the human-readable label of the operation at the top of the
    stack (DM-S3b-1, see-what-I-undo)."""

    description: str
    op_kind: str
    applied: bool


def _display_name(entity: GraphEntity) -> str:
    """A human label for the undo description (DM-S3b-1, see-what-I-undo): a canonical name, else
    the first alias, else the id — never blank."""
    return (
        entity.canonical_name_pl
        or entity.canonical_name_en
        or (entity.aliases[0] if entity.aliases else None)
        or str(entity.id)
    )


def _retarget_description(old: GraphRelation, new: GraphRelation) -> str:
    """The human label an edge re-key's undo affordance previews (DM-S3b-1, see-what-I-undo)."""
    if old.type != new.type:
        return f"re-predicated an edge '{old.type}' → '{new.type}'"
    return f"re-targeted a '{old.type}' edge"


def _rename_predicate_description(from_predicate: str, to_predicate: str, folded: int) -> str:
    """The human label a graph-wide predicate rename's undo affordance previews (DM-S3b-1)."""
    label = f"renamed predicate '{from_predicate}' → '{to_predicate}'"
    if folded:
        label += f" (merged {folded} edge{'s' if folded != 1 else ''})"
    return label


def _relabel_type_description(from_type: str, to_type: str) -> str:
    """The human label a graph-wide entity-type relabel's undo affordance previews (DM-S3b-1)."""
    return f"relabelled type '{from_type}' → '{to_type}'"


def _mention_payload(
    paragraph_id: UUID, entity_id: UUID, span_start: int, span_end: int
) -> dict[str, object]:
    """The `after` image of an `add_mention` row (M4.S3c) — for the audit trail / flywheel; the
    inverse (`RemoveMention`) only needs the row's `target_id`, so this is reference data."""
    return {
        "paragraph_id": str(paragraph_id),
        "entity_id": str(entity_id),
        "span_start": span_start,
        "span_end": span_end,
    }


def _suppression_payload(
    paragraph_id: UUID, entity_id: UUID | None, span_start: int, span_end: int
) -> dict[str, object]:
    """The `after` image of a `suppress_span` row (M4.S3c). `entity_id` None = "not an entity"."""
    return {
        "paragraph_id": str(paragraph_id),
        "entity_id": None if entity_id is None else str(entity_id),
        "span_start": span_start,
        "span_end": span_end,
    }


def _mention_id(paragraph_id: UUID, entity_id: UUID, span_start: int, span_end: int) -> UUID:
    """Deterministic manual-mention id so re-tagging the same (paragraph, entity, span) is
    idempotent (`ON CONFLICT (id) DO NOTHING`). Single source of the formula: every tag path
    (tag-existing, tag-new, atomic re-assign, materialize-boundary) derives the id here, so the
    producer (the insert) and any consumer (an undo `RemoveMention` by id) can never drift."""
    return uuid5(_OP_NS, f"mention:{paragraph_id}:{entity_id}:{span_start}:{span_end}")


def _suppression_id(
    paragraph_id: UUID, span_start: int, span_end: int, entity_id: UUID | None
) -> UUID:
    """Deterministic suppression id so a re-suppress of the same (paragraph, span, entity) is
    idempotent (`ON CONFLICT (id) DO NOTHING`). `entity_id` None ("not an entity") keys on 'all'."""
    return uuid5(_OP_NS, f"suppress:{paragraph_id}:{span_start}:{span_end}:{entity_id or 'all'}")


def _op_seed(base: str, generation: int) -> str:
    """The `uuid5` seed for a grouped operation id. Generation 0 keeps the base seed (be1's exact
    merge id for the common first-time case); re-doing the *same* operation on the *same* targets
    after an undo (generation ≥ 1) suffixes it so the new evidence isn't dropped by `ON CONFLICT
    (id) DO NOTHING` (ADR 0007 — applies to both re-merge and re-delete of a pair/entity)."""
    return base if generation == 0 else f"{base}:{generation}"


class EntityEditService:
    """Edits a committed entity's fields, adds/removes relations, merges/deletes entities, and tags/
    un-tags/re-bounds occurrences in the reader — all under the human gate (M4.S3a edit + S3b
    merge/delete + S3c manual correction). INV-9's "edit" handler keeps *growing operations* rather
    than minting writer classes (broaden-don't-mint, ADR 0006): S3c's `tag_new_entity` is a new
    human-reached *entity* writer and the manual-mention mutators write the mention layer — every
    one reached only from an explicit human action, so no *automated* stage writes the graph."""

    def __init__(
        self,
        graph: EntityGraphEditor,
        evidence: EditEvidenceRepo,
        mentions: MentionRepo,
    ) -> None:
        self._graph = graph
        self._evidence = evidence
        self._mentions = mentions

    async def edit_entity(
        self, project_id: UUID, entity_id: UUID, patch: EntityEditPatch
    ) -> GraphEntity:
        """Apply a validated field patch to a committed entity (DM-S3a-1).

        Re-reads first (the TOCTOU/tenancy guard → `EntityNotFound`), validates + merges the patch
        (`apply_entity_edit` raises `EntityEditInvalid` on a blank name/type), then — only if the
        edit changes something — writes the node and records the before→after evidence.
        """
        entity = await self._graph.get_entity(entity_id)
        if entity is None or entity.project_id != project_id:
            raise EntityNotFound(str(entity_id))

        next_entity = apply_entity_edit(entity, patch)
        changes = diff_entity(entity, next_entity)
        if not changes:
            return entity  # no-op: nothing to write or log

        await self._graph.update_entity(next_entity)
        await self._evidence.record_edit(
            GraphEdit(
                target_id=entity_id,
                target_kind="entity",
                op="edit_fields",
                before={change.field: change.before for change in changes},
                after={change.field: change.after for change in changes},
                project_id=project_id,
            )
        )
        return next_entity

    async def add_relation(
        self, project_id: UUID, subject_id: UUID, predicate: str, object_id: UUID
    ) -> RelationEditResult:
        """Add a relation between two accepted entities (DM-S3a-3, direct edge-writer).

        Both endpoints must exist in the project (→`EntityNotFound`). A manual **self-loop**
        (subject == object) is allowed — intentional, unlike the extraction path's dropped merge
        artifacts. The edge id is `uuid5` of the (subject, predicate, object) triple, so a duplicate
        add MERGEs onto the existing edge; that collision is surfaced (`merged_into_existing`)
        rather than erroring.
        """
        await self._require_entity(project_id, subject_id)
        await self._require_entity(project_id, object_id)

        edge_id = relation_edge_id(subject_id, predicate, object_id)
        existing = await self._graph.get_relation(project_id, edge_id)
        await self._graph.create_relation(
            GraphRelation(
                id=edge_id,
                type=predicate,
                subject_id=subject_id,
                object_id=object_id,
                confidence=_MANUAL_CONFIDENCE,
                # Mint the §4 handle forward on every edge write (ADR 0011). On a MERGE-fold onto an
                # edge that already exists, `create_relation`'s `ON CREATE SET`-only coalesce drops
                # this fresh handle and keeps the existing one (DM-S5-3).
                edge_uid=uuid4(),
            )
        )
        await self._evidence.record_edit(
            GraphEdit(
                target_id=edge_id,
                target_kind="relation",
                op="add_relation",
                after={
                    "subject_id": str(subject_id),
                    "predicate": predicate,
                    "object_id": str(object_id),
                    # whether the add MERGE-folded onto an edge that already existed: if so the add
                    # created nothing, so undo must *not* delete that pre-existing edge (DM-S3a-3).
                    "merged_into_existing": existing is not None,
                },
                project_id=project_id,
            )
        )
        return RelationEditResult(edge_id=edge_id, merged_into_existing=existing is not None)

    async def remove_relation(self, project_id: UUID, edge_id: UUID) -> None:
        """Remove a committed edge (DM-S3a-3). 404s if the edge isn't in the project (a stale
        double-remove), records the before-image for undo, then deletes."""
        existing = await self._graph.get_relation(project_id, edge_id)
        if existing is None:
            raise RelationEdgeNotFound(str(edge_id))

        await self._graph.delete_relation(edge_id)
        await self._evidence.record_edit(
            GraphEdit(
                target_id=edge_id,
                target_kind="relation",
                op="remove_relation",
                # full edge snapshot (not just subject/predicate/object) so undo restores the exact
                # edge — its `confidence`/`properties` too, not a manual-confidence approximation.
                before=existing.model_dump(mode="json"),
                project_id=project_id,
            )
        )

    async def retarget_relation(
        self,
        project_id: UUID,
        edge_id: UUID,
        *,
        predicate: str | None = None,
        subject_id: UUID | None = None,
        object_id: UUID | None = None,
    ) -> RelationEditResult:
        """Atomically edit-predicate and/or re-target a committed edge (DM-S5-2), **preserving the
        §4 surrogate handle across the content-id re-key** (DM-S5-3, INV-10).

        The content id is `uuid5` of the (subject, predicate, object) triple, so any change re-keys
        the edge — done here as delete-old + create-new **server-side as one grouped reversible
        operation**, never the client-side remove+add (which splits the edit into two undo steps,
        opens a partial-failure window, and cannot preserve the handle). The old edge's `edge_uid`
        (or a freshly-minted one for a legacy handle-less edge) rides the new edge; a re-key that
        lands on an edge already between the new pair **folds** — the surviving edge keeps its own
        handle, the folded edge's rides the before-image so undo un-folds (DM-S5-3 survivor rule). A
        no-op (nothing changed) is idempotent: the unchanged id back, nothing written.

        404s a stale edge (`RelationEdgeNotFound`) and a re-target onto a missing endpoint
        (`EntityNotFound`). The re-key writes the graph before the evidence (INV-3), with two crash
        windows — both the accepted single-author LWW posture (DM-S3a-6 / DM-S5-6): **create-new
        before delete-old** means a store failure *mid*-re-key leaves a recoverable duplicate (both
        edges), never a missing edge, and a retry converges; but a failure *after* both graph writes
        and before the evidence row leaves the re-key **applied yet unlogged** — invisible to undo,
        and a retry 404s on the now-deleted old edge. The re-key reuses `create_relation` /
        `delete_relation` — no new graph-write symbol, so INV-9's grep-guard enumeration is
        unchanged; only the reachable *path* grows.
        """
        old = await self._graph.get_relation(project_id, edge_id)
        if old is None:
            raise RelationEdgeNotFound(str(edge_id))

        new_predicate = predicate if predicate is not None else old.type
        new_subject_id = subject_id if subject_id is not None else old.subject_id
        new_object_id = object_id if object_id is not None else old.object_id
        # Only a *supplied* (changed) endpoint needs an existence check; an omitted one keeps the
        # old edge's endpoint, which `get_relation` already confirmed present + in-project — so a
        # re-predicate-only edit does not re-read both endpoints redundantly.
        if subject_id is not None:
            await self._require_entity(project_id, new_subject_id)
        if object_id is not None:
            await self._require_entity(project_id, new_object_id)

        # Preserve the old edge's handle across the re-key; mint one forward if the old edge is a
        # legacy handle-less edge (mint-forward, no backfill — DM-S5-3).
        handle = old.edge_uid or uuid4()
        new_edge_id = relation_edge_id(new_subject_id, new_predicate, new_object_id)
        collision = (
            None
            if new_edge_id == edge_id
            else await self._graph.get_relation(project_id, new_edge_id)
        )
        plan = plan_relation_rekey(
            old,
            new_predicate=new_predicate,
            new_subject_id=new_subject_id,
            new_object_id=new_object_id,
            edge_uid=handle,
            collision_exists=collision is not None,
        )
        if plan.kind == "noop" or plan.new_edge is None:
            return RelationEditResult(edge_id=edge_id, merged_into_existing=False)

        # Graph first: **create the new edge before deleting the old** — so a store failure between
        # the two writes leaves a recoverable duplicate (both edges present), never a missing edge
        # (the client-side remove+add's data-loss window, closed server-side — DM-S5-2). On a fold
        # the create MERGEs onto the pre-existing survivor edge, whose own handle wins (the
        # ON-CREATE coalesce) — the passed handle is dropped, the survivor rule.
        await self._graph.create_relation(plan.new_edge)
        await self._graph.delete_relation(old.id)

        # Evidence last: one grouped reversible op reusing the merge writer's per-edge op strings
        # (`repoint_relation` / `fold_relation`), so `graph_undo.invert_operation` already reverses
        # it — repoint = remove the new edge + recreate the old; fold = recreate the old only (the
        # survivor was never created here). The before-image carries `edge_uid`, so undo restores
        # the edge handle-and-all (INV-3 widened by the handle, DM-S5-3).
        base_seed = f"retarget:{old.id}:{plan.new_edge.id}"
        generation = await self._next_generation(base_seed)
        await self._evidence.record_operation(
            self._grouped(
                project_id,
                op_kind="retarget",
                description=_retarget_description(old, plan.new_edge),
                base_seed=base_seed,
                generation=generation,
                specs=[
                    {
                        "target_id": old.id,
                        "target_kind": "relation",
                        "op": f"{plan.kind}_relation",
                        "before": old.model_dump(mode="json"),
                        "after": plan.new_edge.model_dump(mode="json"),
                    }
                ],
            )
        )
        return RelationEditResult(
            edge_id=plan.new_edge.id, merged_into_existing=plan.kind == "fold"
        )

    async def rename_predicate(
        self, project_id: UUID, from_predicate: str, to_predicate: str
    ) -> PredicateRenameSummary:
        """Rename a predicate graph-wide P→Q as one grouped reversible operation (S6a-2, DM-NN-4).

        The graph-wide generalisation of `retarget_relation`: re-key **every** edge bearing P,
        preserving each `edge_uid` (INV-10) and folding any edge whose renamed id already exists
        onto that survivor (reported via `folded_count`, never the goal). It reuses
        `plan_relation_rekey` per bearing edge (via the pure `plan_predicate_rename`) and the same
        `repoint_relation` / `fold_relation` evidence op-strings, so `graph_undo.invert_operation`
        reverses the whole N-edge operation with **no new inverter branch**, and it reuses
        `create_relation` / `delete_relation` — **no new graph-write symbol, INV-9's grep-guard
        enumeration unchanged** (only the reachable *path* grows; S6 is the graph-wide consumer
        INV-10 anticipated).

        Per edge the graph is written **create-new before delete-old** (a store failure mid-op
        leaves a recoverable duplicate, never a missing edge — the accepted single-author LWW
        window, DM-S3a-6, now spanning N edges; a retry converges since re-keying an already-Q edge
        is a no-op), and the grouped before-image is recorded **atomically last** (INV-3), as every
        grouped op does (merge, delete). That last step widens one accepted window: a store failure
        *after* some edges re-keyed but *before* `record_operation` leaves those re-keys applied yet
        **unlogged** — invisible to undo; a retry re-keys and logs only the still-P edges, so the
        graph converges to Q but the undo history does not cover the first batch. This is the same
        evidence-last posture as the merge/delete fan-out, at larger N — accepted under the
        single-author LWW window (the proposal's "name the wider window", DM-NN-4), not eliminated.
        A rename with no bearing edges (or from == to) writes nothing (planner guards a blank).
        """
        edges = await self._graph.get_relations(project_id)
        # Resolve each bearing edge's handle up-front (mint-forward for a legacy handle-less edge —
        # minting is impure, so it stays out of the pure planner; DM-S5-3).
        handles = {
            edge.id: (edge.edge_uid or uuid4()) for edge in edges if edge.type == from_predicate
        }
        plan = plan_predicate_rename(
            edges, handles, from_predicate=from_predicate, to_predicate=to_predicate
        )
        if not plan.steps:
            return PredicateRenameSummary(renamed_count=0, folded_count=0)

        specs: list[dict[str, object]] = []
        for step in plan.steps:
            # On a fold the create MERGEs onto the pre-existing survivor edge, whose own handle wins
            # (the ON-CREATE coalesce) — mirroring `retarget_relation`, per edge.
            await self._graph.create_relation(step.new_edge)
            await self._graph.delete_relation(step.old_edge.id)
            specs.append(
                {
                    "target_id": step.old_edge.id,
                    "target_kind": "relation",
                    "op": f"{step.kind}_relation",
                    "before": step.old_edge.model_dump(mode="json"),
                    "after": step.new_edge.model_dump(mode="json"),
                }
            )

        base_seed = f"rename_predicate:{project_id}:{from_predicate}:{to_predicate}"
        generation = await self._next_generation(base_seed)
        await self._evidence.record_operation(
            self._grouped(
                project_id,
                op_kind="rename_predicate",
                description=_rename_predicate_description(
                    from_predicate, to_predicate, plan.folded_count
                ),
                base_seed=base_seed,
                generation=generation,
                specs=specs,
            )
        )
        return PredicateRenameSummary(
            renamed_count=plan.renamed_count, folded_count=plan.folded_count
        )

    async def relabel_entity_type(
        self, project_id: UUID, from_type: str, to_type: str
    ) -> TypeRelabelSummary:
        """Relabel an entity type graph-wide A→B as one grouped reversible operation (S6a-2, NN-5).

        The type apply op — the **one net-new graph writer** in S6. A type is a node *property*
        (INV-4 free string), so this is a bulk `SET n.type` over the matched nodes: **no re-key, no
        `edge_uid` handle, no collapse** (two nodes sharing a type stay independent — the apply-fork
        asymmetry vs a predicate rename). The forward write is the new `relabel_entity_type` graph
        writer (INV-9 enumeration grows by one path); undo reuses the existing `edit_fields` inverse
        (`RestoreEntityFields` restores each node's `type` on the *current* node via `model_copy`,
        so other fields are untouched), so no new inverter branch. Every relabelled node had
        `from_type`, so its before-image is uniform (`{"type": from_type}`) and undo is exact.

        Undo's *drift guard* is single-valued (`invert_operation` keeps one `DriftCheck` — designed
        for a singleton `edit_fields`), so a bulk relabel's undo guards one representative node and
        restores the rest best-effort — the inverter's stated posture. Under single-author LIFO undo
        (DM-S3a-6) this is sound: to undo the relabel it must be the live top of the stack, so every
        op above it (any delete or re-edit of a relabelled node) is already undone, leaving all
        affected nodes present and at `to_type` — the representative node is neither absent
        (no false 409) nor drifted (no silent clobber). A stronger per-node guard
        would need `InversePlan` to carry N drift checks — a shared-machinery change out of scope
        here that would apply equally to the existing merge/delete grouped ops.

        A relabel matching no node writes nothing; from == to is skipped (nothing to normalise).
        """
        if not to_type.strip():
            raise ValueError("entity type must be a non-empty string")
        if from_type == to_type:
            return TypeRelabelSummary(relabelled_count=0)

        relabelled = await self._graph.relabel_entity_type(project_id, from_type, to_type)
        if not relabelled:
            return TypeRelabelSummary(relabelled_count=0)

        before = {"type": from_type}
        after = {"type": to_type}
        specs: list[dict[str, object]] = [
            {
                "target_id": entity_id,
                "target_kind": "entity",
                "op": "edit_fields",
                "before": before,
                "after": after,
            }
            for entity_id in relabelled
        ]
        base_seed = f"relabel_type:{project_id}:{from_type}:{to_type}"
        generation = await self._next_generation(base_seed)
        await self._evidence.record_operation(
            self._grouped(
                project_id,
                op_kind="relabel_type",
                description=_relabel_type_description(from_type, to_type),
                base_seed=base_seed,
                generation=generation,
                specs=specs,
            )
        )
        return TypeRelabelSummary(relabelled_count=len(relabelled))

    async def merge_entities(
        self,
        project_id: UUID,
        absorbed_id: UUID,
        target_id: UUID,
        resolved_properties: Mapping[str, object],
    ) -> MergeSummary:
        """Merge entity B (`absorbed_id`) into survivor A (`target_id`) under the human gate
        (M4.S3b, DM-S3b-1/2/3/4). One author action fans out into many writes across both stores;
        the whole thing is a *compensating transaction* — a grouped, reversible before-image is
        recorded so undo (be2) can reverse it as one unit.

        Order: fold A + re-point edges → re-point mentions → **delete B last** → evidence. Keeping
        B alive until the final graph write means a crash anywhere up to the delete is cleanly
        retryable (the retry re-reads B, finds the work already done, and finishes); the only
        post-completion window is the missing audit row (the merge is done, just unlogged — the
        accepted DM-S3a-6 last-write-wins posture; ADR 0007). Guards: self-merge
        (→`SelfMergeError`), either endpoint missing/cross-project (→`EntityNotFound`), an
        unresolved property conflict (→`EntityMergeInvalid`).
        """
        if absorbed_id == target_id:
            raise SelfMergeError(str(absorbed_id))

        absorbed = await self._require_entity(project_id, absorbed_id)
        survivor = await self._require_entity(project_id, target_id)

        # Dedupe by edge id: an undirected neighbourhood query returns a *self-loop twice* (one per
        # orientation), which would otherwise double-count it in the plan + emit a duplicate row.
        incident_by_id = {
            edge.id: edge for edge, _ in await self._graph.get_neighbourhood(absorbed_id)
        }
        incident_edges = list(incident_by_id.values())
        existing_target_edge_ids = {
            edge.id for edge, _ in await self._graph.get_neighbourhood(target_id)
        }
        plan = plan_merge(
            survivor,
            absorbed,
            incident_edges,
            resolved_properties=resolved_properties,
            existing_target_edge_ids=existing_target_edge_ids,
        )

        # Fold B into A and re-point each incident edge (delete-old + create-new, or delete-only
        # for a dropped self-loop). B's node is **kept alive** through these writes.
        await self._graph.update_entity(plan.survivor)
        for step in plan.steps:
            await self._graph.delete_relation(step.repoint.old_edge.id)
            if step.kind in ("repoint", "fold"):
                await self._graph.create_relation(step.repoint.new_edge)

        # Move B's mentions onto A **before** deleting B — so a mention never points at a node that
        # is already gone, and so a crash anywhere up to the delete is cleanly retryable: the retry
        # re-reads B (still present), finds its edges already moved + mentions already moved (a
        # no-op), and completes. The moved ids feed the before-image for undo.
        moved_mention_ids = await self._mentions.repoint_mentions(absorbed_id, target_id)

        # Delete B last (the only post-completion crash window is the missing audit row — the
        # accepted DM-S3a-6 posture, ADR 0007), then record the grouped, reversible before-image.
        await self._graph.delete_entity(absorbed_id)
        generation = await self._next_generation(f"merge:{absorbed_id}:{target_id}")
        await self._evidence.record_operation(
            self._merge_rows(
                project_id,
                survivor,
                absorbed,
                plan.survivor,
                plan.steps,
                moved_mention_ids,
                generation,
            )
        )

        return MergeSummary(
            survivor_entity_id=target_id,
            repointed_count=plan.repointed_count,
            folded_count=plan.folded_count,
            self_loops_dropped=plan.self_loops_dropped,
            mentions_repointed=len(moved_mention_ids),
        )

    async def delete_entity(self, project_id: UUID, entity_id: UUID) -> DeleteSummary:
        """Delete an accepted entity, its relations, and its text occurrences (M4.S3b-be2,
        DM-S3b-5; spec §3.4). A real `DETACH DELETE` (no soft tombstone — that would thread a
        read-filter through every screen), reversible from a **full snapshot** (node fields +
        incident edges + mentions) recorded as one grouped operation.

        Order mirrors merge — snapshot in memory, then mutate, then evidence-last. The snapshot is
        captured *before* any delete, so the recorded operation is complete; the only accepted crash
        window is a crash before the evidence write (the delete happened, just isn't undoable — the
        DM-S3a-6 last-write-wins posture, ADR 0007). 404s if the entity isn't in the project.

        DM-S3b-5 (owner default): an entity that is some earlier merge's *survivor* is deleted
        freely — the consistency check is pushed to that merge's undo, which a drift check refuses.
        """
        entity = await self._require_entity(project_id, entity_id)

        # Snapshot first (dedupe self-loops, which the undirected query returns twice).
        incident_edges = list(
            {edge.id: edge for edge, _ in await self._graph.get_neighbourhood(entity_id)}.values()
        )
        mentions = await self._mentions.mentions_for_entity(entity_id)
        description = f"deleted {_display_name(entity)}"

        # Mutate: drop mentions (Postgres) then DETACH DELETE the node + its edges (Neo4j).
        await self._mentions.delete_mentions_for_entity(entity_id)
        await self._graph.delete_entity(entity_id)

        # Evidence last (grouped, reversible). Generation guards a re-delete after an undo.
        generation = await self._next_generation(f"delete:{entity_id}")
        await self._evidence.record_operation(
            self._delete_rows(project_id, entity, incident_edges, mentions, description, generation)
        )
        return DeleteSummary(
            deleted_entity_id=entity_id,
            edges_removed=len(incident_edges),
            mentions_removed=len(mentions),
            description=description,
        )

    # --- M4.S3c: manual tag / un-tag / change-boundaries in the reader (spec §3.5) -----------
    #
    # The reader's first write family beyond entity/edge edits — it writes the **mention** layer.
    # Each correction is store-mutation-first, evidence-last (the DM-S3a-2/INV-3 order), reversible
    # via the same `graph_edits` undo (new op-kinds add_mention / create_entity_from_tag /
    # suppress_span / edit_mention_span; DM-S3c-5). Rejection ("not an entity"/"not this entity") is
    # *always* a suppression the resolver subtracts (DM-S3c-1 B), never a mention delete — one
    # rejection mechanism, uniform undo. Spans are validated against the paragraph text at the route
    # (`domain.highlights.validate_manual_span`); the service trusts in-bounds, scoped spans.

    async def tag_existing(
        self, project_id: UUID, paragraph_id: UUID, entity_id: UUID, span_start: int, span_end: int
    ) -> UUID:
        """Tag a span as an *existing* accepted entity — insert a manual mention with real offsets
        (DM-S3c-2). 404s if the entity isn't in the project. Idempotent by a deterministic id, so
        re-tagging the same span is an idempotent no-op. Returns the mention id."""
        await self._require_entity(project_id, entity_id)
        mention_id = _mention_id(paragraph_id, entity_id, span_start, span_end)
        await self._mentions.add_mention(
            EntityMention(
                id=mention_id,
                paragraph_id=paragraph_id,
                entity_id=entity_id,
                span_start=span_start,
                span_end=span_end,
                source="manual",
            )
        )
        await self._evidence.record_edit(
            GraphEdit(
                target_id=mention_id,
                target_kind="mention",
                op="add_mention",
                after=_mention_payload(paragraph_id, entity_id, span_start, span_end),
                project_id=project_id,
            )
        )
        return mention_id

    async def tag_new_entity(
        self,
        project_id: UUID,
        paragraph_id: UUID,
        name: str,
        type_: str,
        language: str,
        span_start: int,
        span_end: int,
    ) -> tuple[UUID, UUID]:
        """Tag a span as a *brand-new* accepted entity (DM-S3c-2) — mint a Neo4j node + its
        first manual mention as one grouped, reversible op. A **new human-reached entity writer**:
        INV-9's enumeration grows (broaden-don't-mint, exactly as S3a edit / S3b merge added writers
        reached only from an explicit human action; ADR 0006). The human *is* the §3.3 Stage-4 gate
        in person, so bypassing the cascade does not weaken INV-1 — it is its strongest form.

        Write order is **Neo4j-then-Postgres** (graph owns identity, OQ-1): a crash leaves an orphan
        node that simply doesn't highlight yet — the benign half — and a retry re-derives the same
        ids and completes. Returns `(entity_id, mention_id)`.
        """
        name = name.strip()
        type_ = type_.strip()
        if not name or not type_:
            raise EntityEditInvalid("a manual tag needs a non-empty name and type")
        entity_id = uuid5(_OP_NS, f"tagentity:{paragraph_id}:{span_start}:{span_end}:{name}")
        mention_id = _mention_id(paragraph_id, entity_id, span_start, span_end)
        # Provisional bilingual naming (the §3.2 / §10 q8 rule reused from the accept path): the
        # surface form fills the project-language slot, the peer stays null. A manual entity is
        # embedding-less at PoC (it isn't a candidate; the cascade matches candidates) — name it so
        # the NULL vector doesn't read as a bug.
        entity = GraphEntity(
            id=entity_id,
            type=type_,
            canonical_name_pl=name if language == "pl" else None,
            canonical_name_en=name if language != "pl" else None,
            first_seen_paragraph_id=paragraph_id,
            project_id=project_id,
        )
        await self._graph.create_entity(entity)
        await self._mentions.add_mention(
            EntityMention(
                id=mention_id,
                paragraph_id=paragraph_id,
                entity_id=entity_id,
                span_start=span_start,
                span_end=span_end,
                source="manual",
            )
        )
        generation = await self._next_generation(
            f"tagnew:{paragraph_id}:{span_start}:{span_end}:{name}"
        )
        # seq 0 = create node, seq 1 = add mention; undo replays highest-seq-first → remove the
        # mention, *then* delete the node (no dangling half).
        rows = self._grouped(
            project_id,
            op_kind="tag_new",
            description=f"tagged '{name}' as new {type_}",
            base_seed=f"tagnew:{paragraph_id}:{span_start}:{span_end}:{name}",
            generation=generation,
            specs=[
                {
                    "target_id": entity_id,
                    "target_kind": "entity",
                    "op": "create_entity_from_tag",
                    "after": entity.model_dump(mode="json"),
                },
                {
                    "target_id": mention_id,
                    "target_kind": "mention",
                    "op": "add_mention",
                    "after": _mention_payload(paragraph_id, entity_id, span_start, span_end),
                },
            ],
        )
        await self._evidence.record_operation(rows)
        return entity_id, mention_id

    async def suppress_occurrence(
        self,
        project_id: UUID,
        paragraph_id: UUID,
        span_start: int,
        span_end: int,
        entity_id: UUID | None,
    ) -> UUID:
        """Hide a highlight (DM-S3c-3). "not an entity" → `entity_id=None` (the reader clears every
        claimant at the span); "not this entity" detach → `entity_id` set (clears that one). Writes
        a suppression the resolver subtracts post-overlay. 404s if a named entity isn't in project.
        Returns the suppression id."""
        if entity_id is not None:
            await self._require_entity(project_id, entity_id)
        suppression_id = _suppression_id(paragraph_id, span_start, span_end, entity_id)
        await self._mentions.add_suppression(
            MentionSuppression(
                id=suppression_id,
                paragraph_id=paragraph_id,
                entity_id=entity_id,
                span_start=span_start,
                span_end=span_end,
            )
        )
        await self._evidence.record_edit(
            GraphEdit(
                target_id=suppression_id,
                target_kind="suppression",
                op="suppress_span",
                after=_suppression_payload(paragraph_id, entity_id, span_start, span_end),
                project_id=project_id,
            )
        )
        return suppression_id

    async def retag_occurrence(
        self,
        project_id: UUID,
        paragraph_id: UUID,
        span_start: int,
        span_end: int,
        from_entity_id: UUID,
        to_entity_id: UUID,
    ) -> tuple[UUID, UUID]:
        """ "not this entity" *with* re-assign — atomic (DM-S3c-3): suppress the wrong entity claim
        at the span AND tag the right entity there, as ONE grouped op so undo restores the original
        in a single step. 404s if either entity isn't in the project. Returns `(suppression_id,
        mention_id)`."""
        await self._require_entity(project_id, from_entity_id)
        await self._require_entity(project_id, to_entity_id)
        suppression_id = _suppression_id(paragraph_id, span_start, span_end, from_entity_id)
        mention_id = _mention_id(paragraph_id, to_entity_id, span_start, span_end)
        await self._mentions.add_suppression(
            MentionSuppression(
                id=suppression_id,
                paragraph_id=paragraph_id,
                entity_id=from_entity_id,
                span_start=span_start,
                span_end=span_end,
            )
        )
        await self._mentions.add_mention(
            EntityMention(
                id=mention_id,
                paragraph_id=paragraph_id,
                entity_id=to_entity_id,
                span_start=span_start,
                span_end=span_end,
                source="manual",
            )
        )
        generation = await self._next_generation(
            f"retag:{paragraph_id}:{span_start}:{span_end}:{to_entity_id}"
        )
        rows = self._grouped(
            project_id,
            op_kind="retag",
            description="re-assigned an occurrence to another entity",
            base_seed=f"retag:{paragraph_id}:{span_start}:{span_end}:{to_entity_id}",
            generation=generation,
            specs=[
                {
                    "target_id": suppression_id,
                    "target_kind": "suppression",
                    "op": "suppress_span",
                    "after": _suppression_payload(
                        paragraph_id, from_entity_id, span_start, span_end
                    ),
                },
                {
                    "target_id": mention_id,
                    "target_kind": "mention",
                    "op": "add_mention",
                    "after": _mention_payload(paragraph_id, to_entity_id, span_start, span_end),
                },
            ],
        )
        await self._evidence.record_operation(rows)
        return suppression_id, mention_id

    async def change_boundaries(
        self,
        project_id: UUID,
        paragraph_id: UUID,
        entity_id: UUID,
        mention_id: UUID | None,
        old_start: int,
        old_end: int,
        new_start: int,
        new_end: int,
    ) -> UUID:
        """Change a highlight's boundaries (DM-S3c-4, materialize-then-edit). On a *manual* mention
        (`mention_id` given) the offsets are edited **in place**. On an *auto* search hit
        (`mention_id` None) the occurrence is **materialized** — a stored manual span is created at
        the new offsets AND the original position is suppressed so search doesn't re-surface it as a
        duplicate, recorded as ONE grouped op. 404s if the entity (or a named mention) is missing.
        Returns the new/edited mention id."""
        await self._require_entity(project_id, entity_id)

        if mention_id is not None:
            existing = await self._mentions.get_mention(mention_id)
            if existing is None:
                raise MentionNotFound(str(mention_id))
            await self._mentions.update_mention_span(mention_id, new_start, new_end)
            await self._evidence.record_edit(
                GraphEdit(
                    target_id=mention_id,
                    target_kind="mention",
                    op="edit_mention_span",
                    before={"span_start": existing.span_start, "span_end": existing.span_end},
                    after={"span_start": new_start, "span_end": new_end},
                    project_id=project_id,
                )
            )
            return mention_id

        new_mention_id = _mention_id(paragraph_id, entity_id, new_start, new_end)
        suppression_id = _suppression_id(paragraph_id, old_start, old_end, entity_id)
        await self._mentions.add_mention(
            EntityMention(
                id=new_mention_id,
                paragraph_id=paragraph_id,
                entity_id=entity_id,
                span_start=new_start,
                span_end=new_end,
                source="manual",
            )
        )
        await self._mentions.add_suppression(
            MentionSuppression(
                id=suppression_id,
                paragraph_id=paragraph_id,
                entity_id=entity_id,
                span_start=old_start,
                span_end=old_end,
            )
        )
        generation = await self._next_generation(
            f"materialize:{paragraph_id}:{old_start}:{old_end}:{entity_id}"
        )
        rows = self._grouped(
            project_id,
            op_kind="materialize_boundary",
            description="changed a highlight's boundaries",
            base_seed=f"materialize:{paragraph_id}:{old_start}:{old_end}:{entity_id}",
            generation=generation,
            specs=[
                {
                    "target_id": new_mention_id,
                    "target_kind": "mention",
                    "op": "add_mention",
                    "after": _mention_payload(paragraph_id, entity_id, new_start, new_end),
                },
                {
                    "target_id": suppression_id,
                    "target_kind": "suppression",
                    "op": "suppress_span",
                    "after": _suppression_payload(paragraph_id, entity_id, old_start, old_end),
                },
            ],
        )
        await self._evidence.record_operation(rows)
        return new_mention_id

    def _grouped(
        self,
        project_id: UUID,
        *,
        op_kind: str,
        description: str,
        base_seed: str,
        generation: int,
        specs: list[dict[str, object]],
    ) -> list[GraphEdit]:
        """Build a grouped, reversible operation from per-row `specs` (M4.S3c). `seq` is the spec
        index; deterministic `uuid5` ids keep a crash-retry idempotent and `generation` separates
        a redo after an undo (ADR 0007) — the same machinery `_merge_rows`/`_delete_rows` use."""
        operation_id = uuid5(_OP_NS, _op_seed(base_seed, generation))
        return [
            GraphEdit(
                id=uuid5(_OP_NS, f"{operation_id}:{seq}"),
                operation_id=operation_id,
                seq=seq,
                op_kind=op_kind,
                description=description,
                project_id=project_id,
                **spec,
            )
            for seq, spec in enumerate(specs)
        ]

    async def undo_last(self, project_id: UUID, *, preview_only: bool = False) -> UndoResult:
        """Reverse the newest not-yet-undone operation in this project — the general undo executor
        (M4.S3b-be2, DM-S3b-1; resolves spec §10 q2 / §11 / §4.3). Reads the top of the stack,
        inverts it (`domain/graph_undo`), runs the drift check, then — unless `preview_only` —
        applies each inverse in reverse `seq` and stamps the operation `undone`.

        404 (`NothingToUndo`) when the stack is empty; 409 (`UndoConflict`) when the graph drifted
        since (a lost update in reverse). A re-undo of an already-undone operation can't recur — it
        is no longer the live top of the stack — and the inverse actions are idempotent, so a
        crashed undo's retry is safe.
        """
        rows = await self._evidence.latest_live_operation(project_id)
        if not rows:
            raise NothingToUndo(str(project_id))

        head = rows[0]
        op_kind = head.op_kind or head.op
        description = head.description or _SINGLETON_LABELS.get(head.op, head.op)
        plan = invert_operation(rows)

        if plan.drift is not None:
            await self._check_drift(plan.drift, description)
        if preview_only:
            return UndoResult(description=description, op_kind=op_kind, applied=False)

        for action in plan.actions:
            await self._apply_inverse(action)
        op_key = head.operation_id or head.id
        await self._evidence.mark_operation_undone(op_key, undone_at=datetime.now(UTC))
        return UndoResult(description=description, op_kind=op_kind, applied=True)

    async def _check_drift(self, drift: DriftCheck, description: str) -> None:
        entity = await self._graph.get_entity(drift.entity_id)
        if (entity is not None) != drift.expect_present:
            verb = "no longer exists" if drift.expect_present else "was re-created"
            raise UndoConflict(f"cannot undo '{description}': the entity {verb} since")
        if (
            entity is not None
            and drift.expected_fields is not None
            and not fields_match(entity, drift.expected_fields)
        ):
            raise UndoConflict(f"cannot undo '{description}': the entity was edited since")

    async def _apply_inverse(self, action: InverseAction) -> None:
        """Execute one inverse action against the stores. Each is idempotent (create = MERGE,
        delete = no-op-if-absent, reassign/restore = id-keyed) — a crashed undo's retry is safe."""
        if isinstance(action, RecreateEntity):
            await self._graph.create_entity(action.entity)
        elif isinstance(action, RestoreEntityFields):
            current = await self._graph.get_entity(action.entity_id)
            if current is not None:
                await self._graph.update_entity(current.model_copy(update=action.fields))
        elif isinstance(action, RecreateRelation):
            await self._graph.create_relation(action.relation)
        elif isinstance(action, RemoveRelation):
            await self._graph.delete_relation(action.edge_id)
        elif isinstance(action, ReassignMentions):
            await self._mentions.reassign_mentions(action.mention_ids, action.to_entity_id)
        elif isinstance(action, RestoreMentions):
            await self._mentions.restore_mentions(action.mentions)
        elif isinstance(action, RemoveMention):
            await self._mentions.delete_mention(action.mention_id)
        elif isinstance(action, DeleteEntity):
            await self._graph.delete_entity(action.entity_id)
        elif isinstance(action, RemoveSuppression):
            await self._mentions.delete_suppression(action.suppression_id)
        elif isinstance(action, RestoreMentionSpan):
            await self._mentions.update_mention_span(
                action.mention_id, action.span_start, action.span_end
            )

    @staticmethod
    def _delete_rows(
        project_id: UUID,
        entity: GraphEntity,
        edges: list[GraphRelation],
        mentions: list[EntityMention],
        description: str,
        generation: int,
    ) -> list[GraphEdit]:
        """The grouped before-image of a whole-entity delete. `seq` is ordered so undo's reverse
        replay recreates the **node first** (seq 2), then its edges (seq 1 — Neo4j would drop an
        edge whose endpoint is missing), then its mentions (seq 0)."""
        operation_id = uuid5(_OP_NS, _op_seed(f"delete:{entity.id}", generation))

        def row(seq: int, op: str, before: dict[str, object]) -> GraphEdit:
            return GraphEdit(
                id=uuid5(_OP_NS, f"{operation_id}:{seq}"),
                operation_id=operation_id,
                seq=seq,
                op_kind="delete",
                description=description,
                project_id=project_id,
                target_id=entity.id,
                target_kind="entity",
                op=op,
                before=before,
            )

        return [
            row(0, "delete_mentions", {"mentions": [m.model_dump(mode="json") for m in mentions]}),
            row(1, "delete_relations", {"edges": [e.model_dump(mode="json") for e in edges]}),
            row(2, "delete_entity", entity.model_dump(mode="json")),
        ]

    async def _next_generation(self, base: str) -> int:
        """Pick the generation discriminator for a grouped operation's id (ADR 0007, Consequences).

        The id is `uuid5` of the operation's targets so a crash-retry re-derives it and never
        doubles the evidence. But after an undo, redoing the *same* operation on the *same* targets
        (re-merge a pair, re-delete an entity) would re-derive the **same** id and be dropped by
        `ON CONFLICT (id) DO NOTHING`. So we bump a generation past any *undone* operation for these
        targets: a live op probes False (a retry of an in-flight op keeps the same generation —
        still idempotent), only an undone prior op pushes the next generation. Almost always 0;
        1+ only after a real undo-then-redo."""
        generation = 0
        while await self._evidence.is_operation_undone(uuid5(_OP_NS, _op_seed(base, generation))):
            generation += 1
        return generation

    @staticmethod
    def _merge_rows(
        project_id: UUID,
        survivor_before: GraphEntity,
        absorbed: GraphEntity,
        consolidated: GraphEntity,
        steps: tuple[MergeStep, ...],
        moved_mention_ids: list[UUID],
        generation: int,
    ) -> list[GraphEdit]:
        """Build the grouped before-image of a merge — one reversible row per sub-change, so undo
        (be2) replays each inverse in reverse `seq` order (INV-3, the compensating-transaction
        shape). Deterministic operation + row ids keep a crash-retry idempotent; `generation`
        disambiguates a re-merge of the same pair after an undo (ADR 0007)."""
        operation_id = uuid5(
            _OP_NS, _op_seed(f"merge:{absorbed.id}:{survivor_before.id}", generation)
        )
        description = f"merged {_display_name(absorbed)} into {_display_name(survivor_before)}"

        def row(seq: int, **kw: object) -> GraphEdit:
            return GraphEdit(
                id=uuid5(_OP_NS, f"{operation_id}:{seq}"),
                operation_id=operation_id,
                seq=seq,
                op_kind="merge",
                description=description,
                project_id=project_id,
                **kw,
            )

        rows = [
            # seq 0: A's pre-merge aliases/properties → the consolidated values (un-fold on undo).
            row(
                0,
                target_id=survivor_before.id,
                target_kind="entity",
                op="merge_consolidate",
                before={
                    "aliases": survivor_before.aliases,
                    "properties": survivor_before.properties,
                },
                after={"aliases": consolidated.aliases, "properties": consolidated.properties},
            )
        ]
        # one row per edge sub-change, in plan order (the re-point/fold/discard step list).
        for seq, step in enumerate(steps, start=1):
            after = (
                None
                if step.kind == "discard_self_loop"
                else step.repoint.new_edge.model_dump(mode="json")
            )
            rows.append(
                row(
                    seq,
                    target_id=step.repoint.old_edge.id,
                    target_kind="relation",
                    op=f"{step.kind}_relation",
                    before=step.repoint.old_edge.model_dump(mode="json"),
                    after=after,
                )
            )
        # `seq` mirrors the forward execution order (mentions move while B is alive, *then* B is
        # deleted last), so undo's reverse replay recreates B before re-pointing mentions to it.
        next_seq = len(steps) + 1
        rows.append(
            # the moved mention ids (re-point them back to B on undo).
            row(
                next_seq,
                target_id=absorbed.id,
                target_kind="entity",
                op="repoint_mentions",
                before={
                    "from_entity_id": str(absorbed.id),
                    "to_entity_id": str(survivor_before.id),
                    "mention_ids": [str(mid) for mid in moved_mention_ids],
                },
            )
        )
        rows.append(
            # B's full node snapshot (recreate B on undo) — last, so it reverses first.
            row(
                next_seq + 1,
                target_id=absorbed.id,
                target_kind="entity",
                op="delete_absorbed",
                before=absorbed.model_dump(mode="json"),
            )
        )
        return rows

    async def _require_entity(self, project_id: UUID, entity_id: UUID) -> GraphEntity:
        entity = await self._graph.get_entity(entity_id)
        if entity is None or entity.project_id != project_id:
            raise EntityNotFound(str(entity_id))
        return entity
