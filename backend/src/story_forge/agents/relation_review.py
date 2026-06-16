"""RelationReviewService — the human-gated relation-edge write path (M3.S4e, spec §3.3's
5th Stage-4 action "decide on relations").

Entity dedupe (S4a–S4d) commits *nodes* under a human gate; this is the symmetric gate for
*edges*. It is the **only** code that writes a graph edge, and only on an explicit human
decision — extending INV-1 (human-in-the-loop) and INV-9 (no automated stage writes the
graph) from nodes to edges. The `ExtractionCoordinator` still writes zero edges; it only
stages surface-form relations.

The shape mirrors `CandidateReviewService`:

- **Resolve, don't re-point** (`[[referential-integrity]]`). A staged relation's endpoints
  are *surface strings* with no entity id; an edge is written **lazily**, after review, by
  resolving each string to the *committed* id of the same-paragraph accepted candidate it
  names (DM-Rel-2, normalised-exact). A candidate that was merged resolves to its target's
  id, so a merge needs no edge re-point — the edge is born pointing at the survivor.
- **Idempotent, status-last.** The edge id is a deterministic function of the resolved
  (subject, predicate, object) triple (DM-Rel-6), so the same fact across two paragraphs is
  one edge and a retried commit doubles nothing; the status flip is the last write, so a
  crash before it leaves the relation `staged` and a retry re-commits idempotently.
- **Re-resolve at commit (TOCTOU).** `list_committable` resolves at list-time, but a
  candidate could be rejected/retargeted before the human commits, so `decide` re-resolves
  against the current accepted set and refuses (→409) rather than write a stale edge.

Held endpoints (named but never accepted — DM-Rel-7) and self-loops (both endpoints
resolving to one entity after merges) are simply never committable; no fuzzy fallback.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID

from story_forge.domain.candidates import (
    RelationStatus,
    StagedCandidate,
    StagedRelation,
    committed_entity_id,
    normalize_name,
    relation_edge_id,
)
from story_forge.domain.graph import GraphRelation

DecideAction = Literal["commit", "reject"]


class GraphRelationWriter(Protocol):
    """The accept-time edge write (a `Neo4jRepo`)."""

    async def create_relation(self, relation: GraphRelation) -> None: ...


class RelationRepo(Protocol):
    """The staged-relation store's review ops (a `PostgresRelationStore`)."""

    async def list_staged(self, story_id: UUID) -> list[StagedRelation]: ...
    async def get_relation(self, relation_id: UUID) -> StagedRelation | None: ...
    async def mark_written(
        self,
        relation_id: UUID,
        *,
        subject_entity_id: UUID,
        object_entity_id: UUID,
        edge_id: UUID,
    ) -> None: ...
    async def mark_rejected(self, relation_id: UUID) -> None: ...


class AcceptedCandidateRepo(Protocol):
    """Reads the accepted candidates a relation resolves its endpoints against."""

    async def list_accepted(self, story_id: UUID) -> list[StagedCandidate]: ...


class RelationNotFound(LookupError):
    """No staged relation with that id (→404)."""


class RelationEndpointsUnresolved(RuntimeError):
    """At commit, an endpoint no longer resolves to a committed entity, or the relation is a
    self-loop — the TOCTOU/held guard at the gate (→409); nothing is written."""


@dataclass(frozen=True)
class CommittableRelation:
    """A staged relation whose *both* endpoints currently resolve to committed entities —
    the render set for the §3.3 decide-relations surface, with the resolved ids."""

    relation: StagedRelation
    subject_entity_id: UUID
    object_entity_id: UUID


@dataclass(frozen=True)
class RelationDecisionResult:
    """Outcome of a commit/reject — the terminal status and the committed edge id (if any)."""

    relation_id: UUID
    status: RelationStatus
    edge_id: UUID | None
    already_decided: bool  # True when the relation was already terminal (idempotent no-op)


