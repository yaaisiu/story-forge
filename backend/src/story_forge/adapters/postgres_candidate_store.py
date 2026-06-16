"""PostgresCandidateStore — the `candidates` staging store + the review/accept ops (M3.S4a).

Backs the intercept-before-write write path (DM6, ADR 0004): extraction stages candidates
here instead of writing the graph, and the human-review endpoints read/accept/reject through
the same store. Like `PostgresMentionStore`, each operation opens its own short-lived
connection rather than sharing the request transaction — that is what makes the batch ingest
resumable: a paragraph's candidates + its `paragraph_processed` marker are committed together
as one atomic unit, so a mid-batch pause or crash leaves a durable record of which paragraphs
are already staged (the resume checkpoint, OQ-1/DM-S4a-3).

The accept-path write order (Neo4j → mention → evidence → status-flip) lives in the
`CandidateReviewService`; this store provides only the individual Postgres operations it
sequences (`get`, `set_status`, `insert_decision`) plus the queue read (`list_pending`).
"""

from __future__ import annotations

from uuid import UUID

import psycopg
from pgvector import Vector
from psycopg.rows import class_row
from psycopg.types.json import Jsonb

from story_forge.adapters.db import connect, libpq_kwargs
from story_forge.adapters.postgres_relation_store import PostgresRelationStore
from story_forge.config import settings
from story_forge.domain.candidates import (
    CandidateDecision,
    CandidateProposal,
    CandidateStatus,
    StagedCandidate,
    StagedRelation,
)

_CANDIDATE_COLUMNS = (
    "id, project_id, story_id, paragraph_id, candidate_name, type, properties, context, "
    "context_embedding, proposal, target_entity_id, stage_reached, confidence, reasoning, "
    "alternatives, status, created_at, updated_at"
)


