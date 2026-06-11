"""The cost-ledger seam (spec §6.6).

The router records one `LlmCallRecord` per call — including refusals and failures,
so the trail explains *why* a batch stopped — and reads the day's spend back to
enforce the `DAILY_BUDGET_USD` cap. Both go through the `CostStore` Protocol so
the router stays unit-testable against an in-memory fake; the Postgres-backed
`llm_calls` implementation is a sibling adapter (built with its migration).
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from pydantic import BaseModel

from story_forge.adapters.llm.base import ModelTier

CallOutcome = Literal["success", "refusal", "failure"]


class LlmCallRecord(BaseModel):
    """One row of the §6.6 ledger. Tier/provider/model are system-derived by the
    router from the adapter that served the call, never echoed from the caller
    (INV-7); `task_type` is a caller-supplied label for per-task aggregation only.

    `model` and the usage counts are nullable because a refused or failed call may
    never reach the provider (so no served model) or return no usage. The store
    assigns the timestamp; `latency_ms` is the only clock the router holds — the
    wall-clock duration it measured around the provider call (None when nothing was
    dispatched, e.g. a pre-dispatch budget refusal).
    """

    tier: ModelTier
    provider: str  # the adapter class that served (or would have served) the call
    model: str | None
    task_type: str
    outcome: CallOutcome
    input_tokens: int | None = None
    output_tokens: int | None = None
    gpu_seconds: float | None = None
    cost_estimate: float | None = None
    latency_ms: int | None = None


class TaskTypeUsage(BaseModel):
    """Today's call count and USD spend for one task type (status dashboard)."""

    task_type: str
    calls: int
    cost_usd: float


class DailyUsage(BaseModel):
    """Today's aggregate ledger view surfaced by the status endpoint (§6.6)."""

    spent_usd: float
    gpu_seconds: float
    calls: int
    by_task_type: list[TaskTypeUsage]


class LastCall(BaseModel):
    """The most recently recorded call, for the §8.5 agent-activity panel ("which
    agent ran most recently, which model/tier, latency, cost"). System-derived,
    read straight from the latest ledger row; `created_at` is the store's clock.
    """

    task_type: str
    tier: ModelTier
    provider: str
    model: str | None
    outcome: CallOutcome
    latency_ms: int | None
    cost_estimate: float | None
    gpu_seconds: float | None
    created_at: datetime


class CostStore(Protocol):
    """Persists usage rows and reports the day's paid spend for the budget gate."""

    async def spend_today_usd(self) -> float:
        """Sum of `cost_estimate` for today's calls — drives the fail-closed cap."""
        ...

    async def record(self, record: LlmCallRecord) -> None:
        """Append one usage row (success, refusal, or failure)."""
        ...

    async def last_call(self) -> LastCall | None:
        """The most recent call (any outcome), or None if the ledger is empty."""
        ...
