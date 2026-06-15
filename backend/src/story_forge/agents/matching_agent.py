"""MatchingAgent — Stages 1 & 2 of the §3.3 dedupe cascade (M3.S1–S2).

Stage 1 is the cheapest cascade rung: a deterministic RapidFuzz token-set ratio of a
candidate's surface form against every existing entity's `canonical_name` + aliases.
Stage 2 is the next: the max cosine of a candidate's context vector (produced by
`EmbeddingAgent`) against an entity's stored mention vectors. Both are deterministic,
local compute — no LLM, no network — so, like `PreNERAgent`, this module imports its
local libraries (RapidFuzz; plain `math` for cosine) directly rather than behind a
Protocol (the layering rule targets network/DB/provider I/O; ceremony for a single
deterministic implementation buys nothing — `backend/src/story_forge/AGENTS.md`). The
pure band/distance helpers (`classify`, `cosine_similarity`) need neither RapidFuzz nor
a model, so the §3.3 thresholds are CI-tested without any scoring or embedding call.

Both stages only *propose* and never touch the graph (INV-1; a human commits at Stage 4).
Stage 1 routes a candidate to `auto-merge-proposed` (> merge threshold), `ambiguous`
(handed to Stage 2), or `new-proposed` (< ambiguous floor). Stage 2, reached only on an
ambiguous Stage-1 match, routes to `auto-merge-proposed` (cosine > 0.85) or `ambiguous`
(escalate to the Stage-3 judge). Fail-closed throughout: anything short of a confident
match falls through toward the human, never auto-merges (the cascade's whole reason to
exist — a diminutive like "Bronek"↔"Bronisław" must *not* be auto-merged on string
distance).

Both stages are built proposal-only and *unwired* through M3.S2–S3; the cascade is wired
into the live extraction path with the review queue + the DM6 write-path refactor (M3.S4).
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from typing import Literal

from pydantic import BaseModel, Field
from rapidfuzz import fuzz

from story_forge.config import settings

# The closed set of Stage-1 lifecycle states (`[[candidate-lifecycle]]`). Closed —
# unlike the open-world entity *type* (INV-4) — because it is a state machine, not a
# taxonomy: a candidate is in exactly one of these three after Stage 1.
MatchOutcome = Literal["auto-merge-proposed", "ambiguous", "new-proposed"]


class ExistingEntity(BaseModel):
    """An entity already in the graph, in the shape Stage 1 matches against.

    `canonical_name` is the resolved name assigned at the M3 human merge (§3.2);
    `aliases` are the surface forms folded in on prior merges. Stage 1 scores the
    candidate against the canonical name *and* every alias, taking the best.
    """

    id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)


class Stage1Result(BaseModel):
    """Stage 1's proposal for one candidate — a routing decision, never a write."""

    outcome: MatchOutcome
    target_entity_id: str | None = None
    score: float = 0.0


class EntityVectors(BaseModel):
    """An existing entity's stored mention vectors, the shape Stage 2 matches against.

    Each entity accumulates one context vector per recorded mention (§3.3 Stage 2,
    DM3/DM4). Stage 2 scores the candidate against *every* mention vector and keeps the
    best — one strongly-matching mention is enough to propose a merge.
    """

    id: str
    mention_vectors: list[list[float]] = Field(default_factory=list)


class Stage2Result(BaseModel):
    """Stage 2's proposal for one candidate — merge or escalate, never a write.

    `outcome` is only ever `auto-merge-proposed` or `ambiguous`: Stage 2 cannot produce
    `new-proposed` (that is Stage 1's <floor branch). `score` is the max cosine in
    [-1, 1] of the best-matching entity.
    """

    outcome: MatchOutcome
    target_entity_id: str | None = None
    score: float = 0.0


def cosine_similarity(a: Sequence[float], b: Sequence[float]) -> float:
    """Cosine similarity of two equal-length vectors, in [-1.0, 1.0].

    Pure — no model — so the §3.3 Stage-2 distance math is unit-tested in CI without
    loading the ~2 GB embedding stack. Raises on a length mismatch (a candidate vector
    and a stored mention vector must share the model's dimensionality) and on a
    zero-magnitude vector (cosine is undefined there; a real embedding is never all-zero).
    """
    if len(a) != len(b):
        raise ValueError(f"vector length mismatch: {len(a)} != {len(b)}")
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    if norm_a == 0.0 or norm_b == 0.0:
        raise ValueError("cosine similarity is undefined for a zero-magnitude vector")
    return dot / (norm_a * norm_b)


