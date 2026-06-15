"""Staging-store domain models for the M3 dedupe cascade (spec §3.3 / §7 steps 6–7).

Under **intercept-before-write** (DM6, ADR 0004) extraction no longer writes the graph.
Each extracted entity candidate is *staged* into Postgres carrying the §3.3 cascade's
proposal — NEW vs a MERGE target, with the stage it reached, a confidence, the judge's
reasoning, and the top-3 alternatives the Stage-4 reviewer chooses among. Neo4j is written
only when a human accepts at the review queue; that human action is INV-1's first enforcer
and the *only* graph-writing transition (INV-9 — no automated stage writes the graph).

These are the **persisted** shapes of the `[[candidate-lifecycle]]` state machine — pure
Pydantic/dataclasses, no I/O. The transient cascade states (`extracted`, `ambiguous`,
`auto-merge-proposed`, `new-proposed`) live only in memory while the cascade runs; by the
time a row is written it is at least `review-queued`, so the persisted `status` enum carries
only the resting + terminal states.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from story_forge.domain.graph import GraphEntity


def _now() -> datetime:
    return datetime.now(UTC)


# The persisted lifecycle states (`[[candidate-lifecycle]]`): a resting `review-queued`
# the queue reads, plus the three human-decided terminals. Closed — it is a state machine,
# not the open-world entity *type* taxonomy (INV-4).
CandidateStatus = Literal["review-queued", "merged", "created", "rejected"]

# The cascade's routing proposal for a staged candidate: a fresh entity, or a fold into an
# existing one. (The transient "ambiguous" routing is resolved before the row is written.)
CandidateProposal = Literal["new", "merge"]


class StagedCandidate(BaseModel):
    """One extracted candidate, staged with the cascade's proposal (spec §3.3 Stage 4).

    `context` is the ±200-char window the reviewer reads; `context_embedding` is its
    Stage-2 vector, copied onto the `entity_mention` at accept-time. `target_entity_id`
    references a **Neo4j** id (a soft cross-store key, no FK — the OQ-1 seam). `proposal` /
    `stage_reached` / `confidence` / `reasoning` / `alternatives` are the Stage-4 render set.
    """

    id: UUID = Field(default_factory=uuid4)
    project_id: UUID
    story_id: UUID
    paragraph_id: UUID
    candidate_name: str
    type: str
    properties: dict[str, object] = Field(default_factory=dict)
    context: str
    context_embedding: list[float] | None = None
    proposal: CandidateProposal
    target_entity_id: UUID | None = None
    stage_reached: int  # 1 (fuzzy), 2 (embedding), or 3 (judge) — how far the cascade ran
    confidence: float | None = None
    reasoning: str | None = None
    alternatives: list[dict[str, object]] = Field(default_factory=list)
    status: CandidateStatus = "review-queued"
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class CandidateDecision(BaseModel):
    """Append-only evidence of a human accept/reject (INV-3 reversibility, spec §11).

    A focused decisions log (DM-S4a-4) — *not* the §4.2 `edit_history` text-edit dataset,
    which is graph-decision-shaped here and is deferred to the editing milestone. Each row
    captures what the human decided, against which target, and the proposal they were shown.
    The matcher consults `rejected` rows so it does not re-pester the author (DM-rej).
    """

    id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    decision: Literal["created", "merged", "rejected"]
    target_entity_id: UUID | None = None
    actor: str = "human"
    shown_proposal: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


@dataclass(frozen=True)
class AcceptedSnapshot:
    """The already-accepted graph the cascade matches a candidate against (read once/run).

    Stage 2 of §3.3 matches a new candidate against *accepted* entities only — exactly
    right: a candidate is judged against what the author has already committed. Read once
    per ingest run (the C4 store-chatty mitigation): the entities from Neo4j, their stored
    mention vectors and a bounded sample of their mention texts from Postgres, all keyed by
    the entity's (Neo4j) id. Within a single run nothing is accepted, so the snapshot does
    not drift; across runs it is re-read.
    """

    entities: list[GraphEntity] = field(default_factory=list)
    mention_vectors: dict[UUID, list[list[float]]] = field(default_factory=dict)
    recent_mentions: dict[UUID, list[str]] = field(default_factory=dict)
