"""The cost-ledger seam (spec §6.6).

The router records one `LlmCallRecord` per call — including refusals and failures,
so the trail explains *why* a batch stopped — and reads the day's spend back to
enforce the `DAILY_BUDGET_USD` cap. Both go through the `CostStore` Protocol so
the router stays unit-testable against an in-memory fake; the Postgres-backed
`llm_calls` implementation is a sibling adapter (built with its migration).
"""

from __future__ import annotations

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
    assigns the timestamp, so the router holds no clock.
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


class CostStore(Protocol):
    """Persists usage rows and reports the day's paid spend for the budget gate."""

    async def spend_today_usd(self) -> float:
        """Sum of `cost_estimate` for today's calls — drives the fail-closed cap."""
        ...

    async def record(self, record: LlmCallRecord) -> None:
        """Append one usage row (success, refusal, or failure)."""
        ...
