"""CandidateStager — the §3.3 dedupe cascade, run per paragraph at stage time (M3.S4a).

Under intercept-before-write the cascade no longer feeds a write; it attaches a *proposal*
to each extracted candidate before it is staged (`[[candidate-lifecycle]]`). This module is
the cascade glue: for one paragraph's `ExtractionProposal`, against the already-accepted
graph (`AcceptedSnapshot`), it runs

    derive ±200-char context → EmbeddingAgent.encode → MatchingAgent.stage1 / stage2
    → JudgeAgent.judge (only when Stages 1–2 leave a candidate ambiguous)

and returns the `StagedCandidate` rows + the paragraph's raw relation proposals. It does **no
I/O** itself (the snapshot is read once per run by the coordinator; the staging write is the
coordinator's) and depends only on injected Protocols, so it is unit-testable with fakes — the
same driver-vs-task seam as `ExtractionCoordinator`/`ExtractionAgent`.

**Fail-closed throughout** ([[fail-closed]]): a candidate that cannot be resolved routes
*toward the human* as a NEW proposal, never auto-commits and never crashes the batch. An
embedding failure drops Stage 2 (string Stage 1 + the LLM Stage 3 still run); a `JudgeError`
yields a NEW/"uncertain" proposal. The router's `BudgetExceededError`/`QuotaExhaustedError`
deliberately propagate (the coordinator catches them to pause-and-ask) — they are *not*
fail-closed cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from story_forge.agents.extraction_agent import EntityCandidate, ExtractionProposal
from story_forge.agents.judge_agent import ExistingEntityContext, JudgeError, Stage3Result
from story_forge.agents.matching_agent import (
    EntityVectors,
    ExistingEntity,
    Stage1Result,
    Stage2Result,
    top_alternatives,
)
from story_forge.domain.candidates import (
    AcceptedSnapshot,
    CandidateProposal,
    StagedCandidate,
)
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import Paragraph

CONTEXT_WINDOW = 200  # ±chars around the evidence quote (spec §3.3 Stage-4 "±200 chars")


class Embedder(Protocol):
    """The Stage-2 encoder the stager needs (an `EmbeddingAgent`)."""

    def encode(self, text: str) -> list[float]: ...


class Matcher(Protocol):
    """Stages 1 & 2 of the cascade (a `MatchingAgent`)."""

    def stage1(self, candidate_name: str, existing: list[ExistingEntity]) -> Stage1Result: ...
    def stage2(
        self, candidate_vector: list[float], existing: list[EntityVectors]
    ) -> Stage2Result: ...


class Judge(Protocol):
    """Stage 3, the LLM judge (a `JudgeAgent`)."""

    async def judge(
        self,
        *,
        candidate_name: str,
        candidate_context: str,
        candidate_type: str,
        candidate_properties: dict[str, object] | None = None,
        existing: ExistingEntityContext,
        language: str,
    ) -> Stage3Result: ...


@dataclass(frozen=True)
class StagedParagraph:
    """One paragraph's cascade result: the staged candidates + its raw relation proposals.

    Relations are kept as raw `RelationCandidate` dicts and written only at S4b: a relation
    can be committed to the graph only once *both* endpoints are accepted (which entity each
    resolves to is a post-review fact), so S4a stages the data but writes no edge.
    """

    candidates: list[StagedCandidate]
    relations: list[dict[str, object]]


@dataclass(frozen=True)
class _Outcome:
    """The cascade's verdict for one candidate (everything but the candidate's own fields)."""

    proposal: CandidateProposal
    target_entity_id: UUID | None
    stage_reached: int
    confidence: float | None
    reasoning: str | None


def derive_context(paragraph_text: str, evidence_quote: str | None) -> str:
    """The ±200-char window around the candidate's evidence quote (spec §3.3 Stage 4).

    Falls back to the whole paragraph when there is no quote, or the (already
    whitespace-grounded) quote does not locate exactly — the paragraph is always a safe,
    if wider, context for the reviewer and the embedding.
    """
    if evidence_quote:
        idx = paragraph_text.find(evidence_quote)
        if idx != -1:
            start = max(0, idx - CONTEXT_WINDOW)
            end = min(len(paragraph_text), idx + len(evidence_quote) + CONTEXT_WINDOW)
            return paragraph_text[start:end]
    return paragraph_text


def _canonical(entity: GraphEntity, language: str) -> str:
    """Pick the single name Stages 1/3 match against — project language first, peer fallback."""
    if language == "pl":
        return entity.canonical_name_pl or entity.canonical_name_en or ""
    return entity.canonical_name_en or entity.canonical_name_pl or ""


class CandidateStager:
    """Runs the §3.3 cascade over a paragraph's candidates and stages them, fail-closed."""

    def __init__(self, embedder: Embedder, matcher: Matcher, judge: Judge) -> None:
        self._embedder = embedder
        self._matcher = matcher
        self._judge = judge

    async def stage(
        self,
        *,
        proposal: ExtractionProposal,
        paragraph: Paragraph,
        project_id: UUID,
        story_id: UUID,
        language: str,
        snapshot: AcceptedSnapshot,
    ) -> StagedParagraph:
        """Attach a cascade proposal to each candidate and return the staged rows + relations."""
        existing = [_to_existing(e, language) for e in snapshot.entities]
        entity_vectors = [
            EntityVectors(id=str(e.id), mention_vectors=snapshot.mention_vectors.get(e.id, []))
            for e in snapshot.entities
        ]
        candidates: list[StagedCandidate] = []
        for candidate in proposal.entities:
            context = derive_context(paragraph.content, candidate.evidence_quote)
            vector = self._safe_encode(context)
            outcome = await self._cascade(
                candidate, context, vector, existing, entity_vectors, snapshot, language
            )
            candidates.append(
                StagedCandidate(
                    project_id=project_id,
                    story_id=story_id,
                    paragraph_id=paragraph.id,
                    candidate_name=candidate.candidate_name,
                    type=candidate.type,
                    properties=candidate.properties,
                    context=context,
                    context_embedding=vector,
                    proposal=outcome.proposal,
                    target_entity_id=outcome.target_entity_id,
                    stage_reached=outcome.stage_reached,
                    confidence=outcome.confidence,
                    reasoning=outcome.reasoning,
                    alternatives=top_alternatives(candidate.candidate_name, existing),
                )
            )
        relations = [relation.model_dump() for relation in proposal.relations]
        return StagedParagraph(candidates=candidates, relations=relations)

    def _safe_encode(self, text: str) -> list[float] | None:
        """Encode the context, or None on any embedder failure (fail-closed → drops Stage 2)."""
        try:
            return self._embedder.encode(text)
        except Exception:
            # A model-load / inference failure must not crash the batch or smuggle a NEW:
            # Stage 2 is simply skipped and the candidate still falls through to the human
            # (Stage 1 string match + Stage 3 judge, both vector-free). The mention written
            # at accept-time will carry no vector — acceptable; the next mention will.
            return None

    async def _cascade(
        self,
        candidate: EntityCandidate,
        context: str,
        vector: list[float] | None,
        existing: list[ExistingEntity],
        entity_vectors: list[EntityVectors],
        snapshot: AcceptedSnapshot,
        language: str,
    ) -> _Outcome:
        """Route one candidate through Stages 1→2→3; every exit is a *proposal*, never a write."""
        stage1 = self._matcher.stage1(candidate.candidate_name, existing)
        if stage1.outcome == "auto-merge-proposed":
            return _merge(stage1.target_entity_id, stage=1, confidence=stage1.score / 100.0)
        if stage1.outcome == "new-proposed":
            return _new(stage=1, confidence=stage1.score / 100.0)

        # Ambiguous after Stage 1 → Stage 2 (embedding), if a vector is available.
        target_id = stage1.target_entity_id
        stage_reached = 1
        if vector is not None:
            stage2 = self._matcher.stage2(vector, entity_vectors)
            stage_reached = 2
            if stage2.outcome == "auto-merge-proposed":
                return _merge(stage2.target_entity_id, stage=2, confidence=stage2.score)
            target_id = stage2.target_entity_id or target_id

        # Still ambiguous (or no vector) → Stage 3, the LLM judge, against the best match.
        target_entity = _find(snapshot.entities, target_id)
        if target_entity is None:
            return _new(
                stage=stage_reached, confidence=None, reasoning="uncertain (no judge target)"
            )
        try:
            stage3 = await self._judge.judge(
                candidate_name=candidate.candidate_name,
                candidate_context=context,
                candidate_type=candidate.type,
                candidate_properties=candidate.properties,
                existing=_to_context(target_entity, snapshot, language),
                language=language,
            )
        except JudgeError:
            # A flaky/unavailable judge falls through to the human, never auto-merges.
            return _new(stage=3, confidence=None, reasoning="uncertain (judge unavailable)")
        if stage3.outcome == "auto-merge-proposed":
            return _merge(
                stage3.target_entity_id,
                stage=3,
                confidence=stage3.verdict.confidence,
                reasoning=stage3.verdict.reasoning,
            )
        return _new(
            stage=3, confidence=stage3.verdict.confidence, reasoning=stage3.verdict.reasoning
        )


