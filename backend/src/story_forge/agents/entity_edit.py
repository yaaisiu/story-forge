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
from typing import Protocol
from uuid import UUID, uuid5

from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.entity_edits import EntityEditPatch, apply_entity_edit, diff_entity
from story_forge.domain.entity_merge import MergeStep, plan_merge
from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.graph_edit import GraphEdit

# A manually-asserted edge carries full confidence (a human stated it, not a model).
_MANUAL_CONFIDENCE = 1.0

# Fixed namespace so a merge's `operation_id` and its grouped row ids are a deterministic function
# of the (absorbed, survivor) pair — the basis of the crash-retry idempotency contract (a re-run
# re-derives the same ids, so `ON CONFLICT (id) DO NOTHING` never doubles the evidence). Distinct
# from the accept/relation namespaces in `domain/candidates.py` so the id spaces never collide.
_OP_NS = UUID("a5f0c0de-0000-4000-8000-000000000004")


class EntityGraphEditor(Protocol):
    """The committed-graph mutators + reads the edit path needs (a `Neo4jRepo`)."""

    async def get_entity(self, entity_id: UUID) -> GraphEntity | None: ...
    async def update_entity(self, entity: GraphEntity) -> None: ...
    async def get_relation(self, project_id: UUID, edge_id: UUID) -> GraphRelation | None: ...
    async def create_relation(self, relation: GraphRelation) -> None: ...
    async def delete_relation(self, edge_id: UUID) -> None: ...
    async def get_neighbourhood(
        self, entity_id: UUID
    ) -> list[tuple[GraphRelation, GraphEntity]]: ...
    async def delete_entity(self, entity_id: UUID) -> None: ...


class EditEvidenceRepo(Protocol):
    """The before→after edit log (a `PostgresEditStore`)."""

    async def record_edit(self, edit: GraphEdit) -> None: ...
    async def record_operation(self, edits: Sequence[GraphEdit]) -> None: ...


class MentionRepo(Protocol):
    """The cross-store mention re-point a merge needs (a `PostgresMentionStore`)."""

    async def repoint_mentions(self, from_entity_id: UUID, to_entity_id: UUID) -> list[UUID]: ...


class EntityNotFound(LookupError):
    """No such entity in this project (→404). Covers a stale-tab edit of a node that was merged or
    removed, and the tenancy guard (an entity belonging to another project)."""


class RelationEdgeNotFound(LookupError):
    """No such committed edge in this project (→404) — e.g. a double-remove from two tabs."""


class SelfMergeError(ValueError):
    """A merge whose absorbed and survivor are the same entity (→409) — a no-op that would delete
    the only node. Guarded before any read."""


@dataclass(frozen=True)
class RelationEditResult:
    """Outcome of an add — the edge id and whether the MERGE folded onto an edge that already
    existed (the re-predicate / duplicate-add collision the UI warns on, DM-S3a-3)."""

    edge_id: UUID
    merged_into_existing: bool


@dataclass(frozen=True)
class MergeSummary:
    """Outcome of a merge — the survivor's id + the counts the side panel reports to the author
    (re-pointed/folded edges, dropped self-loops, mentions moved; DM-S3b-3)."""

    survivor_entity_id: UUID
    repointed_count: int
    folded_count: int
    self_loops_dropped: int
    mentions_repointed: int


def _display_name(entity: GraphEntity) -> str:
    """A human label for the undo description (DM-S3b-1, see-what-I-undo): a canonical name, else
    the first alias, else the id — never blank."""
    return (
        entity.canonical_name_pl
        or entity.canonical_name_en
        or (entity.aliases[0] if entity.aliases else None)
        or str(entity.id)
    )


class EntityEditService:
    """Edits a committed entity's fields, adds/removes relations, and merges entities under the
    human gate (M4.S3a edit path + M4.S3b merge — INV-9's "edit" handler grows operations, no new
    writer class)."""

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
                },
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
                before={
                    "subject_id": str(existing.subject_id),
                    "predicate": existing.type,
                    "object_id": str(existing.object_id),
                },
            )
        )

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

        Order, mirroring the accept/edit services: **Neo4j first → Postgres mention re-point →
        evidence last**. The before-image is captured **in memory before** the Neo4j writes (B is
        unreadable once deleted). A crash between the Neo4j writes and the evidence write strands a
        completed merge whose audit row was not written — the narrow, accepted PoC window (the
        DM-S3a-6 last-write-wins posture; ADR 0007). Guards: self-merge (→`SelfMergeError`), either
        endpoint missing/cross-project (→`EntityNotFound`), an unresolved property conflict
        (→`EntityMergeInvalid`).
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

        # Neo4j first: fold B into A, re-point each incident edge (delete-old + create-new, or
        # delete-only for a dropped self-loop), then DETACH DELETE B.
        await self._graph.update_entity(plan.survivor)
        for step in plan.steps:
            await self._graph.delete_relation(step.repoint.old_edge.id)
            if step.kind in ("repoint", "fold"):
                await self._graph.create_relation(step.repoint.new_edge)
        await self._graph.delete_entity(absorbed_id)

        # Postgres next: move B's mentions onto A (the moved ids feed the before-image for undo).
        moved_mention_ids = await self._mentions.repoint_mentions(absorbed_id, target_id)

        # Evidence last: the grouped, reversible before-image of the whole operation.
        await self._evidence.record_operation(
            self._merge_rows(
                project_id, survivor, absorbed, plan.survivor, plan.steps, moved_mention_ids
            )
        )

        return MergeSummary(
            survivor_entity_id=target_id,
            repointed_count=plan.repointed_count,
            folded_count=plan.folded_count,
            self_loops_dropped=plan.self_loops_dropped,
            mentions_repointed=len(moved_mention_ids),
        )

    @staticmethod
    def _merge_rows(
        project_id: UUID,
        survivor_before: GraphEntity,
        absorbed: GraphEntity,
        consolidated: GraphEntity,
        steps: tuple[MergeStep, ...],
        moved_mention_ids: list[UUID],
    ) -> list[GraphEdit]:
        """Build the grouped before-image of a merge — one reversible row per sub-change, so undo
        (be2) replays each inverse in reverse `seq` order (INV-3, the compensating-transaction
        shape). Deterministic operation + row ids keep a crash-retry idempotent."""
        operation_id = uuid5(_OP_NS, f"merge:{absorbed.id}:{survivor_before.id}")
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
        next_seq = len(steps) + 1
        rows.append(
            # B's full node snapshot (recreate B on undo).
            row(
                next_seq,
                target_id=absorbed.id,
                target_kind="entity",
                op="delete_absorbed",
                before=absorbed.model_dump(mode="json"),
            )
        )
        rows.append(
            # the moved mention ids (re-point them back to B on undo).
            row(
                next_seq + 1,
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
        return rows

    async def _require_entity(self, project_id: UUID, entity_id: UUID) -> GraphEntity:
        entity = await self._graph.get_entity(entity_id)
        if entity is None or entity.project_id != project_id:
            raise EntityNotFound(str(entity_id))
        return entity
