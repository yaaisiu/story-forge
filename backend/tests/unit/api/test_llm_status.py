"""Unit tests for `GET /llm/status` (spec §6.6, §8.5).

No DB: the `get_cost_store` dependency is overridden with a fake returning a
canned `DailyUsage`, so we assert the route's own contract — budget passthrough,
remaining = budget − spent (clamped at zero), and the task breakdown — not the
store's SQL (that's the integration test).
"""

from __future__ import annotations

from datetime import UTC, datetime

from httpx import ASGITransport, AsyncClient

from story_forge.adapters.llm.cost import DailyUsage, LastCall, TaskTypeUsage
from story_forge.api.llm import get_cost_store
from story_forge.config import settings
from story_forge.main import app


class _FakeStore:
    def __init__(self, summary: DailyUsage, last_call: LastCall | None = None) -> None:
        self._summary = summary
        self._last_call = last_call

    async def summary_today(self) -> DailyUsage:
        return self._summary

    async def last_call(self) -> LastCall | None:
        return self._last_call


async def _get_status(summary: DailyUsage, last_call: LastCall | None = None) -> dict[str, object]:
    app.dependency_overrides[get_cost_store] = lambda: _FakeStore(summary, last_call)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            response = await client.get("/llm/status")
    finally:
        app.dependency_overrides.clear()
    assert response.status_code == 200
    body = response.json()
    assert isinstance(body, dict)
    return body


async def test_reports_budget_spend_and_remaining() -> None:
    budget = settings.daily_budget_usd
    body = await _get_status(
        DailyUsage(spent_usd=budget - 2.0, gpu_seconds=12.0, calls=4, by_task_type=[])
    )

    assert body["daily_budget_usd"] == budget
    assert body["spent_today_usd"] == budget - 2.0
    assert body["remaining_usd"] == 2.0
    assert body["gpu_seconds_today"] == 12.0
    assert body["calls_today"] == 4


async def test_remaining_clamps_at_zero_when_over_budget() -> None:
    budget = settings.daily_budget_usd
    body = await _get_status(
        DailyUsage(spent_usd=budget + 100.0, gpu_seconds=0.0, calls=1, by_task_type=[])
    )

    assert body["remaining_usd"] == 0.0


async def test_passes_through_task_type_breakdown() -> None:
    body = await _get_status(
        DailyUsage(
            spent_usd=1.0,
            gpu_seconds=0.0,
            calls=2,
            by_task_type=[
                TaskTypeUsage(task_type="rewrite", calls=1, cost_usd=1.0),
                TaskTypeUsage(task_type="extraction", calls=1, cost_usd=0.0),
            ],
        )
    )

    by_type = body["by_task_type"]
    assert by_type == [
        {"task_type": "rewrite", "calls": 1, "cost_usd": 1.0},
        {"task_type": "extraction", "calls": 1, "cost_usd": 0.0},
    ]


async def test_surfaces_the_most_recent_call_for_the_panel() -> None:
    # §8.5 panel: which agent ran most recently, the tier/model chosen, latency, cost.
    ran_at = datetime(2026, 6, 11, 9, 30, tzinfo=UTC)
    body = await _get_status(
        DailyUsage(spent_usd=1.0, gpu_seconds=0.0, calls=1, by_task_type=[]),
        last_call=LastCall(
            task_type="extraction",
            tier="cloud_free",
            provider="OllamaProvider",
            model="gpt-oss:120b-cloud",
            outcome="success",
            latency_ms=842,
            cost_estimate=None,
            gpu_seconds=3.5,
            created_at=ran_at,
        ),
    )

    last = body["last_call"]
    assert last["task_type"] == "extraction"
    assert last["tier"] == "cloud_free"
    assert last["model"] == "gpt-oss:120b-cloud"
    assert last["latency_ms"] == 842
    assert last["outcome"] == "success"
    assert last["created_at"].startswith("2026-06-11T09:30:00")


async def test_last_call_is_null_before_any_call() -> None:
    body = await _get_status(
        DailyUsage(spent_usd=0.0, gpu_seconds=0.0, calls=0, by_task_type=[]),
    )
    assert body["last_call"] is None
