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

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from story_forge.domain.candidates import relation_edge_id
from story_forge.domain.entity_edits import EntityEditPatch, apply_entity_edit, diff_entity
from story_forge.domain.graph import GraphEntity, GraphRelation
from story_forge.domain.graph_edit import GraphEdit

# A manually-asserted edge carries full confidence (a human stated it, not a model).
_MANUAL_CONFIDENCE = 1.0


class EntityGraphEditor(Protocol):
    """The committed-graph mutators + reads the edit path needs (a `Neo4jRepo`)."""

    async def get_entity(self, entity_id: UUID) -> GraphEntity | None: ...
    async def update_entity(self, entity: GraphEntity) -> None: ...
    async def get_relation(self, project_id: UUID, edge_id: UUID) -> GraphRelation | None: ...
    async def create_relation(self, relation: GraphRelation) -> None: ...
    async def delete_relation(self, edge_id: UUID) -> None: ...


class EditEvidenceRepo(Protocol):
    """The before→after edit log (a `PostgresEditStore`)."""

    async def record_edit(self, edit: GraphEdit) -> None: ...


class EntityNotFound(LookupError):
    """No such entity in this project (→404). Covers a stale-tab edit of a node that was merged or
    removed, and the tenancy guard (an entity belonging to another project)."""


class RelationEdgeNotFound(LookupError):
    """No such committed edge in this project (→404) — e.g. a double-remove from two tabs."""


@dataclass(frozen=True)
class RelationEditResult:
    """Outcome of an add — the edge id and whether the MERGE folded onto an edge that already
    existed (the re-predicate / duplicate-add collision the UI warns on, DM-S3a-3)."""

    edge_id: UUID
    merged_into_existing: bool


class EntityEditService:
    """Edits a committed entity's fields and adds/removes relations under the human gate."""

    def __init__(self, graph: EntityGraphEditor, evidence: EditEvidenceRepo) -> None:
        self._graph = graph
        self._evidence = evidence

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

    async def _require_entity(self, project_id: UUID, entity_id: UUID) -> GraphEntity:
        entity = await self._graph.get_entity(entity_id)
        if entity is None or entity.project_id != project_id:
            raise EntityNotFound(str(entity_id))
        return entity
