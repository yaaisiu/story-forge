"""MatchingAgent — Stage 1 of the §3.3 dedupe cascade (M3.S1).

Stage 1 is the cheapest cascade rung: a deterministic RapidFuzz token-set ratio of a
candidate's surface form against every existing entity's `canonical_name` + aliases.
No LLM, no network — like `PreNERAgent`, it imports its local-compute library
(RapidFuzz) directly rather than behind a Protocol (the layering rule targets
network/DB/provider I/O; ceremony for a single deterministic implementation buys
nothing — `backend/src/story_forge/AGENTS.md`). The reusable band logic that needs no
RapidFuzz (`classify`) is a pure function so the §3.3 thresholds are CI-tested without
any scoring call.

Stage 1 only *proposes*: it routes a candidate to one of three lifecycle states
(`[[candidate-lifecycle]]`) — `auto-merge-proposed` (≥ merge threshold), `ambiguous`
(handed to Stage 2), or `new-proposed`. Per INV-1 none of these touches the graph; a
human commits at Stage 4. Fail-closed: anything short of a confident match falls
through toward the human, never auto-merges (the cascade's whole reason to exist — a
diminutive like "Bronek"↔"Bronisław" must *not* be auto-merged on string distance).
"""

from __future__ import annotations

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


def classify(score: float, *, merge_threshold: float, ambiguous_floor: float) -> MatchOutcome:
    """Map a RapidFuzz score (0–100) to a §3.3 lifecycle state.

    Spec §3.3 bands: ≥ merge → MERGE proposal; [ambiguous_floor, merge) → ambiguous
    (Stage 2); < ambiguous_floor → NEW. Thresholds are inclusive at the lower edge so
    a score sitting exactly on the spec boundary takes the *more cautious* branch
    (85 → still a proposal not a silent skip; 60 → still escalated to Stage 2).
    """
    if score >= merge_threshold:
        return "auto-merge-proposed"
    if score >= ambiguous_floor:
        return "ambiguous"
    return "new-proposed"


class MatchingAgent:
    """Deterministic cascade matcher (Stage 1 fuzzy; Stage 2 embeddings follow)."""

    def __init__(
        self,
        *,
        merge_threshold: float | None = None,
        ambiguous_floor: float | None = None,
    ) -> None:
        # Spec §3.3 thresholds default from the one config home (DM1); constructor
        # overrides keep the agent unit-testable without touching global settings.
        self._merge_threshold = (
            settings.match_stage1_merge if merge_threshold is None else merge_threshold
        )
        self._ambiguous_floor = (
            settings.match_stage1_ambiguous_floor if ambiguous_floor is None else ambiguous_floor
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
