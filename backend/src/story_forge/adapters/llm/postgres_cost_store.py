"""PostgresCostStore — the `llm_calls` ledger implementation (spec §6.6).

Each operation opens its own short-lived **autocommit** connection rather than
sharing the request transaction. That is deliberate: a failed LLM call should
leave a row explaining why a batch stopped, but the request that triggered it may
roll back on that same failure — sharing its transaction would erase exactly the
trail we want. Independent commits keep the ledger durable. Per-operation connects
mirror `db.py`'s "single-user local app, a connection per unit of work is simple
and sufficient" stance.

"Today" is the Postgres server's local day (`date_trunc('day', now())`) — the
natural boundary for a single-user local app; revisit if the app ever runs
against a shared/UTC server.
"""

from __future__ import annotations

import psycopg

from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.llm.cost import (
    DailyUsage,
    LlmCallRecord,
    TaskTypeUsage,
)
from story_forge.config import settings

_TODAY = "created_at >= date_trunc('day', now())"


class PostgresCostStore:
    """`CostStore` backed by the `llm_calls` table."""

    def __init__(self, conninfo: dict[str, object] | None = None) -> None:
        # Resolved once; the DSN doesn't change over the app's life.
        self._conninfo = conninfo if conninfo is not None else libpq_kwargs(settings.database_url)

    async def _connect(self) -> psycopg.AsyncConnection:
        return await psycopg.AsyncConnection.connect(autocommit=True, **self._conninfo)  # type: ignore[arg-type]

    async def spend_today_usd(self) -> float:
        async with await self._connect() as conn:
            cur = await conn.execute(
                f"SELECT COALESCE(SUM(cost_estimate), 0) FROM llm_calls WHERE {_TODAY}"
            )
            row = await cur.fetchone()
        return float(row[0]) if row else 0.0

    async def record(self, record: LlmCallRecord) -> None:
        async with await self._connect() as conn:
            await conn.execute(
                "INSERT INTO llm_calls "
                "(tier, provider, model, task_type, outcome, "
                " input_tokens, output_tokens, gpu_seconds, cost_estimate) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)",
                (
                    record.tier,
                    record.provider,
                    record.model,
                    record.task_type,
                    record.outcome,
                    record.input_tokens,
                    record.output_tokens,
                    record.gpu_seconds,
                    record.cost_estimate,
                ),
            )

    async def summary_today(self) -> DailyUsage:
        """Aggregate today's ledger for the status dashboard (§6.6)."""
        async with await self._connect() as conn:
            totals_cur = await conn.execute(
                "SELECT COALESCE(SUM(cost_estimate), 0), COALESCE(SUM(gpu_seconds), 0), COUNT(*) "
                f"FROM llm_calls WHERE {_TODAY}"
            )
            totals = await totals_cur.fetchone()
            by_type_cur = await conn.execute(
                "SELECT task_type, COUNT(*), COALESCE(SUM(cost_estimate), 0) "
                f"FROM llm_calls WHERE {_TODAY} GROUP BY task_type ORDER BY task_type"
            )
            by_type = await by_type_cur.fetchall()

        spent, gpu_seconds, calls = (totals[0], totals[1], totals[2]) if totals else (0, 0, 0)
        return DailyUsage(
            spent_usd=float(spent),
            gpu_seconds=float(gpu_seconds),
            calls=int(calls),
            by_task_type=[
                TaskTypeUsage(task_type=r[0], calls=int(r[1]), cost_usd=float(r[2]))
                for r in by_type
            ],
        )
