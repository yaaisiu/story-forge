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
from typing import Any, Literal
from uuid import UUID, uuid4, uuid5

from pydantic import BaseModel, Field

from story_forge.domain.graph import GraphEntity

# A fixed namespace so an accepted candidate's graph id is a deterministic function of the
# candidate id — the basis of the accept-path retry-idempotency contract (same candidate →
# same entity/mention/decision id). Lives here (the persisted-shapes home) rather than in
# `agents/candidate_review.py` so both the accept path *and* relation-endpoint resolution
# derive a committed id from the one source (no drift — `[[idempotency]]`).
_ACCEPT_NS = UUID("a5f0c0de-0000-4000-8000-000000000001")

# Namespaces for the M3 relation slice (S4e). A *staged-relation* id is per-paragraph
# occurrence (one row per "this fact in this paragraph"); a *graph-edge* id is per the
# (subject, predicate, object) triple, so the same fact stated in two paragraphs collapses
# to one edge (DM-Rel-6). Distinct namespaces keep the two id spaces from ever colliding.
_REL_STAGE_NS = UUID("a5f0c0de-0000-4000-8000-000000000002")
_REL_EDGE_NS = UUID("a5f0c0de-0000-4000-8000-000000000003")


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
    Rejections are recorded here **so a future matcher can consult them** and not re-pester the
    author (DM-rej) — that consult is not built in S4a; this is the data it will read.
    """

    id: UUID = Field(default_factory=uuid4)
    candidate_id: UUID
    decision: Literal["created", "merged", "rejected"]
    target_entity_id: UUID | None = None
    actor: str = "human"
    shown_proposal: dict[str, object] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=_now)


def committed_entity_id(candidate: StagedCandidate) -> UUID | None:
    """The graph id a candidate resolves to once a human has committed it, else None.

    The inverse of the accept path's write: a `created` candidate's node lives at the
    deterministic accept id; a `merged` one folded into its chosen target. A still
    `review-queued` or `rejected` candidate has *no* committed entity, so it cannot anchor a
    relation endpoint (DM-Rel-2). Pure — the one home for this derivation, shared by the
    accept path (`agents/candidate_review.py`) and relation-endpoint resolution.
    """
    if candidate.status == "created":
        return uuid5(_ACCEPT_NS, f"entity:{candidate.id}")
    if candidate.status == "merged":
        return candidate.target_entity_id
    return None


def normalize_name(name: str) -> str:
    """The relation-endpoint match key (DM-Rel-2): casefold + strip whitespace.

    The LLM emitted both an entity candidate and a relation endpoint from the *same* text,
    so their surface forms align up to case/whitespace; this is the tightest rule that links
    them without the silent mis-links a fuzzy match would risk (`[[prefer-deterministic]]`).
    """
    return name.strip().casefold()


def staged_relation_id(paragraph_id: UUID, subject: str, predicate: str, object_: str) -> UUID:
    """Deterministic per-paragraph-occurrence id, so re-staging a paragraph is idempotent
    (`ON CONFLICT (id) DO NOTHING`). Keyed on the *surface* triple within one paragraph."""
    return uuid5(_REL_STAGE_NS, f"{paragraph_id}|{subject}|{predicate}|{object_}")


def relation_edge_id(subject_id: UUID, predicate: str, object_id: UUID) -> UUID:
    """Deterministic graph-edge id (DM-Rel-6): keyed on the *resolved* triple, so the same
    fact stated in two paragraphs MERGEs to one edge and a retried commit never doubles it."""
    return uuid5(_REL_EDGE_NS, f"{subject_id}|{predicate}|{object_id}")


# The staged relation's lifecycle (mirrors `CandidateStatus`): a resting `staged` the
# decide-relations queue resolves + the two human-decided terminals. Closed — a state
# machine, not the open-world relation *type* (INV-4).
RelationStatus = Literal["staged", "written", "rejected"]


class StagedRelation(BaseModel):
    """One extracted relation, staged with surface endpoints awaiting the §3.3 5th human
    action ("decide on relations", DM-Rel-1). Endpoints are *surface strings* (no entity id
    until both are resolved against accepted candidates); `subject_entity_id`/`object_entity_id`
    /`edge_id` fill in at commit. Mirrors `StagedCandidate`'s persisted shape — pure, no I/O.
    """

    id: UUID
    story_id: UUID
    paragraph_id: UUID
    subject: str
    predicate: str
    object: str
    confidence: float | None = None
    evidence_quote: str | None = None
    subject_entity_id: UUID | None = None
    object_entity_id: UUID | None = None
    edge_id: UUID | None = None
    status: RelationStatus = "staged"
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)

    @classmethod
    def from_proposal(
        cls,
        *,
        story_id: UUID,
        paragraph_id: UUID,
        relation: dict[str, Any],
    ) -> StagedRelation:
        """Build a staged row from a raw `RelationCandidate.model_dump()` dict (the JSONB
        shape extraction stages). Derives the deterministic per-paragraph id from the
        surface triple so re-staging is idempotent."""
        subject = str(relation["subject"])
        predicate = str(relation["predicate"])
        object_ = str(relation["object"])
        confidence = relation.get("confidence")
        evidence = relation.get("evidence_quote")
        return cls(
            id=staged_relation_id(paragraph_id, subject, predicate, object_),
            story_id=story_id,
            paragraph_id=paragraph_id,
            subject=subject,
            predicate=predicate,
            object=object_,
            confidence=float(confidence) if confidence is not None else None,
            evidence_quote=str(evidence) if evidence is not None else None,
        )


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