def _merge(
    target_entity_id: str | None,
    *,
    stage: int,
    confidence: float | None,
    reasoning: str | None = None,
) -> _Outcome:
    return _Outcome(
        proposal="merge",
        target_entity_id=UUID(target_entity_id) if target_entity_id else None,
        stage_reached=stage,
        confidence=confidence,
        reasoning=reasoning,
    )


def _new(*, stage: int, confidence: float | None, reasoning: str | None = None) -> _Outcome:
    return _Outcome(
        proposal="new",
        target_entity_id=None,
        stage_reached=stage,
        confidence=confidence,
        reasoning=reasoning,
    )


def _to_existing(entity: GraphEntity, language: str) -> ExistingEntity:
    return ExistingEntity(
        id=str(entity.id), canonical_name=_canonical(entity, language), aliases=entity.aliases
    )


def _to_context(
    entity: GraphEntity, snapshot: AcceptedSnapshot, language: str
) -> ExistingEntityContext:
    return ExistingEntityContext(
        id=str(entity.id),
        canonical_name=_canonical(entity, language),
        aliases=entity.aliases,
        type=entity.type,
        properties=entity.properties,
        recent_mentions=snapshot.recent_mentions.get(entity.id, []),
    )


def _find(entities: list[GraphEntity], entity_id: str | None) -> GraphEntity | None:
    if entity_id is None:
        return None
    for entity in entities:
        if str(entity.id) == entity_id:
            return entity
    return None
