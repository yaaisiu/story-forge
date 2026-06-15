"""Unit tests for the CandidateStager — the §3.3 cascade glue (M3.S4a).

No I/O: fakes stand in for the embedder, matcher, and judge, and the accepted graph is a
hand-built `AcceptedSnapshot`. These pin the cascade *routing* (Stage 1 → 2 → 3 short-circuits)
and the [[fail-closed]] contract (an embedding/judge failure routes the candidate toward the
human as NEW, never crashes; a budget pause propagates).
"""

from __future__ import annotations

from uuid import uuid4

import pytest

from story_forge.adapters.llm.base import BudgetExceededError
from story_forge.agents.candidate_staging import CandidateStager, derive_context
from story_forge.agents.extraction_agent import (
    EntityCandidate,
    ExtractionProposal,
    RelationCandidate,
)
from story_forge.agents.judge_agent import JudgeError, JudgeVerdict, Stage3Result
from story_forge.agents.matching_agent import Stage1Result, Stage2Result
from story_forge.domain.candidates import AcceptedSnapshot
from story_forge.domain.graph import GraphEntity
from story_forge.domain.models import Paragraph

LANG = "pl"
PROJECT = uuid4()
STORY = uuid4()
VEC = [0.1] * 768


def _para(content: str = "Bronek walked to the mill.") -> Paragraph:
    return Paragraph(scene_id=uuid4(), order_index=0, content=content)


def _proposal(name: str = "Bronek") -> ExtractionProposal:
    return ExtractionProposal(
        entities=[EntityCandidate(candidate_name=name, type="Character", match_confidence=0.5)]
    )


def _entity() -> GraphEntity:
    return GraphEntity(
        type="Character", canonical_name_pl="Bronisław", aliases=["Bronek"], project_id=PROJECT
    )


class FakeEmbedder:
    def __init__(self, *, vector: list[float] | None = None, exc: Exception | None = None) -> None:
        self._vector = vector if vector is not None else VEC
        self._exc = exc
        self.calls = 0

    def encode(self, text: str) -> list[float]:
        self.calls += 1
        if self._exc is not None:
            raise self._exc
        return self._vector


class FakeMatcher:
    def __init__(self, s1: Stage1Result, s2: Stage2Result | None = None) -> None:
        self._s1 = s1
        self._s2 = s2
        self.stage2_called = False

    def stage1(self, candidate_name: str, existing: list[object]) -> Stage1Result:
        return self._s1

    def stage2(self, candidate_vector: list[float], existing: list[object]) -> Stage2Result:
        self.stage2_called = True
        assert self._s2 is not None, "stage2 was not expected to be called"
        return self._s2


class FakeJudge:
    def __init__(self, result: Stage3Result | None = None, exc: Exception | None = None) -> None:
        self._result = result
        self._exc = exc
        self.called = False

    async def judge(self, **kwargs: object) -> Stage3Result:
        self.called = True
        if self._exc is not None:
            raise self._exc
        assert self._result is not None
        return self._result


def _snapshot(entity: GraphEntity | None = None) -> AcceptedSnapshot:
    if entity is None:
        return AcceptedSnapshot()
    return AcceptedSnapshot(
        entities=[entity],
        mention_vectors={entity.id: [VEC]},
        recent_mentions={entity.id: ["Bronek was here."]},
    )


async def _stage(stager: CandidateStager, snapshot: AcceptedSnapshot, proposal=None):
    return await stager.stage(
        proposal=proposal or _proposal(),
        paragraph=_para(),
        project_id=PROJECT,
        story_id=STORY,
        language=LANG,
        snapshot=snapshot,
    )


# --- routing ---------------------------------------------------------------


async def test_stage1_auto_merge_short_circuits_the_judge() -> None:
    e = _entity()
    judge = FakeJudge()
    matcher = FakeMatcher(
        Stage1Result(outcome="auto-merge-proposed", target_entity_id=str(e.id), score=92.0)
    )
    staged = await _stage(CandidateStager(FakeEmbedder(), matcher, judge), _snapshot(e))

    c = staged.candidates[0]
    assert c.proposal == "merge"
    assert c.target_entity_id == e.id
    assert c.stage_reached == 1
    assert matcher.stage2_called is False
    assert judge.called is False


async def test_stage1_new_proposed_short_circuits() -> None:
    matcher = FakeMatcher(Stage1Result(outcome="new-proposed", target_entity_id=None, score=10.0))
    judge = FakeJudge()
    staged = await _stage(CandidateStager(FakeEmbedder(), matcher, judge), _snapshot())

    c = staged.candidates[0]
    assert c.proposal == "new"
    assert c.target_entity_id is None
    assert c.stage_reached == 1
    assert judge.called is False


async def test_stage2_auto_merge_short_circuits_the_judge() -> None:
    e = _entity()
    matcher = FakeMatcher(
        Stage1Result(outcome="ambiguous", target_entity_id=str(e.id), score=70.0),
        Stage2Result(outcome="auto-merge-proposed", target_entity_id=str(e.id), score=0.91),
    )
    judge = FakeJudge()
    staged = await _stage(CandidateStager(FakeEmbedder(), matcher, judge), _snapshot(e))

    c = staged.candidates[0]
    assert c.proposal == "merge"
    assert c.stage_reached == 2
    assert matcher.stage2_called is True
    assert judge.called is False