def top_alternatives(
    candidate_name: str, existing: list[ExistingEntity], *, k: int = 3
) -> list[dict[str, object]]:
    """The k best-scoring existing entities for a candidate, for the Stage-4 reviewer.

    Spec §3.3 Stage 4 shows the human "top-3 alternative existing entities to choose from"
    alongside the cascade's own proposal. This is a pure RapidFuzz ranking over the same
    canonical_name + aliases signal Stage 1 uses (a second cheap local pass — no I/O), so
    the staged candidate carries the alternatives the review UI (S4b) renders without
    re-querying the graph. Empty graph → empty list.
    """
    scored: list[tuple[float, str, str]] = []
    for entity in existing:
        names = [entity.canonical_name, *entity.aliases]
        best = max((fuzz.token_set_ratio(candidate_name, name) for name in names), default=0.0)
        scored.append((best, entity.id, entity.canonical_name))
    scored.sort(key=lambda row: row[0], reverse=True)
    return [
        {"entity_id": entity_id, "canonical_name": name, "score": score}
        for score, entity_id, name in scored[:k]
    ]


def classify(score: float, *, merge_threshold: float, ambiguous_floor: float) -> MatchOutcome:
    """Map a RapidFuzz score (0–100) to a §3.3 lifecycle state.

    Spec §3.3 bands, literally: ``> merge`` → MERGE proposal; ``[ambiguous_floor,
    merge]`` → ambiguous (Stage 2); ``< ambiguous_floor`` → NEW. The upper edge is
    *strict* (`>`), so a score sitting exactly on the spec's 85 boundary is NOT
    auto-merged — it escalates to Stage 2, the more fail-closed branch (the spec
    writes merge as "> 85%" and the 85 itself as part of the "60–85%" Stage-2 band).
    The lower edge is inclusive (`>=`): 60 is the bottom of "60–85%", still ambiguous.
    """
    if score > merge_threshold:
        return "auto-merge-proposed"
    if score >= ambiguous_floor:
        return "ambiguous"
    return "new-proposed"


class MatchingAgent:
    """Deterministic cascade matcher (Stage 1 fuzzy + Stage 2 embedding cosine; judge follows)."""

    def __init__(
        self,
        *,
        merge_threshold: float | None = None,
        ambiguous_floor: float | None = None,
        cosine_merge_threshold: float | None = None,
    ) -> None:
        # Spec §3.3 thresholds default from the one config home (DM1); constructor
        # overrides keep the agent unit-testable without touching global settings.
        self._merge_threshold = (
            settings.match_stage1_merge if merge_threshold is None else merge_threshold
        )
        self._ambiguous_floor = (
            settings.match_stage1_ambiguous_floor if ambiguous_floor is None else ambiguous_floor
        )
        self._cosine_merge = (
            settings.match_stage2_cosine_merge
            if cosine_merge_threshold is None
            else cosine_merge_threshold
        )

    def stage1(self, candidate_name: str, existing: list[ExistingEntity]) -> Stage1Result:
        """Fuzzy-match a candidate against existing entities; route by §3.3 bands.

        Scores the candidate against each entity's canonical_name + aliases with
        RapidFuzz token-set ratio (order-insensitive, tolerant of extra tokens like
        the honorific in "Stary Bronek"), keeps the single best-scoring entity, and
        classifies. An empty graph (or no scorable name) yields NEW with no target.
        """
        best_id: str | None = None
        best_score = 0.0
        for entity in existing:
            names = [entity.canonical_name, *entity.aliases]
            entity_best = max(
                (fuzz.token_set_ratio(candidate_name, name) for name in names),
                default=0.0,
            )
            if entity_best > best_score:
                best_score = entity_best
                best_id = entity.id

        outcome = classify(
            best_score,
            merge_threshold=self._merge_threshold,
            ambiguous_floor=self._ambiguous_floor,
        )
        # A NEW proposal has no merge target; only merge/ambiguous carry one forward.
        target = None if outcome == "new-proposed" else best_id
        return Stage1Result(outcome=outcome, target_entity_id=target, score=best_score)

    def stage2(self, candidate_vector: list[float], existing: list[EntityVectors]) -> Stage2Result:
        """Embedding-match a candidate's context vector; route by the §3.3 cosine band.

        For each existing entity, take the max cosine of the candidate against its
        mention vectors; keep the single best-scoring entity. Cosine strictly above the
        merge threshold (spec §3.3: > 0.85) → MERGE proposal against that entity; at or
        below it → ambiguous, escalated to the Stage-3 judge but still carrying the best
        entity as the comparison target. The strict upper edge mirrors Stage 1: a score
        exactly on the threshold escalates (the more fail-closed branch).

        Stage 2 is reached only on an ambiguous Stage-1 match, so there is normally a
        candidate entity; defensively, no entity with any mention vector yields an
        escalation with no target (nothing to merge into).
        """
        best_id: str | None = None
        best_score = float("-inf")  # below any cosine, so the first real comparison wins
        for entity in existing:
            entity_best = max(
                (cosine_similarity(candidate_vector, v) for v in entity.mention_vectors),
                default=None,
            )
            if entity_best is not None and entity_best > best_score:
                best_score = entity_best
                best_id = entity.id

        if best_id is None:
            return Stage2Result(outcome="ambiguous", target_entity_id=None, score=0.0)

        outcome: MatchOutcome = (
            "auto-merge-proposed" if best_score > self._cosine_merge else "ambiguous"
        )
        return Stage2Result(outcome=outcome, target_entity_id=best_id, score=best_score)
