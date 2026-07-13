"""PostgresLabelDismissalStore — the dismissed-label-pair store (graph-quality S6a).

Backs DM-NN-3: the label-synonym self-join computes suggestions on open, and this store
records the human's "these labels are genuinely different" so a dismissed pair is suppressed
on the next read. Staging-side (Postgres only) — INV-9 holds, this is never a graph write.

The direct sibling of `PostgresDuplicateDismissalStore` (ADR 0010) at label granularity: a
label pair is a *string* pair scoped to a *surface* (predicate or type), so it is a separate
table (`label_pair_dismissals`) rather than the uuid-pair `duplicate_suggestion_dismissals`.
Mirrors the same design — each op opens its own short-lived connection so a dismissal commits
independently of any request transaction; the row id is the deterministic `label_dismissal_id`
(uuid5 over project + surface + sorted pair), so insert is idempotent (`ON CONFLICT DO
NOTHING`) and the read suppresses by recomputing the same id. A dismissal is reversible:
`delete` removes the row (un-dismiss).
"""

from __future__ import annotations

from uuid import UUID

import psycopg

from story_forge.adapters.db import connect, libpq_kwargs
from story_forge.config import settings
from story_forge.domain.label_synonyms import canonical_label_pair, label_dismissal_id


class PostgresLabelDismissalStore:
    """The `label_pair_dismissals` store: dismiss a label pair, list a project's, un-dismiss."""

    def __init__(self, conninfo: dict[str, object] | None = None) -> None:
        self._conninfo = conninfo if conninfo is not None else libpq_kwargs(settings.database_url)

    async def _connect(self, *, autocommit: bool = False) -> psycopg.AsyncConnection:
        return await connect(self._conninfo, autocommit=autocommit)

    async def insert(self, project_id: UUID, surface: str, label_a: str, label_b: str) -> None:
        """Record a dismissed (unordered) label pair on a surface. Idempotent."""
        lo, hi = canonical_label_pair(label_a, label_b)
        pair_id = label_dismissal_id(project_id, surface, label_a, label_b)
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                "INSERT INTO label_pair_dismissals "
                "(id, project_id, surface, label_lo, label_hi) VALUES (%s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                (pair_id, project_id, surface, lo, hi),
            )

    async def list_pair_ids(self, project_id: UUID) -> set[UUID]:
        """The set of dismissed pair ids for a project (both surfaces — the id encodes surface)."""
        async with await self._connect(autocommit=True) as conn:
            cur = await conn.execute(
                "SELECT id FROM label_pair_dismissals WHERE project_id = %s",
                (project_id,),
            )
            rows = await cur.fetchall()
        return {row[0] for row in rows}

    async def delete(self, project_id: UUID, surface: str, label_a: str, label_b: str) -> None:
        """Un-dismiss a label pair (reversibility, DM-NN-3). Returns silently if not dismissed."""
        pair_id = label_dismissal_id(project_id, surface, label_a, label_b)
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                "DELETE FROM label_pair_dismissals WHERE id = %s",
                (pair_id,),
            )