async def test_ambiguous_through_stage3_merge() -> None:
    e = _entity()
    matcher = FakeMatcher(
        Stage1Result(outcome="ambiguous", target_entity_id=str(e.id), score=70.0),
        Stage2Result(outcome="ambiguous", target_entity_id=str(e.id), score=0.5),
    )
    judge = FakeJudge(
        Stage3Result(
            outcome="auto-merge-proposed",
            target_entity_id=str(e.id),
            verdict=JudgeVerdict(match=True, confidence=0.95, reasoning="same diminutive"),
        )
    )
    staged = await _stage(CandidateStager(FakeEmbedder(), matcher, judge), _snapshot(e))

    c = staged.candidates[0]
    assert c.proposal == "merge"
    assert c.target_entity_id == e.id
    assert c.stage_reached == 3
    assert c.reasoning == "same diminutive"
    assert judge.called is True


async def test_ambiguous_through_stage3_new() -> None:
    e = _entity()
    matcher = FakeMatcher(
        Stage1Result(outcome="ambiguous", target_entity_id=str(e.id), score=70.0),
        Stage2Result(outcome="ambiguous", target_entity_id=str(e.id), score=0.5),
    )
    judge = FakeJudge(
        Stage3Result(
            outcome="new-proposed",
            target_entity_id=None,
            verdict=JudgeVerdict(match=False, confidence=0.9, reasoning="different person"),
        )
    )
    staged = await _stage(CandidateStager(FakeEmbedder(), matcher, judge), _snapshot(e))

    c = staged.candidates[0]
    assert c.proposal == "new"
    assert c.stage_reached == 3


# --- fail-closed -----------------------------------------------------------


async def test_embedding_failure_drops_stage2_and_falls_through_to_judge() -> None:
    e = _entity()
    matcher = FakeMatcher(Stage1Result(outcome="ambiguous", target_entity_id=str(e.id), score=70.0))
    judge = FakeJudge(
        Stage3Result(
            outcome="new-proposed",
            target_entity_id=None,
            verdict=JudgeVerdict(match=False, confidence=0.7, reasoning="unclear"),
        )
    )
    embedder = FakeEmbedder(exc=RuntimeError("model failed to load"))
    staged = await _stage(CandidateStager(embedder, matcher, judge), _snapshot(e))

    c = staged.candidates[0]
    # Stage 2 skipped (no vector), but the candidate is still staged via the judge — never NEW
    # by silent default, never a crash.
    assert matcher.stage2_called is False
    assert judge.called is True
    assert c.proposal == "new"
    assert c.context_embedding is None


async def test_judge_failure_stages_uncertain_new() -> None:
    e = _entity()
    matcher = FakeMatcher(
        Stage1Result(outcome="ambiguous", target_entity_id=str(e.id), score=70.0),
        Stage2Result(outcome="ambiguous", target_entity_id=str(e.id), score=0.5),
    )
    judge = FakeJudge(exc=JudgeError("router gave up"))
    staged = await _stage(CandidateStager(FakeEmbedder(), matcher, judge), _snapshot(e))

    c = staged.candidates[0]
    assert c.proposal == "new"
    assert c.stage_reached == 3
    assert c.reasoning is not None and "uncertain" in c.reasoning


async def test_budget_error_from_judge_propagates() -> None:
    e = _entity()
    matcher = FakeMatcher(
        Stage1Result(outcome="ambiguous", target_entity_id=str(e.id), score=70.0),
        Stage2Result(outcome="ambiguous", target_entity_id=str(e.id), score=0.5),
    )
    judge = FakeJudge(exc=BudgetExceededError("daily budget reached"))
    stager = CandidateStager(FakeEmbedder(), matcher, judge)

    # A budget pause is NOT a fail-closed case — it must propagate so the coordinator pauses.
    with pytest.raises(BudgetExceededError):
        await _stage(stager, _snapshot(e))


# --- staging shape ---------------------------------------------------------


async def test_relations_are_staged_as_dicts() -> None:
    matcher = FakeMatcher(Stage1Result(outcome="new-proposed", target_entity_id=None, score=0.0))
    proposal = ExtractionProposal(
        entities=[EntityCandidate(candidate_name="Janek", type="Character", match_confidence=0.5)],
        relations=[
            RelationCandidate(subject="Janek", predicate="LIVES_IN", object="Mill", confidence=0.8)
        ],
    )
    staged = await _stage(
        CandidateStager(FakeEmbedder(), matcher, FakeJudge()), _snapshot(), proposal
    )

    assert len(staged.relations) == 1
    assert staged.relations[0]["predicate"] == "LIVES_IN"


async def test_alternatives_are_populated_from_existing_entities() -> None:
    e = _entity()
    matcher = FakeMatcher(Stage1Result(outcome="new-proposed", target_entity_id=None, score=0.0))
    staged = await _stage(CandidateStager(FakeEmbedder(), matcher, FakeJudge()), _snapshot(e))

    alts = staged.candidates[0].alternatives
    assert alts and alts[0]["entity_id"] == str(e.id)


def test_derive_context_windows_around_the_quote() -> None:
    text = "x" * 300 + "QUOTE" + "y" * 300
    ctx = derive_context(text, "QUOTE")
    assert "QUOTE" in ctx
    assert len(ctx) == 200 + len("QUOTE") + 200  # ±200 around the quote


def test_derive_context_falls_back_to_whole_paragraph() -> None:
    text = "a short paragraph with no locatable quote"
    assert derive_context(text, None) == text
    assert derive_context(text, "absent") == text
