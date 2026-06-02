"""Unit tests for `GET /llm/status` (spec §6.6, §8.5).

No DB: the `get_cost_store` dependency is overridden with a fake returning a
canned `DailyUsage`, so we assert the route's own contract — budget passthrough,
remaining = budget − spent (clamped at zero), and the task breakdown — not the
store's SQL (that's the integration test).
"""

from __future__ import annotations

from httpx import ASGITransport, AsyncClient

from story_forge.adapters.llm.cost import DailyUsage, TaskTypeUsage
from story_forge.api.llm import get_cost_store
from story_forge.config import settings
from story_forge.main import app


class _FakeStore:
    def __init__(self, summary: DailyUsage) -> None:
        self._summary = summary

    async def summary_today(self) -> DailyUsage:
        return self._summary


async def _get_status(summary: DailyUsage) -> dict[str, object]:
    app.dependency_overrides[get_cost_store] = lambda: _FakeStore(summary)
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
