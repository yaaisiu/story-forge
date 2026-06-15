"""CandidateReviewService — the human-accept write path (M3.S4a, spec §3.3 Stage 4 / §7 step 7).

This is INV-1's first enforcer: the **only** code that writes the graph, and only on an explicit
human action (accept). Under intercept-before-write the cascade merely staged proposals; here a
reviewer commits one — create a new entity, fold the candidate into an existing one (merge), or
reject it. Each terminal leaves durable, reversible evidence (INV-3) in `candidate_decisions`.

Two contracts make the cross-store write safe ([[idempotency]], [[toctou]]):

- **Status-flip is the LAST write.** The order is Neo4j → `entity_mention` (+ the candidate's
  context vector) → evidence row → flip `candidates.status`. A crash before the flip leaves the
  candidate `review-queued`, so a retry re-runs — and because the entity / mention / decision ids
  are derived **deterministically** from the candidate id (and the writes are MERGE-on-id /
  `ON CONFLICT DO NOTHING`), the retry produces no duplicate node, mention, or evidence row.
- **Re-validate the merge target.** Between staging (time T) and accept (T+Δ) the chosen target
  may have been merged away; the service re-reads it and raises `StaleMergeTarget` (→409) rather
  than aliasing onto a vanished node.

It lives in `agents/` (orchestration composing domain + adapters via Protocols), not `domain/`
(which forbids I/O), and not the API (kept thin) — the same placement as the coordinators.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid5

from story_forge.domain.candidates import (
    CandidateDecision,
    CandidateStatus,
    StagedCandidate,
)
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import EntityMention

# A fixed namespace so accept-path ids are a deterministic function of the candidate id —
# the basis of the retry-idempotency contract (same candidate → same entity/mention/decision id).
_ACCEPT_NS = UUID("a5f0c0de-0000-4000-8000-000000000001")

AcceptAction = Literal["create", "merge"]


class GraphWriter(Protocol):
    """The accept-time graph writes (a `Neo4jRepo`)."""

    async def create_entity(self, entity: GraphEntity) -> None: ...
    async def add_alias(self, entity_id: UUID, alias: str) -> None: ...
    async def get_entity(self, entity_id: UUID) -> GraphEntity | None: ...


class MentionWriter(Protocol):
    """The accept-time mention write (a `PostgresMentionStore`)."""

    async def add_mention(self, mention: EntityMention) -> None: ...


class CandidateRepo(Protocol):
    """The staging store's review ops (a `PostgresCandidateStore`)."""

    async def get(self, candidate_id: UUID) -> StagedCandidate | None: ...
    async def insert_decision(self, decision: CandidateDecision) -> None: ...
    async def set_status(self, candidate_id: UUID, status: CandidateStatus) -> None: ...


class CandidateNotFound(LookupError):
    """No candidate with that id (→404)."""


class StaleMergeTarget(RuntimeError):
    """The chosen merge target no longer exists (TOCTOU at the review gate, →409)."""


@dataclass(frozen=True)
class ReviewResult:
    """Outcome of an accept/reject — the committed entity (if any) and the terminal status."""

    candidate_id: UUID
    status: CandidateStatus
    entity_id: UUID | None
    already_decided: bool  # True when the candidate was already terminal (idempotent no-op)