class PostgresCandidateStore:
    """`CandidateStore` (+ review ops) backed by the `candidates` / `candidate_decisions` tables."""

    def __init__(self, conninfo: dict[str, object] | None = None) -> None:
        self._conninfo = conninfo if conninfo is not None else libpq_kwargs(settings.database_url)

    async def _connect(self, *, autocommit: bool = False) -> psycopg.AsyncConnection:
        # Via db.connect so the pgvector type is registered (the `context_embedding vector(768)`
        # column needs the dumper on write and the loader on read).
        return await connect(self._conninfo, autocommit=autocommit)

    # --- Staging (the extract path) ----------------------------------------

    async def persist(
        self,
        *,
        paragraph_id: UUID,
        story_id: UUID,
        candidates: list[StagedCandidate],
        relations: list[dict[str, object]],
    ) -> None:
        """Stage a paragraph's candidates + relations + its resume marker atomically (one txn).

        The marker is written even for a zero-candidate paragraph, so a re-run skips it.
        `ON CONFLICT DO NOTHING` on the marker keeps a defensive re-persist idempotent. Since
        M3.S4e relations are staged into `staged_relations` (so they carry a lifecycle) rather
        than the `paragraph_processed.relations` JSONB, which is now left empty (vestigial).
        """
        async with await self._connect() as conn:  # autocommit=False → commits on clean exit
            for candidate in candidates:
                await self._insert_candidate(conn, candidate)
            for relation in relations:
                await PostgresRelationStore.insert(
                    conn,
                    StagedRelation.from_proposal(
                        story_id=story_id, paragraph_id=paragraph_id, relation=relation
                    ),
                )
            await conn.execute(
                "INSERT INTO paragraph_processed (paragraph_id, story_id) "
                "VALUES (%s, %s) ON CONFLICT (paragraph_id) DO NOTHING",
                (paragraph_id, story_id),
            )

    @staticmethod
    async def _insert_candidate(conn: psycopg.AsyncConnection, candidate: StagedCandidate) -> None:
        await conn.execute(
            f"INSERT INTO candidates ({_CANDIDATE_COLUMNS}) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
            (
                candidate.id,
                candidate.project_id,
                candidate.story_id,
                candidate.paragraph_id,
                candidate.candidate_name,
                candidate.type,
                Jsonb(candidate.properties),
                candidate.context,
                None
                if candidate.context_embedding is None
                else Vector(candidate.context_embedding),
                candidate.proposal,
                candidate.target_entity_id,
                candidate.stage_reached,
                candidate.confidence,
                candidate.reasoning,
                Jsonb(candidate.alternatives),
                candidate.status,
                candidate.created_at,
                candidate.updated_at,
            ),
        )

    async def paragraphs_processed(self, paragraph_ids: list[UUID]) -> set[UUID]:
        """Which of `paragraph_ids` are already staged — the resume checkpoint."""
        if not paragraph_ids:
            return set()
        async with await self._connect(autocommit=True) as conn:
            cur = await conn.execute(
                "SELECT paragraph_id FROM paragraph_processed WHERE paragraph_id = ANY(%s)",
                (paragraph_ids,),
            )
            rows = await cur.fetchall()
        return {row[0] for row in rows}

    # --- Review (the accept/reject path) -----------------------------------

    async def list_pending(self, story_id: UUID) -> list[StagedCandidate]:
        """The review queue (spec §3.3 Stage 4): a story's candidates still awaiting a human."""
        async with await self._connect(autocommit=True) as conn:
            cur = conn.cursor(row_factory=class_row(StagedCandidate))
            await cur.execute(
                f"SELECT {_CANDIDATE_COLUMNS} FROM candidates "
                "WHERE story_id = %s AND status = 'review-queued' ORDER BY created_at",
                (story_id,),
            )
            return await cur.fetchall()

    async def list_accepted(self, story_id: UUID) -> list[StagedCandidate]:
        """A story's committed candidates (`created`/`merged`) — the set a relation resolves
        its surface endpoints against (M3.S4e, DM-Rel-2). Rejected/queued rows have no
        committed entity, so they cannot anchor an endpoint and are excluded."""
        async with await self._connect(autocommit=True) as conn:
            cur = conn.cursor(row_factory=class_row(StagedCandidate))
            await cur.execute(
                f"SELECT {_CANDIDATE_COLUMNS} FROM candidates "
                "WHERE story_id = %s AND status IN ('created', 'merged') ORDER BY created_at",
                (story_id,),
            )
            return await cur.fetchall()

    async def get(self, candidate_id: UUID) -> StagedCandidate | None:
        async with await self._connect(autocommit=True) as conn:
            cur = conn.cursor(row_factory=class_row(StagedCandidate))
            await cur.execute(
                f"SELECT {_CANDIDATE_COLUMNS} FROM candidates WHERE id = %s",
                (candidate_id,),
            )
            return await cur.fetchone()

    async def insert_decision(self, decision: CandidateDecision) -> None:
        """Append an accept/reject evidence row (INV-3; rejections recorded for a future
        matcher consult — DM-rej, not built in S4a)."""
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                "INSERT INTO candidate_decisions "
                "(id, candidate_id, decision, target_entity_id, actor, shown_proposal, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (
                    decision.id,
                    decision.candidate_id,
                    decision.decision,
                    decision.target_entity_id,
                    decision.actor,
                    Jsonb(decision.shown_proposal),
                    decision.created_at,
                ),
            )

    async def set_status(
        self,
        candidate_id: UUID,
        status: CandidateStatus,
        *,
        target_entity_id: UUID | None = None,
    ) -> None:
        """Flip a candidate's lifecycle status — the **last** write on the accept path.

        Done after the Neo4j + mention + evidence writes, so an un-flipped candidate is always
        safely retryable (the accept-path idempotency contract). Returns silently if the row
        is gone. On a **merge accept** the caller passes the *committed* `target_entity_id` so
        the row reflects the entity actually merged into — which may differ from the staged
        proposal when the reviewer **changed the merge target** (§3.3). Persisting it keeps
        `committed_entity_id` honest, so relation-endpoint resolution (M3.S4e) and the
        terminal-noop re-read resolve to the entity the human chose, not the stale proposal.
        """
        async with await self._connect(autocommit=True) as conn:
            if target_entity_id is not None:
                await conn.execute(
                    "UPDATE candidates SET status = %s, target_entity_id = %s, "
                    "updated_at = now() WHERE id = %s",
                    (status, target_entity_id, candidate_id),
                )
            else:
                await conn.execute(
                    "UPDATE candidates SET status = %s, updated_at = now() WHERE id = %s",
                    (status, candidate_id),
                )

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
        """Re-stage a still-pending candidate's cascade proposal (M3.S4c on-accept re-match).

        The only writer of a staged proposal *after* staging. The `status = 'review-queued'`
        guard makes it a no-op on any terminal row — defence-in-depth for the monotone /
        never-resurface-a-decision contract, on top of the service's own `proposal == 'new'`
        guard. Writes only the `candidates` table (no graph, no evidence row): INV-9 holds.
        """
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                "UPDATE candidates SET proposal = %s, target_entity_id = %s, "
                "stage_reached = %s, confidence = %s, reasoning = %s, alternatives = %s, "
                "updated_at = now() WHERE id = %s AND status = 'review-queued'",
                (
                    proposal,
                    target_entity_id,
                    stage_reached,
                    confidence,
                    reasoning,
                    Jsonb(alternatives),
                    candidate_id,
                ),
            )
