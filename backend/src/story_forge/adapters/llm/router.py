"""LLMRouter — tier selection, failover, the budget gate, and the cost ledger
(spec §6.5/§6.6, ADR 0003).

Agents call `router.complete(...)`, not a provider directly: the router picks the
tier for the task's weight, tries the tier's providers in their configured order
with **error-discriminated** failover, enforces the fail-closed `DAILY_BUDGET_USD`
cap, and writes one ledger row per call (success, refusal, or failure). Schema
validation and its retry stay in the agent (the ChunkingAgent pattern) — the
router owns the transport-and-spend concerns no single agent should re-implement.

Control-first posture (never silently escalate spend):
- 429 / 5xx / transport error (connect, timeout) → fail over to the next provider
  in the tier (spec §6.5 fails over on network errors too, not just status codes).
- 401 → fail over as well (bad key on this provider), but it does *not* count as
  quota exhaustion.
- other 4xx → a real bug; re-raise, no failover.
- a paid adapter's `BudgetExceededError` (HTTP 402) → re-raise immediately; do not
  try the next provider.
- a `cloud_free` tier exhausted *purely by rate-limit/quota (429)* →
  `QuotaExhaustedError` (pause and ask), never an automatic jump to a paid tier.
  If any provider in the tier failed for another reason (bad key, outage, network),
  that real error is raised instead — we don't cry "quota" over a misconfiguration.

The provider preference *within* a tier (OpenRouter first among paid routes) is
expressed by the order of the list handed in at construction (wired in `main.py`
per ADR 0003), so the router itself stays provider-agnostic.
"""

from __future__ import annotations

from typing import Literal

import httpx

from story_forge.adapters.llm.base import (
    BudgetExceededError,
    CompletionResult,
    LLMProvider,
    Message,
    ModelTier,
    QuotaExhaustedError,
    Usage,
)
from story_forge.adapters.llm.cost import CallOutcome, CostStore, LlmCallRecord

TaskWeight = Literal["light", "medium", "heavy"]

_FREE_PRICE = (0.0, 0.0)


class RouterConfigError(RuntimeError):
    """No provider is configured for the tier a task needs — a wiring mistake."""


def tier_for_weight(weight: TaskWeight, *, gpu_available: bool) -> ModelTier:
    """Map a task's weight to a model tier (spec §6.5 router decision order).

    `light` prefers the local small model, but on a GPU-less host that tier is
    impractical, so it falls back to the cheapest `cloud_free` model.
    """
    if weight == "light":
        return "local_small" if gpu_available else "cloud_free"
    if weight == "medium":
        return "cloud_free"
    return "cloud_strong"


class LLMRouter:
    """Routes a task to a tier, fails over within it, and records every call."""

    def __init__(
        self,
        *,
        providers: dict[ModelTier, list[LLMProvider]],
        cost_store: CostStore,
        daily_budget_usd: float,
        gpu_available: bool = False,
    ) -> None:
        self._providers = providers
        self._cost_store = cost_store
        self._daily_budget_usd = daily_budget_usd
        self._gpu_available = gpu_available

    async def complete(
        self,
        messages: list[Message],
        *,
        weight: TaskWeight,
        task_type: str,
        json_schema: dict[str, object] | None = None,
    ) -> CompletionResult:
        """Run a completion for `task_type` at the tier implied by `weight`."""
        tier = tier_for_weight(weight, gpu_available=self._gpu_available)
        providers = self._providers.get(tier) or []
        if not providers:
            raise RouterConfigError(f"no provider configured for tier {tier!r}")

        # Fail-closed budget gate: if this tier can incur USD cost and today's
        # spend has reached the cap, refuse *before* dispatch. Free tiers are
        # never blocked by the paid cap. Bounded one-call overshoot is accepted
        # (single-user PoC, spec §6.6).
        if _tier_is_paid(providers):
            spend = await self._cost_store.spend_today_usd()
            if spend >= self._daily_budget_usd:
                await self._record(providers[0], tier, task_type, "refusal", usage=None)
                raise BudgetExceededError(
                    f"daily budget ${self._daily_budget_usd:.2f} reached "
                    f"(spent ${spend:.2f}); pausing for the user"
                )

        last_error: Exception | None = None
        saw_non_quota_failure = False
        for provider in providers:
            try:
                result = await provider.complete(messages, tier, json_schema)
            except BudgetExceededError:
                # Provider refused for lack of credit — a spend ceiling, not a
                # transient fault. Record and re-raise; never escalate to the next.
                await self._record(provider, tier, task_type, "refusal", usage=None)
                raise
            except httpx.HTTPStatusError as exc:
                await self._record(provider, tier, task_type, "failure", usage=None)
                status = exc.response.status_code
                if status == 429:
                    last_error = exc  # rate-limit / quota — fail over; may be exhaustion
                    continue
                if status == 401 or 500 <= status < 600:
                    # Bad key or server outage: fail over, but this is NOT quota
                    # exhaustion — surface the real error if the tier runs out.
                    last_error = exc
                    saw_non_quota_failure = True
                    continue
                raise  # other 4xx (e.g. 400 bad request) — failover won't help
            except httpx.RequestError as exc:
                # Transport-level failure (connect refused, timeout, …). Spec §6.5
                # fails over on network errors too; not quota exhaustion.
                await self._record(provider, tier, task_type, "failure", usage=None)
                last_error = exc
                saw_non_quota_failure = True
                continue
            else:
                await self._record(provider, tier, task_type, "success", usage=result.usage)
                return result

        # Every provider in the tier was exhausted by a retryable error. Only pure
        # rate-limit/quota exhaustion of the free tier is a pause-and-ask; a bad
        # key, an outage, or a network failure is a real error we must surface.
        if tier == "cloud_free" and not saw_non_quota_failure:
            raise QuotaExhaustedError(
                "cloud_free quota exhausted across all providers; pausing for the user"
            )
        assert last_error is not None  # the loop only falls through after a failure
        raise last_error

    async def _record(
        self,
        provider: LLMProvider,
        tier: ModelTier,
        task_type: str,
        outcome: CallOutcome,
        *,
        usage: Usage | None,
    ) -> None:
        await self._cost_store.record(
            LlmCallRecord(
                tier=tier,
                provider=type(provider).__name__,
                model=usage.model if usage else None,
                task_type=task_type,
                outcome=outcome,
                input_tokens=usage.input_tokens if usage else None,
                output_tokens=usage.output_tokens if usage else None,
                gpu_seconds=usage.gpu_seconds if usage else None,
                cost_estimate=usage.cost_estimate if usage else None,
            )
        )


def _tier_is_paid(providers: list[LLMProvider]) -> bool:
    """A tier costs money if any of its providers charges per token."""
    return any(p.cost_per_1k_tokens != _FREE_PRICE for p in providers)
