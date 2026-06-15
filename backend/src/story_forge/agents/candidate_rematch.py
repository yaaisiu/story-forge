"""ReMatchService — on-accept intra-batch dedup (M3.S4c, spec §3.3 "on-accept re-match").

The §3.3 cascade matches a candidate only against the graph as it stood at *extraction
time*, so duplicates within one batch (the canonical "Janek" ×3 against an empty graph)
stage as independent NEW proposals the queue cannot merge. This service closes that gap:
when the human accepts a candidate, it re-runs the **deterministic** matcher (Stage 1
RapidFuzz + Stage 2 cosine — never the Stage-3 judge) over the still-pending candidates
against the just-accepted entity, flipping a strong match's staged `proposal` `new → merge`
so the duplicate lights up in the queue (the S4b card refetches on accept).

Three properties make this safe — they are why **INV-1 and INV-9 hold** (the architecture
proposal `m3s4c-intra-batch-rematch` spells them out):

- **Staging-only.** It writes the Postgres `candidates` table and *nothing* else — never
  Neo4j, never an evidence row. It changes a *machine suggestion* on a still-pending
  candidate; the human still commits every merge (INV-1). INV-9 ("no automated stage writes
  the graph") holds because re-match stays on the staging side of the graph/staging line.
- **Monotone** (DM-S4c-4). It only ever upgrades `new → merge`; it never downgrades, never
  re-points an existing merge, and never touches a terminal row. So re-running it on an
  unchanged accepted set is a no-op — it is idempotent and never thrashes a proposal the
  author is mid-decision on.
- **Incremental, zero extra reads** (DM-S4c-2). Its match signal is built entirely from the
  accept's own data — the accepted entity's id, its name, and the mention vector just
  written — so it adds no I/O beyond the one `list_pending` read and the per-flip update.

It lives in `agents/` (orchestration over injected Protocols, no concrete I/O), reusing the
deterministic `MatchingAgent`; it depends only on the `Matcher` and `ReMatchCandidateRepo`
Protocols below, so it stays unit-testable with fakes.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from story_forge.agents.matching_agent import (
    EntityVectors,
    ExistingEntity,
    Stage1Result,
    Stage2Result,
)
from story_forge.domain.candidates import CandidateProposal, StagedCandidate


class Matcher(Protocol):
    """Stages 1 & 2 of the cascade (a `MatchingAgent`) — the same shape `candidate_staging`
    types against. Re-match reuses the deterministic matcher; it never runs the Stage-3 judge."""

    def stage1(self, candidate_name: str, existing: list[ExistingEntity]) -> Stage1Result: ...
    def stage2(
        self, candidate_vector: list[float], existing: list[EntityVectors]
    ) -> Stage2Result: ...


class ReMatchCandidateRepo(Protocol):
    """The staging-store ops re-match needs (a `PostgresCandidateStore`)."""

    async def list_pending(self, story_id: UUID) -> list[StagedCandidate]: ...
    async def update_proposal(
        self,
        candidate_id: UUID,
        *,
        proposal: CandidateProposal,
        target_entity_id: UUID | None,
        stage_reached: int,
        confidence: float | None,
        reasoning: str | None,
        alternatives: list[dict[str, object]],
    ) -> None: ...


@dataclass(frozen=True)
class _Flip:
    """A pending candidate's re-match verdict: how far the matcher ran + the scores it found."""

    stage_reached: int  # 1 (fuzz) or 2 (cosine) — which signal triggered the flip
    confidence: float  # normalised to [0, 1] for the staged row (fuzz/100 or the raw cosine)
    name_score: float  # the Stage-1 fuzz score (0–100), for a uniform alternatives-list scale


class ReMatchService:
    """Re-runs the deterministic matcher over pending candidates after a human accept."""

    def __init__(self, matcher: Matcher, candidates: ReMatchCandidateRepo) -> None:
        self._matcher = matcher
        self._candidates = candidates

    async def rematch(
        self,
        *,
        story_id: UUID,
        accepted_entity_id: UUID,
        accepted_name: str,
        accepted_vector: list[float] | None,
    ) -> int:
        """Flip still-pending candidates that strong-match the just-accepted entity.

        Returns the number of proposals flipped `new → merge`. `accepted_vector` is the
        mention vector written at accept time (None when the embedder had failed at stage
        time → Stage-1-only re-match, mirroring the staging fail-closed gate).
        """
        accepted_id = str(accepted_entity_id)
        existing_names = [ExistingEntity(id=accepted_id, canonical_name=accepted_name, aliases=[])]
        existing_vectors = (
            [EntityVectors(id=accepted_id, mention_vectors=[accepted_vector])]
            if accepted_vector is not None
            else []
        )

        flipped = 0
        for candidate in await self._candidates.list_pending(story_id):
            # Monotone (DM-S4c-4): only ever upgrade a NEW proposal; never re-point an
            # existing merge. (Terminal rows are already excluded by `list_pending`.)
            if candidate.proposal != "new":
                continue
            verdict = self._evaluate(candidate, existing_names, existing_vectors, accepted_vector)
            if verdict is None:
                continue
            await self._candidates.update_proposal(
                candidate.id,
                proposal="merge",
                target_entity_id=accepted_entity_id,
                stage_reached=verdict.stage_reached,
                confidence=verdict.confidence,
                reasoning=f"re-matched against accepted '{accepted_name}' (intra-batch dedup)",
                alternatives=_with_target_first(
                    candidate.alternatives, accepted_entity_id, accepted_name, verdict.name_score
                ),
            )
            flipped += 1
        return flipped

    def _evaluate(
        self,
        candidate: StagedCandidate,
        existing_names: list[ExistingEntity],
        existing_vectors: list[EntityVectors],
        accepted_vector: list[float] | None,
    ) -> _Flip | None:
        """Auto-flip on a strong Stage-1 fuzz (>85%) OR Stage-2 cosine (>0.85) — DM-S4c-3.

        The matcher's `auto-merge-proposed` outcome *is* that band (`classify`'s strict `>`),
        so re-match reuses it verbatim rather than re-deriving a threshold. Sub-threshold
        matches return None (no flip) — they neither merge nor enrich, keeping re-match
        narrow to high-confidence collisions where a nudge helps more than it hurts.
        """
        stage1 = self._matcher.stage1(candidate.candidate_name, existing_names)
        if stage1.outcome == "auto-merge-proposed":
            return _Flip(stage_reached=1, confidence=stage1.score / 100.0, name_score=stage1.score)
        if candidate.context_embedding is not None and accepted_vector is not None:
            stage2 = self._matcher.stage2(candidate.context_embedding, existing_vectors)
            if stage2.outcome == "auto-merge-proposed":
                return _Flip(stage_reached=2, confidence=stage2.score, name_score=stage1.score)
        return None


def _with_target_first(
    alternatives: list[dict[str, object]],
    target_id: UUID,
    target_name: str,
    score: float,
) -> list[dict[str, object]]:
    """Surface the merge target at the head of the card's alternatives, deduped, capped at 3.

    The card renders `target_entity_id` plus a short "change to" list; placing the freshly
    accepted entity first keeps that list honest after a flip without re-querying the graph.
    """
    key = str(target_id)
    entry: dict[str, object] = {"entity_id": key, "canonical_name": target_name, "score": score}
    rest = [alt for alt in alternatives if str(alt.get("entity_id")) != key]
    return [entry, *rest][:3]
