"""PostgresRelationStore — the `staged_relations` store backing the relation-write path (M3.S4e).

The symmetric sibling of `PostgresCandidateStore` for *relations*: it owns the
`staged_relations` table's lifecycle ops (the decide-relations queue read, the per-relation
get, and the two terminal status writes the `RelationReviewService` sequences). Like the
candidate store, each review op opens its own short-lived connection.

The one exception is the **staging insert** (`insert`): it is a `@staticmethod` that runs on a
caller-supplied connection so a paragraph's relations are committed in the *same* transaction
as its candidates + the `paragraph_processed` marker (`PostgresCandidateStore.persist`). If the
relations were a separate autocommit write, a crash between them would mark a paragraph
processed while silently losing its relations on resume.
"""

from __future__ import annotations

from uuid import UUID

import psycopg
from psycopg.rows import class_row

from story_forge.adapters.db import connect, libpq_kwargs
from story_forge.config import settings
from story_forge.domain.candidates import StagedRelation

_RELATION_COLUMNS = (
    "id, story_id, paragraph_id, subject, predicate, object, confidence, evidence_quote, "
    "subject_entity_id, object_entity_id, edge_id, status, created_at, updated_at"
)


class PostgresRelationStore:
    """`RelationRepo` backed by the `staged_relations` table."""

    def __init__(self, conninfo: dict[str, object] | None = None) -> None:
        self._conninfo = conninfo if conninfo is not None else libpq_kwargs(settings.database_url)

    async def _connect(self, *, autocommit: bool = False) -> psycopg.AsyncConnection:
        return await connect(self._conninfo, autocommit=autocommit)

    # --- Staging (runs on the caller's extract-path transaction) -----------

    @staticmethod
    async def insert(conn: psycopg.AsyncConnection, relation: StagedRelation) -> None:
        """Stage one relation on the caller's connection (atomic with the candidate inserts).

        `ON CONFLICT (id) DO NOTHING` keeps a defensive re-persist idempotent — the id is a
        deterministic function of the surface triple within its paragraph.
        """
        await conn.execute(
            f"INSERT INTO staged_relations ({_RELATION_COLUMNS}) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
            "ON CONFLICT (id) DO NOTHING",
            (
                relation.id,
                relation.story_id,
                relation.paragraph_id,
                relation.subject,
                relation.predicate,
                relation.object,
                relation.confidence,
                relation.evidence_quote,
                relation.subject_entity_id,
                relation.object_entity_id,
                relation.edge_id,
                relation.status,
                relation.created_at,
                relation.updated_at,
            ),
        )

    # --- Review (the decide-relations path) --------------------------------

    async def list_staged(self, story_id: UUID) -> list[StagedRelation]:
        """A story's still-staged relations — the decide-relations queue source (§3.3)."""
        async with await self._connect(autocommit=True) as conn:
            cur = conn.cursor(row_factory=class_row(StagedRelation))
            await cur.execute(
                f"SELECT {_RELATION_COLUMNS} FROM staged_relations "
                "WHERE story_id = %s AND status = 'staged' ORDER BY created_at",
                (story_id,),
            )
            return await cur.fetchall()

    async def get_written_by_edge_id(self, story_id: UUID, edge_id: UUID) -> list[StagedRelation]:
        """Every committed source row behind one graph edge — the edge-evidence read (S3, DM-EE-2).

        A content-addressed `edge_id` collapses the same resolved triple across N paragraphs to one
        edge but keeps one `written` row per paragraph, so this returns the **complete one-to-many**
        provenance set (ordered by staging time), scoped to the story. A manually-added edge (no
        staged relation) yields an empty list — the read-side face of INV-9's graph-vs-staging line.
        """
        async with await self._connect(autocommit=True) as conn:
            cur = conn.cursor(row_factory=class_row(StagedRelation))
            await cur.execute(
                f"SELECT {_RELATION_COLUMNS} FROM staged_relations "
                "WHERE edge_id = %s AND story_id = %s AND status = 'written' ORDER BY created_at",
                (edge_id, story_id),
            )
            return await cur.fetchall()

    async def get_relation(self, relation_id: UUID) -> StagedRelation | None:
        async with await self._connect(autocommit=True) as conn:
            cur = conn.cursor(row_factory=class_row(StagedRelation))
            await cur.execute(
                f"SELECT {_RELATION_COLUMNS} FROM staged_relations WHERE id = %s",
                (relation_id,),
            )
            return await cur.fetchone()

    async def mark_written(
        self,
        relation_id: UUID,
        *,
        subject_entity_id: UUID,
        object_entity_id: UUID,
        edge_id: UUID,
    ) -> None:
        """Record a committed edge — the **last** write on the commit path (status-last, so a
        crash before it re-commits idempotently). The `status = 'staged'` guard makes it a
        no-op on any terminal row (defence-in-depth for the never-resurface-a-decision contract).
        """
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                "UPDATE staged_relations SET status = 'written', subject_entity_id = %s, "
                "object_entity_id = %s, edge_id = %s, updated_at = now() "
                "WHERE id = %s AND status = 'staged'",
                (subject_entity_id, object_entity_id, edge_id, relation_id),
            )

    async def mark_rejected(self, relation_id: UUID) -> None:
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                "UPDATE staged_relations SET status = 'rejected', updated_at = now() "
                "WHERE id = %s AND status = 'staged'",
                (relation_id,),
            )