class CandidateReviewService:
    """Commits or rejects a staged candidate — the only graph-writing path (INV-1)."""

    def __init__(
        self, graph: GraphWriter, candidates: CandidateRepo, mentions: MentionWriter
    ) -> None:
        self._graph = graph
        self._candidates = candidates
        self._mentions = mentions

    async def accept(
        self,
        candidate_id: UUID,
        *,
        language: str,
        action: AcceptAction | None = None,
        target_entity_id: UUID | None = None,
        custom_type: str | None = None,
    ) -> ReviewResult:
        """Commit a candidate to the graph (create a new entity or merge into an existing one).

        `action` defaults to the cascade's own proposal; the reviewer may override it (accept,
        change-target, or create-new with a custom type — spec §3.3 Stage 4). Writes in the
        order Neo4j → mention → evidence → status (the last write), so a retry is safe.
        """
        candidate = await self._load_open(candidate_id)
        if candidate is None:
            return await self._terminal_noop(candidate_id)

        resolved = action or ("merge" if candidate.proposal == "merge" else "create")
        entity_id: UUID
        status: Literal["created", "merged"]
        if resolved == "merge":
            entity_id, status = await self._merge(candidate, target_entity_id)
        else:
            entity_id, status = await self._create(candidate, custom_type, language)

        await self._mentions.add_mention(
            EntityMention(
                id=uuid5(_ACCEPT_NS, f"mention:{candidate.id}"),
                paragraph_id=candidate.paragraph_id,
                entity_id=entity_id,
                embedding=candidate.context_embedding,
            )
        )
        await self._record(candidate, decision=status, target_entity_id=entity_id)
        await self._candidates.set_status(candidate.id, status)  # LAST write
        return ReviewResult(candidate.id, status, entity_id, already_decided=False)

    async def reject(self, candidate_id: UUID) -> ReviewResult:
        """Reject a candidate — nothing enters the graph; the rejection is remembered (DM-rej)."""
        candidate = await self._load_open(candidate_id)
        if candidate is None:
            return await self._terminal_noop(candidate_id)
        await self._record(
            candidate, decision="rejected", target_entity_id=candidate.target_entity_id
        )
        await self._candidates.set_status(candidate.id, "rejected")  # LAST write
        return ReviewResult(candidate.id, "rejected", None, already_decided=False)

    # --- helpers -----------------------------------------------------------

    async def _merge(
        self, candidate: StagedCandidate, override_target: UUID | None
    ) -> tuple[UUID, Literal["merged"]]:
        target = override_target or candidate.target_entity_id
        if target is None:
            # A merge with no target is a create in disguise — defensively reject it rather
            # than aliasing onto nothing. (The UI never sends this; guard the contract.)
            raise StaleMergeTarget("merge requested with no target entity")
        if await self._graph.get_entity(target) is None:
            raise StaleMergeTarget(f"merge target {target} no longer exists")
        await self._graph.add_alias(target, candidate.candidate_name)
        return target, "merged"

    async def _create(
        self, candidate: StagedCandidate, custom_type: str | None, language: str
    ) -> tuple[UUID, Literal["created"]]:
        entity_id = uuid5(_ACCEPT_NS, f"entity:{candidate.id}")  # deterministic → idempotent create
        # Provisional bilingual naming (M2 rule, §3.2): the surface form fills the project-language
        # slot, the peer stays null. The §10 q8 peer-naming question becomes concrete here and stays
        # the spec's to resolve (ADR 0004 records it deferred).
        name = candidate.candidate_name
        await self._graph.create_entity(
            GraphEntity(
                id=entity_id,
                type=custom_type or candidate.type,
                canonical_name_pl=name if language == "pl" else None,
                canonical_name_en=name if language != "pl" else None,
                properties=candidate.properties,
                first_seen_paragraph_id=candidate.paragraph_id,
                project_id=candidate.project_id,
            )
        )
        return entity_id, "created"

    async def _record(
        self,
        candidate: StagedCandidate,
        *,
        decision: Literal["created", "merged", "rejected"],
        target_entity_id: UUID | None,
    ) -> None:
        await self._candidates.insert_decision(
            CandidateDecision(
                id=uuid5(_ACCEPT_NS, f"decision:{candidate.id}"),
                candidate_id=candidate.id,
                decision=decision,
                target_entity_id=target_entity_id,
                shown_proposal={
                    "proposal": candidate.proposal,
                    "target_entity_id": str(candidate.target_entity_id)
                    if candidate.target_entity_id
                    else None,
                    "stage_reached": candidate.stage_reached,
                    "confidence": candidate.confidence,
                    "reasoning": candidate.reasoning,
                    "alternatives": candidate.alternatives,
                },
            )
        )

    async def _load_open(self, candidate_id: UUID) -> StagedCandidate | None:
        """Load a candidate that is still awaiting review; raise if it does not exist."""
        candidate = await self._candidates.get(candidate_id)
        if candidate is None:
            raise CandidateNotFound(str(candidate_id))
        return candidate if candidate.status == "review-queued" else None

    async def _terminal_noop(self, candidate_id: UUID) -> ReviewResult:
        """An already-decided candidate: return its terminal state without re-writing."""
        candidate = await self._candidates.get(candidate_id)
        assert candidate is not None  # _load_open already proved it exists
        return ReviewResult(
            candidate.id, candidate.status, candidate.target_entity_id, already_decided=True
        )
