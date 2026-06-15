"""Unit tests for the ReMatchService — on-accept intra-batch dedup (M3.S4c).

No I/O: a `FakeMatcher` stands in for the deterministic Stage 1/2 matcher and a
`FakeReMatchRepo` is an in-memory `candidates` store. These pin the re-match contract:
a strong match flips a still-pending candidate `new → merge` against the just-accepted
entity (spec §3.3 / DM-S4c-3); the flip is **monotone** (only `new → merge`, never the
reverse — DM-S4c-4) so re-running it is idempotent; re-match writes only the staging row
(it returns the flip count and calls `update_proposal`, never any graph writer).
"""

from __future__ import annotations

from uuid import UUID, uuid4

from story_forge.agents.candidate_rematch import ReMatchService
from story_forge.agents.matching_agent import Stage1Result, Stage2Result
from story_forge.domain.candidates import CandidateProposal, StagedCandidate

PROJECT = uuid4()
STORY = uuid4()
ACCEPTED_ID = uuid4()
ACCEPTED_NAME = "Janek"
VEC = [0.1] * 768


def _candidate(
    name: str,
    *,
    proposal: CandidateProposal = "new",
    vector: list[float] | None = None,
    alternatives: list[dict[str, object]] | None = None,
) -> StagedCandidate:
    return StagedCandidate(
        project_id=PROJECT,
        story_id=STORY,
        paragraph_id=uuid4(),
        candidate_name=name,
        type="Character",
        context=f"...{name}...",
        context_embedding=VEC if vector is None else vector,
        proposal=proposal,
        stage_reached=1,
        alternatives=alternatives or [],
    )


def _s1(outcome: str, score: float = 0.0) -> Stage1Result:
    return Stage1Result(outcome=outcome, target_entity_id=str(ACCEPTED_ID), score=score)  # type: ignore[arg-type]


def _s2(outcome: str, score: float = 0.0) -> Stage2Result:
    return Stage2Result(outcome=outcome, target_entity_id=str(ACCEPTED_ID), score=score)  # type: ignore[arg-type]


class FakeMatcher:
    """Returns a per-name Stage-1 verdict and a single Stage-2 verdict for any vector."""

    def __init__(self, stage1: dict[str, Stage1Result], stage2: Stage2Result | None = None) -> None:
        self._stage1 = stage1
        self._stage2 = stage2
        self.stage1_calls: list[str] = []
        self.stage2_calls = 0

    def stage1(self, candidate_name: str, existing: list[object]) -> Stage1Result:
        self.stage1_calls.append(candidate_name)
        return self._stage1[candidate_name]

    def stage2(self, candidate_vector: list[float], existing: list[object]) -> Stage2Result:
        self.stage2_calls += 1
        assert self._stage2 is not None, "stage2 was not expected to be called"
        return self._stage2


class FakeReMatchRepo:
    """In-memory `candidates` store: lists review-queued rows, mutates them in place."""

    def __init__(self, pending: list[StagedCandidate]) -> None:
        self._by_id = {c.id: c for c in pending}
        self.updates: list[dict[str, object]] = []

    async def list_pending(self, story_id: UUID) -> list[StagedCandidate]:
        return [c for c in self._by_id.values() if c.status == "review-queued"]

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
    ) -> None:
        c = self._by_id[candidate_id]
        c.proposal = proposal
        c.target_entity_id = target_entity_id
        c.stage_reached = stage_reached
        c.confidence = confidence
        c.reasoning = reasoning
        c.alternatives = alternatives
        self.updates.append(
            {
                "candidate_id": candidate_id,
                "proposal": proposal,
                "target_entity_id": target_entity_id,
                "stage_reached": stage_reached,
            }
        )


async def _rematch(
    matcher: FakeMatcher, repo: FakeReMatchRepo, *, vector: list[float] | None = VEC
) -> int:
    return await ReMatchService(matcher, repo).rematch(
        story_id=STORY,
        accepted_entity_id=ACCEPTED_ID,
        accepted_name=ACCEPTED_NAME,
        accepted_vector=vector,
    )


