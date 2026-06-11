"""PostgresCostStore against the real `story_forge_test` database (§6.6 ledger).

The store commits autonomously (so a failed call's row survives the request that
rolled back), which means the `db_conn` rollback fixture can't clean up after it.
Instead each test starts from a truncated `llm_calls` table; the whole DB is
dropped at session end by the conftest fixture.
"""

from __future__ import annotations

import asyncio

import psycopg
import pytest
import pytest_asyncio

from story_forge.adapters.db import libpq_kwargs
from story_forge.adapters.llm.cost import LlmCallRecord
from story_forge.adapters.llm.postgres_cost_store import PostgresCostStore
from story_forge.config import settings

pytestmark = pytest.mark.integration


def _rec(
    *,
    task_type: str = "rewrite",
    outcome: str = "success",
    cost: float | None = None,
    gpu_seconds: float | None = None,
    latency_ms: int | None = None,
) -> LlmCallRecord:
    return LlmCallRecord(
        tier="cloud_strong",
        provider="OpenRouterProvider",
        model="anthropic/claude-3.5-sonnet",
        task_type=task_type,
        outcome=outcome,  # type: ignore[arg-type]
        input_tokens=100,
        output_tokens=50,
        gpu_seconds=gpu_seconds,
        cost_estimate=cost,
        latency_ms=latency_ms,
    )


@pytest_asyncio.fixture
async def cost_store(_migrated_test_db: None) -> PostgresCostStore:
    conninfo = libpq_kwargs(settings.test_database_url)
    async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
        await conn.execute("DELETE FROM llm_calls")
    return PostgresCostStore(conninfo)


async def test_spend_today_sums_only_costed_calls(cost_store: PostgresCostStore) -> None:
    await cost_store.record(_rec(cost=1.0))
    await cost_store.record(_rec(cost=2.0))
    await cost_store.record(_rec(task_type="chunking", outcome="success", cost=None))  # free tier

    assert await cost_store.spend_today_usd() == pytest.approx(3.0)


async def test_records_failures_and_refusals_for_the_trail(cost_store: PostgresCostStore) -> None:
    # Failures/refusals carry no cost but must still leave a row (spec §6.6).
    await cost_store.record(_rec(outcome="failure", cost=None))
    await cost_store.record(_rec(outcome="refusal", cost=None))

    summary = await cost_store.summary_today()
    assert summary.calls == 2
    assert summary.spent_usd == pytest.approx(0.0)


async def test_persists_latency_ms(cost_store: PostgresCostStore) -> None:
    # OQ-9: the §6.6 ledger records wall-clock latency per call; it round-trips
    # through the store, and stays NULL when the router didn't dispatch (refusal).
    await cost_store.record(_rec(latency_ms=250))
    await cost_store.record(_rec(outcome="refusal", latency_ms=None))

    conninfo = libpq_kwargs(settings.test_database_url)
    async with await psycopg.AsyncConnection.connect(autocommit=True, **conninfo) as conn:  # type: ignore[arg-type]
        cur = await conn.execute("SELECT latency_ms FROM llm_calls ORDER BY latency_ms NULLS LAST")
        rows = await cur.fetchall()
    assert [r[0] for r in rows] == [250, None]


async def test_last_call_returns_the_most_recent_row(cost_store: PostgresCostStore) -> None:
    # §8.5 panel: the most recently recorded call. A small gap between inserts keeps
    # the `created_at DESC` ordering unambiguous (each commit stamps its own now()).
    await cost_store.record(_rec(task_type="chunking", cost=0.1, latency_ms=100))
    await asyncio.sleep(0.01)
    await cost_store.record(_rec(task_type="extraction", cost=None, latency_ms=842))

    last = await cost_store.last_call()

    assert last is not None
    assert last.task_type == "extraction"
    assert last.tier == "cloud_strong"
    assert last.provider == "OpenRouterProvider"
    assert last.latency_ms == 842
    assert last.outcome == "success"
    assert last.created_at is not None


async def test_last_call_is_none_when_empty(cost_store: PostgresCostStore) -> None:
    assert await cost_store.last_call() is None


async def test_summary_groups_by_task_type(cost_store: PostgresCostStore) -> None:
    await cost_store.record(_rec(task_type="rewrite", cost=1.5, gpu_seconds=None))
    await cost_store.record(_rec(task_type="rewrite", cost=0.5))
    await cost_store.record(_rec(task_type="extraction", cost=None, gpu_seconds=4.0))

    summary = await cost_store.summary_today()

    assert summary.calls == 3
    assert summary.spent_usd == pytest.approx(2.0)
    assert summary.gpu_seconds == pytest.approx(4.0)
    by_type = {t.task_type: t for t in summary.by_task_type}
    assert by_type["rewrite"].calls == 2
    assert by_type["rewrite"].cost_usd == pytest.approx(2.0)
    assert by_type["extraction"].calls == 1
    assert by_type["extraction"].cost_usd == pytest.approx(0.0)
