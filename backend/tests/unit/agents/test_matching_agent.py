"""Unit tests for the MatchingAgent Stage 1 (RapidFuzz) — spec §3.3, M3.S1.

Stage 1 is the cheapest cascade rung: a deterministic fuzzy match of a candidate's
surface form against every existing entity's `canonical_name` + aliases (no LLM, no
network). It only *proposes* — it routes a candidate to one of three lifecycle
states (`[[candidate-lifecycle]]`): `auto-merge-proposed` (>85%), `ambiguous`
(60–85%, handed to Stage 2), or `new-proposed` (<60%). Per INV-1, none of these
writes to the graph; the human commits at Stage 4.

These tests assert the *contract we own* — the §3.3 threshold bands and the
best-match wiring — not RapidFuzz's internal scoring. The band logic (`classify`)
is pure and tested directly against the spec thresholds with no RapidFuzz call; the
`stage1` tests use the Appendix B "Bronek" fixture to prove the agent picks the best
candidate and routes it through those bands.
"""

from __future__ import annotations

import pytest

from story_forge.agents.matching_agent import (
    ExistingEntity,
    MatchingAgent,
    classify,
)

# Appendix B characters, in the post-merge shape Stage 1 matches against: an entity
# carries a resolved `canonical_name` plus folded-in aliases (assigned at the M3
# human merge, §3.2). Stage 1 compares a new candidate's surface form against both.
BRONEK = ExistingEntity(id="e-bronek", canonical_name="Stary Bronek", aliases=["Bronek"])
KAZIMIERZ = ExistingEntity(
    id="e-kazimierz", canonical_name="stryj Kazimierz", aliases=["Kazimierz"]
)


# ── Pure band logic: spec §3.3 thresholds → lifecycle state (no RapidFuzz) ────


@pytest.mark.parametrize(
    ("score", "expected"),
    [
        (100.0, "auto-merge-proposed"),
        (85.1, "auto-merge-proposed"),  # strictly >85 → merge
        (85.0, "ambiguous"),  # exactly 85 is the TOP of the 60–85 band → Stage 2
        (84.9, "ambiguous"),
        (72.5, "ambiguous"),
        (60.0, "ambiguous"),  # ≥60 is the bottom of 60–85 → Stage 2 (boundary inclusive)
        (59.9, "new-proposed"),
        (12.0, "new-proposed"),
    ],
)
def test_classify_bands(score: float, expected: str) -> None:
    # Encodes §3.3 literally: >85 merge, 60–85 ambiguous, <60 new. Spec defaults.
    assert classify(score, merge_threshold=85.0, ambiguous_floor=60.0) == expected


# ── Stage 1 against real RapidFuzz scoring (Appendix B fixture) ───────────────


@pytest.fixture
def agent() -> MatchingAgent:
    """Spec-default thresholds (85 / 60); deterministic, no I/O."""
    return MatchingAgent()


def test_stage1_exact_alias_proposes_merge(agent: MatchingAgent) -> None:
    # "Bronek" is an existing alias of "Stary Bronek" → an unambiguous high score
    # that Stage 1 *should* catch on its own (the cheapest-rung win).
    result = agent.stage1("Bronek", existing=[KAZIMIERZ, BRONEK])

    assert result.outcome == "auto-merge-proposed"
    assert result.target_entity_id == "e-bronek"  # best match, not just *a* match
    assert result.score >= 85.0


def test_stage1_does_not_auto_merge_a_diminutive(agent: MatchingAgent) -> None:
    # The cascade's reason to exist: "Bronek" is the diminutive of the formal
    # "Bronisław" — the *same* person — but fuzzy string distance alone cannot
    # safely assert that. Stage 1 must therefore NOT auto-merge them; it falls
    # through toward Stage 2/3/human (fail-closed, INV-1). Asserting "not an
    # auto-merge" is robust to the exact score; silently merging here would be the
    # bug the embedding/judge stages exist to prevent.
    bronislaw = ExistingEntity(id="e-bron", canonical_name="Bronisław", aliases=[])
    result = agent.stage1("Bronek", existing=[bronislaw])

    assert result.outcome != "auto-merge-proposed"


def test_stage1_unrelated_candidate_proposes_new(agent: MatchingAgent) -> None:
    # A location surface form against a set of people scores far below 60 → NEW.
    result = agent.stage1("Czarna Hańcza", existing=[BRONEK, KAZIMIERZ])

    assert result.outcome == "new-proposed"
    assert result.target_entity_id is None


def test_stage1_empty_graph_proposes_new(agent: MatchingAgent) -> None:
    # With no existing entities there is nothing to merge into — every candidate is
    # NEW. (At M3.S1 the graph starts empty until the Stage-4 review queue lands.)
    result = agent.stage1("Bronek", existing=[])

    assert result.outcome == "new-proposed"
    assert result.target_entity_id is None
    assert result.score == 0.0
