"""PostgresEditStore — the `graph_edits` before→after edit-evidence log (M4.S3a, DM-S3a-2).

The graph-edit twin of `PostgresCandidateStore.insert_decision`: an append-only record of each
human edit to committed graph state (INV-3 reversibility + the correction flywheel). Like the
candidate/relation stores, each write opens its own short-lived autocommit connection. The
`EntityEditService` sequences the write order (graph mutation first, this evidence row last);
this store provides only the single insert.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any
from uuid import UUID

import psycopg
from psycopg.rows import dict_row
from psycopg.types.json import Jsonb

from story_forge.adapters.db import connect, libpq_kwargs
from story_forge.config import settings
from story_forge.domain.graph_edit import GraphEdit

# An S3a singleton edit carries no grouping (`operation_id`/`seq`/`op_kind`/`description` stay
# NULL — it is its own one-step operation), but it *does* carry `project_id` so the M4.S3b-be2
# undo read path can find it scoped to a project (`COALESCE(operation_id, id)` groups it by its id).
_EDIT_COLUMNS = "id, target_id, target_kind, op, before, after, actor, created_at, project_id"

# The read path (M4.S3b-be2 undo) selects whole rows; an S3a singleton has a NULL `operation_id`,
# so it groups under its own `id` (the COALESCE below) — one row is its own one-step operation.
_ALL_COLUMNS = (
    "id, target_id, target_kind, op, before, after, actor, created_at, "
    "operation_id, seq, op_kind, description, project_id"
)

# The grouped-operation write (M4.S3b) carries the grouping columns too; `undone_at` is left to
# its NULL default (a freshly-recorded operation is live).
_OPERATION_COLUMNS = (
    "id, target_id, target_kind, op, before, after, actor, created_at, "
    "operation_id, seq, op_kind, description, project_id"
)


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
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s) ON CONFLICT (id) DO NOTHING",
                (
                    edit.id,
                    edit.target_id,
                    edit.target_kind,
                    edit.op,
                    Jsonb(edit.before) if edit.before is not None else None,
                    Jsonb(edit.after) if edit.after is not None else None,
                    edit.actor,
                    edit.created_at,
                    edit.project_id,
                ),
            )

    async def record_operation(self, edits: Sequence[GraphEdit]) -> None:
        """Append all rows of one grouped operation (a merge's N writes, M4.S3b, DM-S3b-1) in a
        **single transaction**, so undo never reads a half-recorded operation. Each row carries the
        shared `operation_id` + its `seq`/`op_kind`/`description`/`project_id`. `ON CONFLICT (id) DO
        NOTHING` keeps a retried operation idempotent — the orchestration derives every row id
        deterministically, so a crash before the evidence write completes without duplicating."""
        if not edits:
            return
        rows = [
            (
                edit.id,
                edit.target_id,
                edit.target_kind,
                edit.op,
                Jsonb(edit.before) if edit.before is not None else None,
                Jsonb(edit.after) if edit.after is not None else None,
                edit.actor,
                edit.created_at,
                edit.operation_id,
                edit.seq,
                edit.op_kind,
                edit.description,
                edit.project_id,
            )
            for edit in edits
        ]
        async with await self._connect(autocommit=False) as conn, conn.cursor() as cur:
            await cur.executemany(
                f"INSERT INTO graph_edits ({_OPERATION_COLUMNS}) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON CONFLICT (id) DO NOTHING",
                rows,
            )

    async def latest_live_operation(self, project_id: UUID) -> list[GraphEdit] | None:
        """The newest not-yet-undone operation in this project — the undo stack's top (M4.S3b-be2,
        DM-S3b-1). Returns all its rows ordered by `seq`, or `None` when nothing is live. A grouped
        op (merge/delete) shares an `operation_id`; an S3a singleton edit has a NULL `operation_id`
        and groups under its own `id` — `COALESCE(operation_id, id)` is the uniform group key."""
        async with await self._connect(autocommit=True) as conn:
            cur = conn.cursor(row_factory=dict_row)
            await cur.execute(
                "SELECT COALESCE(operation_id, id) AS op_key FROM graph_edits "
                "WHERE project_id = %s AND undone_at IS NULL "
                "ORDER BY created_at DESC, seq DESC LIMIT 1",
                (project_id,),
            )
            head = await cur.fetchone()
            if head is None:
                return None
            await cur.execute(
                f"SELECT {_ALL_COLUMNS} FROM graph_edits "
                "WHERE COALESCE(operation_id, id) = %s AND undone_at IS NULL ORDER BY seq",
                (head["op_key"],),
            )
            return [_row_to_edit(row) for row in await cur.fetchall()]

    async def mark_operation_undone(self, op_key: UUID, *, undone_at: datetime) -> None:
        """Stamp `undone_at` on every still-live row of an operation (the `applied → undone` flip,
        ADR 0007). `op_key` is the `COALESCE(operation_id, id)` group key. The `undone_at IS NULL`
        guard makes a re-stamp a no-op, so a crashed undo's retry is idempotent."""
        async with await self._connect(autocommit=True) as conn:
            await conn.execute(
                "UPDATE graph_edits SET undone_at = %s "
                "WHERE COALESCE(operation_id, id) = %s AND undone_at IS NULL",
                (undone_at, op_key),
            )

    async def is_operation_undone(self, operation_id: UUID) -> bool:
        """Does an operation with this id already exist *and* sit in the `undone` state? The merge
        id-generation probe (M4.S3b-be2): a re-merge of the same pair after an undo must derive a
        fresh `operation_id` or `ON CONFLICT (id) DO NOTHING` would silently drop its evidence
        (ADR 0007, Consequences). A *live* op returns False, so a crash-retry of an in-flight merge
        re-derives the same id (idempotent); only an *undone* prior op pushes the next gen."""
        async with await self._connect(autocommit=True) as conn:
            cur = await conn.execute(
                "SELECT 1 FROM graph_edits "
                "WHERE operation_id = %s AND undone_at IS NOT NULL LIMIT 1",
                (operation_id,),
            )
            return await cur.fetchone() is not None


def _row_to_edit(row: dict[str, Any]) -> GraphEdit:
    """Map a `graph_edits` row (jsonb before/after already decoded) back to a `GraphEdit`."""
    return GraphEdit(
        id=row["id"],
        target_id=row["target_id"],
        target_kind=row["target_kind"],
        op=row["op"],
        before=row["before"],
        after=row["after"],
        actor=row["actor"],
        created_at=row["created_at"],
        operation_id=row["operation_id"],
        seq=row["seq"] if row["seq"] is not None else 0,
        op_kind=row["op_kind"],
        description=row["description"],
        project_id=row["project_id"],
    )
