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
    EntityVectors,
    ExistingEntity,
    MatchingAgent,
    classify,
    cosine_similarity,
    search_entities,
    top_alternatives,
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


# ── Pure cosine similarity (spec §3.3 Stage-2 distance math, no model) ────────


def test_cosine_identical_is_one() -> None:
    assert cosine_similarity([1.0, 2.0, 3.0], [1.0, 2.0, 3.0]) == pytest.approx(1.0)


def test_cosine_orthogonal_is_zero() -> None:
    assert cosine_similarity([1.0, 0.0], [0.0, 1.0]) == pytest.approx(0.0)


def test_cosine_opposite_is_minus_one() -> None:
    assert cosine_similarity([1.0, 1.0], [-1.0, -1.0]) == pytest.approx(-1.0)


def test_cosine_is_magnitude_invariant() -> None:
    # Scaling a vector leaves its direction — and so the cosine — unchanged.
    assert cosine_similarity([1.0, 2.0], [3.0, 6.0]) == pytest.approx(1.0)


def test_cosine_length_mismatch_raises() -> None:
    with pytest.raises(ValueError, match="length mismatch"):
        cosine_similarity([1.0, 2.0], [1.0])


def test_cosine_zero_vector_raises() -> None:
    with pytest.raises(ValueError, match="zero-magnitude"):
        cosine_similarity([0.0, 0.0], [1.0, 1.0])


# ── Stage 2 routing: max cosine vs an entity's mention vectors ───────────────


def test_stage2_close_context_proposes_merge(agent: MatchingAgent) -> None:
    # A candidate context whose vector matches a stored mention vector (cosine > 0.85)
    # is proposed for MERGE against that entity.
    result = agent.stage2(
        [1.0, 0.0, 0.0],
        existing=[EntityVectors(id="e-1", mention_vectors=[[1.0, 0.0, 0.0]])],
    )
    assert result.outcome == "auto-merge-proposed"
    assert result.target_entity_id == "e-1"
    assert result.score == pytest.approx(1.0)


def test_stage2_distant_context_escalates(agent: MatchingAgent) -> None:
    # Orthogonal context (cosine 0.0, well under 0.85) does NOT auto-merge — it
    # escalates to Stage 3, still carrying the best candidate entity for the judge.
    result = agent.stage2(
        [1.0, 0.0],
        existing=[EntityVectors(id="e-1", mention_vectors=[[0.0, 1.0]])],
    )
    assert result.outcome == "ambiguous"
    assert result.target_entity_id == "e-1"
    assert result.score == pytest.approx(0.0)


def test_stage2_picks_entity_with_highest_max_cosine(agent: MatchingAgent) -> None:
    # Across entities, Stage 2 takes the single best-scoring one; within an entity it
    # takes the max over its mention vectors (one good mention is enough to match).
    result = agent.stage2(
        [1.0, 0.0],
        existing=[
            EntityVectors(id="e-far", mention_vectors=[[0.0, 1.0], [-1.0, 0.0]]),
            EntityVectors(id="e-near", mention_vectors=[[0.0, 1.0], [1.0, 0.0]]),
        ],
    )
    assert result.target_entity_id == "e-near"
    assert result.score == pytest.approx(1.0)


def test_stage2_threshold_edge_is_strict(agent: MatchingAgent) -> None:
    # Spec §3.3 writes Stage-2 merge as "cosine > 0.85" — strict. A cosine sitting
    # exactly on the threshold escalates (the more fail-closed branch), mirroring
    # Stage 1's strict upper edge. Override the threshold to 1.0 so an identical
    # vector (cosine exactly 1.0) lands on the edge.
    strict = MatchingAgent(cosine_merge_threshold=1.0)
    result = strict.stage2(
        [1.0, 0.0],
        existing=[EntityVectors(id="e-1", mention_vectors=[[1.0, 0.0]])],
    )
    assert result.score == pytest.approx(1.0)
    assert result.outcome == "ambiguous"


