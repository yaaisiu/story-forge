"""PostgresDuplicateDismissalStore — the dismissed-duplicate-pair store (graph-quality S4a).

Backs DM-CD-3 (ADR 0010): the duplicate self-join computes suggestions on open, and this store
records the human's "not a duplicate" so a dismissed pair is suppressed on the next read.
Staging-side (Postgres only) — INV-9 holds, this is never a graph write.

Mirrors `PostgresCandidateStore`: each op opens its own short-lived connection so a dismissal
commits independently of any request transaction. The row id is the deterministic
`dismissal_pair_id` (uuid5 over project + sorted pair), so insert is idempotent
(`ON CONFLICT DO NOTHING`) and the suggestion read suppresses by recomputing the same id.
A dismissal is reversible: `delete` removes the row (un-dismiss).
"""

from __future__ import annotations

from uuid import UUID

import psycopg

from story_forge.adapters.db import connect, libpq_kwargs
from story_forge.config import settings
from story_forge.domain.duplicate_clusters import canonical_pair, dismissal_pair_id


class PostgresDuplicateDismissalStore:
    """The `duplicate_suggestion_dismissals` store: dismiss a pair, list a project's, un-dismiss."""

    def __init__(self, conninfo: dict[str, object] | None = None) -> None:
        self._conninfo = conninfo if conninfo is not None else libpq_kwargs(settings.database_url)

    async def _connect(self, *, autocommit: bool = False) -> psycopg.AsyncConnection:
        return await connect(self._conninfo, autocommit=autocommit)

    async def insert(self, project_id: UUID, entity_a: UUID, entity_b: UUID) -> None:
        """Record a dismissed (unordered) pair. Idempotent — re-dismissing is a no-op."""
        lo, hi = canonical_pair(entity_a, entity_b)
        pair_id = dismissal_pair_id(project_id, entity_a, entity_b)
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                "INSERT INTO duplicate_suggestion_dismissals "
                "(id, project_id, entity_id_lo, entity_id_hi) VALUES (%s, %s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (pair_id, project_id, lo, hi),
            )

    async def list_pair_ids(self, project_id: UUID) -> set[UUID]:
        """The set of dismissed pair ids for a project — the suppression set the read consults."""
        async with await self._connect(autocommit=True) as conn:
            cur = await conn.execute(
                "SELECT id FROM duplicate_suggestion_dismissals WHERE project_id = %s",
                (project_id,),
            )
            rows = await cur.fetchall()
        return {row[0] for row in rows}

    async def delete(self, project_id: UUID, entity_a: UUID, entity_b: UUID) -> None:
        """Un-dismiss a pair (reversibility, DM-CD-3). Returns silently if not dismissed."""
        pair_id = dismissal_pair_id(project_id, entity_a, entity_b)
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                "DELETE FROM duplicate_suggestion_dismissals WHERE id = %s",
                (pair_id,),
            )