# --- the flip ---------------------------------------------------------------


async def test_stage1_strong_match_flips_new_to_merge() -> None:
    """A pending 'Janek' fuzz-matching the accepted 'Janek' flips new → merge (DM-S4c-3)."""
    pending = _candidate("Janek")
    repo = FakeReMatchRepo([pending])
    matcher = FakeMatcher({"Janek": _s1("auto-merge-proposed", score=100.0)})

    flipped = await _rematch(matcher, repo)

    assert flipped == 1
    assert pending.proposal == "merge"
    assert pending.target_entity_id == ACCEPTED_ID
    assert pending.stage_reached == 1
    assert matcher.stage2_calls == 0  # a Stage-1 hit short-circuits Stage 2
    # The accepted entity is surfaced first in the alternatives the card renders.
    assert pending.alternatives[0]["entity_id"] == str(ACCEPTED_ID)


async def test_stage2_cosine_flips_when_stage1_ambiguous() -> None:
    """Stage-1 ambiguous + Stage-2 cosine > 0.85 → flip (the semantic net, DM-S4c-3)."""
    pending = _candidate("Janusz")
    repo = FakeReMatchRepo([pending])
    matcher = FakeMatcher(
        {"Janusz": _s1("ambiguous", score=70.0)}, stage2=_s2("auto-merge-proposed", score=0.92)
    )

    flipped = await _rematch(matcher, repo)

    assert flipped == 1
    assert pending.proposal == "merge"
    assert pending.target_entity_id == ACCEPTED_ID
    assert pending.stage_reached == 2
    assert matcher.stage2_calls == 1


async def test_no_strong_match_leaves_proposal_untouched() -> None:
    """Stage-1 ambiguous + Stage-2 sub-threshold → no flip, no write (still a NEW)."""
    pending = _candidate("Bronek")
    repo = FakeReMatchRepo([pending])
    matcher = FakeMatcher(
        {"Bronek": _s1("ambiguous", score=70.0)}, stage2=_s2("ambiguous", score=0.40)
    )

    flipped = await _rematch(matcher, repo)

    assert flipped == 0
    assert pending.proposal == "new"
    assert pending.target_entity_id is None
    assert repo.updates == []


async def test_monotone_never_repoints_an_existing_merge() -> None:
    """A pending candidate already proposing merge is skipped — re-match only upgrades NEW."""
    pending = _candidate("Janek", proposal="merge")
    repo = FakeReMatchRepo([pending])
    matcher = FakeMatcher({"Janek": _s1("auto-merge-proposed", score=100.0)})

    flipped = await _rematch(matcher, repo)

    assert flipped == 0
    assert matcher.stage1_calls == []  # skipped before scoring
    assert repo.updates == []


async def test_stage1_only_when_no_vectors_available() -> None:
    """No accepted vector → Stage 2 is never run; only a Stage-1 fuzz hit can flip."""
    flips = _candidate("Janek")
    no_flip = _candidate("Bronek")
    repo = FakeReMatchRepo([flips, no_flip])
    matcher = FakeMatcher(
        {
            "Janek": _s1("auto-merge-proposed", score=100.0),
            "Bronek": _s1("ambiguous", score=70.0),  # would reach Stage 2, but no vector
        }
    )

    flipped = await _rematch(matcher, repo, vector=None)

    assert flipped == 1
    assert flips.proposal == "merge"
    assert no_flip.proposal == "new"
    assert matcher.stage2_calls == 0


async def test_rematch_is_idempotent_on_unchanged_accepted_set() -> None:
    """Re-running re-match flips nothing new — the once-flipped row is now merge, so skipped."""
    pending = _candidate("Janek")
    repo = FakeReMatchRepo([pending])
    matcher = FakeMatcher({"Janek": _s1("auto-merge-proposed", score=100.0)})

    first = await _rematch(matcher, repo)
    second = await _rematch(matcher, repo)

    assert first == 1
    assert second == 0
    assert len(repo.updates) == 1  # the proposal was written exactly once
