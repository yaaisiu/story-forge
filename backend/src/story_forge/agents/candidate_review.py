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

import contextlib
from dataclasses import dataclass
from typing import Literal, Protocol
from uuid import UUID, uuid5

from story_forge.domain.candidates import (
    _ACCEPT_NS,
    CandidateDecision,
    CandidateStatus,
    StagedCandidate,
    committed_entity_id,
)
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import EntityMention

# `_ACCEPT_NS` (the deterministic-id namespace) and `committed_entity_id` (the create→uuid5 /
# merge→target derivation) live in `domain/candidates.py`, shared with relation-endpoint
# resolution so the two homes can't drift (`[[idempotency]]`).

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


class ReMatcher(Protocol):
    """On-accept intra-batch dedup (a `ReMatchService`, M3.S4c).

    After a human accept commits an entity, re-runs the deterministic matcher over the
    still-pending candidates against it and flips strong duplicates `new → merge` — writing
    only the staging table, never the graph (INV-9 holds). Optional: when absent, accept
    behaves exactly as in S4a."""

    async def rematch(
        self,
        *,
        story_id: UUID,
        accepted_entity_id: UUID,
        accepted_name: str,
        accepted_vector: list[float] | None,
    ) -> int: ...


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
        self,
        graph: GraphWriter,
        candidates: CandidateRepo,
        mentions: MentionWriter,
        rematch: ReMatcher | None = None,
    ) -> None:
        self._graph = graph
        self._candidates = candidates
        self._mentions = mentions
        self._rematch = rematch

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
        await self._candidates.set_status(candidate.id, status)  # LAST graph-affecting write
        await self._maybe_rematch(candidate, entity_id)
        return ReviewResult(candidate.id, status, entity_id, already_decided=False)

    async def reject(self, candidate_id: UUID) -> ReviewResult:
        """Reject a candidate — nothing enters the graph; the rejection is recorded as evidence
        for a future matcher consult (DM-rej; that consult is not built in S4a)."""
        candidate = await self._load_open(candidate_id)
        if candidate is None:
            return await self._terminal_noop(candidate_id)
        await self._record(
            candidate, decision="rejected", target_entity_id=candidate.target_entity_id
        )
        await self._candidates.set_status(candidate.id, "rejected")  # LAST write
        return ReviewResult(candidate.id, "rejected", None, already_decided=False)

    # --- helpers -----------------------------------------------------------

    async def _maybe_rematch(self, candidate: StagedCandidate, entity_id: UUID) -> None:
        """On-accept intra-batch dedup (M3.S4c): flip still-pending duplicates of the
        just-committed entity to a merge proposal.

        Runs **after** the status flip, so the committed candidate is itself out of the
        pending set, and is **fail-closed**: a re-match failure must never roll back the
        human's accept (which has already fully succeeded). Any error is swallowed — the
        proposals simply stay as they were (a safe NEW the author can still merge by hand);
        re-match is a suggestion enhancement, never a gate on the commit. The match signal
        is built from the accept's own data (the entity id, the candidate's surface name,
        and the mention vector just written), so this adds no read beyond re-match's own.
        """
        if self._rematch is None:
            return
        # Fail-closed ([[fail-closed]]): the accept has fully succeeded; re-match is a best-effort
        # suggestion enhancement, never a gate on the commit, so any failure is suppressed (the
        # proposals simply stay as they were — a safe NEW the author can still merge by hand). When
        # operational logging lands this becomes a logged warning (backend/AGENTS.md).
        with contextlib.suppress(Exception):
            await self._rematch.rematch(
                story_id=candidate.story_id,
                accepted_entity_id=entity_id,
                accepted_name=candidate.candidate_name,
                accepted_vector=candidate.context_embedding,
            )

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
        """An already-decided candidate: return its terminal state without re-writing.

        Reports the same `entity_id` the original accept committed, so an idempotent
        re-accept (a double-submit) still hands the caller the live node: a `created`
        candidate's node lives at the deterministic accept id; a `merged` one folded into
        its target. (For a merge the reviewer *retargeted*, this reflects the proposal
        target — the committed-target precision is the decision row's, an edge of the
        double-submit edge, not worth a second read here.)
        """
        candidate = await self._candidates.get(candidate_id)
        if candidate is None:
            raise CandidateNotFound(str(candidate_id))  # deleted between the two reads
        entity_id = committed_entity_id(candidate)  # created → accept-id, merged → target
        return ReviewResult(candidate.id, candidate.status, entity_id, already_decided=True)
