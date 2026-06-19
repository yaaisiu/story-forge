"""PostgresEditStore — the `graph_edits` before→after edit-evidence log (M4.S3a, DM-S3a-2).

The graph-edit twin of `PostgresCandidateStore.insert_decision`: an append-only record of each
human edit to committed graph state (INV-3 reversibility + the correction flywheel). Like the
candidate/relation stores, each write opens its own short-lived autocommit connection. The
`EntityEditService` sequences the write order (graph mutation first, this evidence row last);
this store provides only the single insert.
"""

from __future__ import annotations

import psycopg
from psycopg.types.json import Jsonb

from story_forge.adapters.db import connect, libpq_kwargs
from story_forge.config import settings
from story_forge.domain.graph_edit import GraphEdit

_EDIT_COLUMNS = "id, target_id, target_kind, op, before, after, actor, created_at"


class PostgresEditStore:
    """`EditEvidenceRepo` backed by the `graph_edits` table."""

    def __init__(self, conninfo: dict[str, object] | None = None) -> None:
        self._conninfo = conninfo if conninfo is not None else libpq_kwargs(settings.database_url)

    async def _connect(self, *, autocommit: bool = False) -> psycopg.AsyncConnection:
        return await connect(self._conninfo, autocommit=autocommit)

    async def record_edit(self, edit: GraphEdit) -> None:
        """Append one before→after edit row. `ON CONFLICT (id) DO NOTHING` keeps a defensive
        re-record idempotent (the service may retry after a crash before the evidence write)."""
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                f"INSERT INTO graph_edits ({_EDIT_COLUMNS}) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (
                    edit.id,
                    edit.target_id,
                    edit.target_kind,
                    edit.op,
                    Jsonb(edit.before) if edit.before is not None else None,
                    Jsonb(edit.after) if edit.after is not None else None,
                    edit.actor,
                    edit.created_at,
                ),
            )
