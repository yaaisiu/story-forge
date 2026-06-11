"""LLM status route (spec §6.6, §8.5).

A thin read endpoint the M2.S5 agent-activity panel consumes: today's paid spend
against the `DAILY_BUDGET_USD` cap, GPU-seconds consumed (Ollama Cloud's billing
unit), and a per-task-type breakdown — all read from the `llm_calls` ledger.

GPU-time *quota remaining* is not surfaced here: that needs a live call to Ollama
Cloud's account API, which lands with the panel (M2.S5). For now we report the
GPU-seconds the ledger has observed, not a remaining-quota figure we can't yet
obtain — better an honest gap than a fabricated number.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel

from story_forge.adapters.llm.cost import LastCall, TaskTypeUsage
from story_forge.adapters.llm.postgres_cost_store import PostgresCostStore
from story_forge.config import settings

router = APIRouter(prefix="/llm", tags=["llm"])


class LlmStatusResponse(BaseModel):
    """Budget + today's usage + the most recent call, for the agent-activity panel."""

    daily_budget_usd: float
    spent_today_usd: float
    remaining_usd: float
    gpu_seconds_today: float
    calls_today: int
    by_task_type: list[TaskTypeUsage]
    last_call: LastCall | None


def get_cost_store(request: Request) -> PostgresCostStore:
    """The app-lifetime cost store wired in `main.py`."""
    store: PostgresCostStore = request.app.state.cost_store
    return store


@router.get("/status")
async def llm_status(
    cost_store: Annotated[PostgresCostStore, Depends(get_cost_store)],
) -> LlmStatusResponse:
    """Today's spend, GPU-seconds, per-task-type breakdown, and the most recent call."""
    summary = await cost_store.summary_today()
    budget = settings.daily_budget_usd
    return LlmStatusResponse(
        daily_budget_usd=budget,
        spent_today_usd=summary.spent_usd,
        remaining_usd=max(0.0, budget - summary.spent_usd),
        gpu_seconds_today=summary.gpu_seconds,
        calls_today=summary.calls,
        by_task_type=summary.by_task_type,
        last_call=await cost_store.last_call(),
    )