def test_stage2_no_vectors_escalates(agent: MatchingAgent) -> None:
    # Stage 2 is only reached on an ambiguous Stage-1 match, but defensively: with no
    # entity vectors to compare against there is nothing to merge — escalate, no target.
    result = agent.stage2([1.0, 0.0], existing=[])
    assert result.outcome == "ambiguous"
    assert result.target_entity_id is None
    assert result.score == 0.0


def test_stage2_opposite_vector_still_selects_the_entity(agent: MatchingAgent) -> None:
    # An exactly-opposite mention (cosine -1.0) is a real comparison: the entity must
    # still be carried forward as the target (escalated, not merged), distinct from the
    # "no vectors to compare" case which carries none. Guards the sentinel: a -1.0
    # initial best would wrongly drop this entity and report "no target".
    result = agent.stage2(
        [1.0, 0.0],
        existing=[EntityVectors(id="e-1", mention_vectors=[[-1.0, 0.0]])],
    )
    assert result.outcome == "ambiguous"
    assert result.target_entity_id == "e-1"
    assert result.score == pytest.approx(-1.0)


# ── Manual-handpick search (M3.S4d) — same RapidFuzz signal as the matcher ────


def test_search_entities_ranks_by_fuzzy_score() -> None:
    # The author types "Bronek"; the search ranks accepted entities by the *same*
    # token_set_ratio the matcher uses, best first — so "search ≈ match".
    results = search_entities("Bronek", [KAZIMIERZ, BRONEK], limit=20)

    assert results[0]["entity_id"] == "e-bronek"  # best match leads
    assert results[0]["canonical_name"] == "Stary Bronek"
    assert results[0]["score"] >= results[-1]["score"]  # descending


def test_search_entities_keeps_low_score_match_reachable() -> None:
    # The feature's whole point: handpick must reach a duplicate the *matcher* missed.
    # A diminutive like "Kasia"↔"Katarzyna" scores low on token_set_ratio (~43, below the
    # cascade's bands) — yet it must NOT be filtered out, or the safety net has the same
    # blind spot the cascade does. There is no score floor; the human makes the pick.
    katarzyna = ExistingEntity(id="e-kat", canonical_name="Katarzyna", aliases=[])
    results = search_entities("Kasia", [katarzyna], limit=20)

    assert [r["entity_id"] for r in results] == ["e-kat"]


def test_search_entities_respects_limit() -> None:
    # The result cap bounds the payload (a top-N, no pagination — solo author).
    people = [ExistingEntity(id=f"e-{i}", canonical_name=f"Jan {i}", aliases=[]) for i in range(10)]
    results = search_entities("Jan", people, limit=3)

    assert len(results) == 3


def test_search_entities_blank_query_returns_empty() -> None:
    # A blank/whitespace query is not a search — short-circuit to [] (the hook
    # gates on a non-empty q, but the endpoint must be safe regardless).
    assert search_entities("", [BRONEK], limit=20) == []
    assert search_entities("   ", [BRONEK], limit=20) == []


def test_search_entities_matches_on_aliases() -> None:
    # The search scores against canonical_name *and* aliases, like the matcher — so a
    # folded-in surface form ("Bronek" is an alias of "Stary Bronek") still hits.
    results = search_entities("Bronek", [BRONEK], limit=20)

    assert results and results[0]["entity_id"] == "e-bronek"


def test_top_alternatives_still_returns_top_k_with_existing_shape() -> None:
    # Regression guard: top_alternatives keeps its {entity_id, canonical_name, score}
    # shape and top-k cut after the shared-ranking refactor that search_entities reuses.
    alts = top_alternatives("Bronek", [KAZIMIERZ, BRONEK], k=3)

    assert alts[0] == {
        "entity_id": "e-bronek",
        "canonical_name": "Stary Bronek",
        "score": alts[0]["score"],
    }
    assert len(alts) <= 3