def _resolution_index(accepted: list[StagedCandidate]) -> dict[tuple[UUID, str], UUID | None]:
    """Map (paragraph_id, normalised surface name) → the committed entity id it resolves to.

    Built only from accepted candidates (`created`/`merged`); a key whose paragraph holds two
    accepted candidates of the same name resolving to *different* entities is **ambiguous** →
    stored as `None` so it is treated as unresolved (held), never guessed.
    """
    index: dict[tuple[UUID, str], UUID | None] = {}
    for candidate in accepted:
        entity_id = committed_entity_id(candidate)
        if entity_id is None:
            continue
        key = (candidate.paragraph_id, normalize_name(candidate.candidate_name))
        if key in index and index[key] != entity_id:
            index[key] = None  # ambiguous → held
        elif key not in index:
            index[key] = entity_id
    return index


def _resolve(
    relation: StagedRelation, index: dict[tuple[UUID, str], UUID | None]
) -> tuple[UUID, UUID] | None:
    """Resolve a staged relation's two surface endpoints to committed ids within its
    paragraph, or None if either is unresolved/ambiguous (held) or the pair is a self-loop."""
    subject_id = index.get((relation.paragraph_id, normalize_name(relation.subject)))
    object_id = index.get((relation.paragraph_id, normalize_name(relation.object)))
    if subject_id is None or object_id is None:
        return None  # held: an endpoint is pending/rejected/ambiguous (DM-Rel-7)
    if subject_id == object_id:
        return None  # self-loop (a merge artifact) — drop, don't write (e)-[r]->(e)
    return subject_id, object_id


class RelationReviewService:
    """Commits or rejects a staged relation — the only edge-writing path (INV-1/INV-9)."""

    def __init__(
        self,
        graph: GraphRelationWriter,
        relations: RelationRepo,
        candidates: AcceptedCandidateRepo,
    ) -> None:
        self._graph = graph
        self._relations = relations
        self._candidates = candidates

    async def list_committable(self, story_id: UUID) -> list[CommittableRelation]:
        """The §3.3 decide-relations queue: staged relations whose *both* endpoints now
        resolve to committed entities (held/self-loop relations are excluded)."""
        index = _resolution_index(await self._candidates.list_accepted(story_id))
        committable: list[CommittableRelation] = []
        for relation in await self._relations.list_staged(story_id):
            resolved = _resolve(relation, index)
            if resolved is None:
                continue
            subject_id, object_id = resolved
            committable.append(CommittableRelation(relation, subject_id, object_id))
        return committable

    async def decide(self, relation_id: UUID, *, action: DecideAction) -> RelationDecisionResult:
        """Commit (write the edge) or reject a staged relation under the human gate.

        Commit re-resolves both endpoints (TOCTOU), then writes the edge idempotently and
        flips the status **last**, so a crash before the flip re-commits cleanly on retry. A
        relation that is already terminal is an idempotent no-op (a double-submit).
        """
        relation = await self._relations.get_relation(relation_id)
        if relation is None:
            raise RelationNotFound(str(relation_id))
        if relation.status != "staged":
            return RelationDecisionResult(
                relation.id, relation.status, relation.edge_id, already_decided=True
            )

        if action == "reject":
            await self._relations.mark_rejected(relation.id)  # LAST write
            return RelationDecisionResult(relation.id, "rejected", None, already_decided=False)

        # commit: re-resolve against the *current* accepted set, refuse a stale/held edge.
        index = _resolution_index(await self._candidates.list_accepted(relation.story_id))
        resolved = _resolve(relation, index)
        if resolved is None:
            raise RelationEndpointsUnresolved(str(relation_id))
        subject_id, object_id = resolved
        edge_id = relation_edge_id(subject_id, relation.predicate, object_id)
        await self._graph.create_relation(
            GraphRelation(
                id=edge_id,
                type=relation.predicate,
                subject_id=subject_id,
                object_id=object_id,
                confidence=relation.confidence if relation.confidence is not None else 0.0,
                source_paragraph_id=relation.paragraph_id,
            )
        )
        await self._relations.mark_written(  # LAST graph-affecting write
            relation.id,
            subject_entity_id=subject_id,
            object_entity_id=object_id,
            edge_id=edge_id,
        )
        return RelationDecisionResult(relation.id, "written", edge_id, already_decided=False)
