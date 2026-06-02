"""Unit tests for `LLMRouter` — tier selection, error-discriminated failover,
the control-first pause-and-ask paths, and one-row-per-call ledger recording.

No network, no DB: providers are fakes that succeed or raise a chosen error, and
the cost store is an in-memory `CostStore`. The router's contract is what we
assert — which tier it picks, when it fails over vs. fails fast vs. pauses, and
what it writes to the ledger — never a real model's behaviour.
"""

from __future__ import annotations

import httpx
import pytest

from story_forge.adapters.llm.base import (
    BudgetExceededError,
    CompletionResult,
    Message,
    ModelTier,
    QuotaExhaustedError,
    Usage,
)
from story_forge.adapters.llm.cost import LlmCallRecord
from story_forge.adapters.llm.router import LLMRouter, RouterConfigError, tier_for_weight


def _http_error(status: int) -> httpx.HTTPStatusError:
    request = httpx.Request("POST", "https://provider.example/chat")
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


class FakeProvider:
    """An `LLMProvider` that returns a canned result or raises a chosen error."""

    def __init__(
        self,
        *,
        result: CompletionResult | None = None,
        error: Exception | None = None,
        paid: bool = False,
    ) -> None:
        self._result = result
        self._error = error
        self._paid = paid
        self.calls = 0

    @property
    def cost_per_1k_tokens(self) -> tuple[float, float]:
        return (3.0, 15.0) if self._paid else (0.0, 0.0)

    @property
    def rate_limit_kind(self) -> str:
        return "per_minute_tokens" if self._paid else "none"

    async def complete(
        self,
        messages: list[Message],
        model_tier: ModelTier,
        json_schema: dict[str, object] | None = None,
    ) -> CompletionResult:
        self.calls += 1
        if self._error is not None:
            raise self._error
        assert self._result is not None
        return self._result


class FakeCostStore:
    """In-memory `CostStore`: records rows and reports a settable day's spend."""

    def __init__(self, spend_today: float = 0.0) -> None:
        self.records: list[LlmCallRecord] = []
        self._spend_today = spend_today

    async def spend_today_usd(self) -> float:
        return self._spend_today

    async def record(self, record: LlmCallRecord) -> None:
        self.records.append(record)


def _ok(tier: ModelTier, *, cost: float | None = None) -> CompletionResult:
    return CompletionResult(
        content="ok",
        model_tier=tier,
        usage=Usage(model="served-model", input_tokens=10, output_tokens=5, cost_estimate=cost),
    )


def _router(
    providers: dict[ModelTier, list[object]], store: FakeCostStore, **kw: object
) -> LLMRouter:
    return LLMRouter(
        providers=providers,  # type: ignore[arg-type]  # FakeProvider is structurally an LLMProvider
        cost_store=store,
        daily_budget_usd=float(kw.get("daily_budget_usd", 10.0)),
        gpu_available=bool(kw.get("gpu_available", False)),
    )


MESSAGES = [Message(role="user", content="hi")]


def test_tier_for_weight_maps_weights() -> None:
    assert tier_for_weight("light", gpu_available=False) == "cloud_free"
    assert tier_for_weight("light", gpu_available=True) == "local_small"
    assert tier_for_weight("medium", gpu_available=False) == "cloud_free"
    assert tier_for_weight("heavy", gpu_available=False) == "cloud_strong"


async def test_light_task_routes_to_cloud_free_on_gpu_less_host() -> None:
    provider = FakeProvider(result=_ok("cloud_free"))
    store = FakeCostStore()
    router = _router({"cloud_free": [provider]}, store)

    result = await router.complete(MESSAGES, weight="light", task_type="chunking")

    assert result.model_tier == "cloud_free"
    assert provider.calls == 1
    assert [r.outcome for r in store.records] == ["success"]
    assert store.records[0].tier == "cloud_free"


async def test_heavy_task_prefers_first_cloud_strong_provider() -> None:
    first = FakeProvider(result=_ok("cloud_strong", cost=1.05), paid=True)
    second = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [first, second]}, store)

    await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert first.calls == 1
    assert second.calls == 0  # preferred provider served it; no failover


async def test_429_fails_over_to_next_provider() -> None:
    failing = FakeProvider(error=_http_error(429), paid=True)
    healthy = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [failing, healthy]}, store)

    result = await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert result.content == "ok"
    assert failing.calls == 1 and healthy.calls == 1
    assert [r.outcome for r in store.records] == ["failure", "success"]


async def test_5xx_fails_over_to_next_provider() -> None:
    failing = FakeProvider(error=_http_error(503), paid=True)
    healthy = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [failing, healthy]}, store)

    await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert failing.calls == 1 and healthy.calls == 1


async def test_401_skips_provider_then_uses_next() -> None:
    bad_key = FakeProvider(error=_http_error(401), paid=True)
    healthy = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [bad_key, healthy]}, store)

    await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert bad_key.calls == 1 and healthy.calls == 1


async def test_402_pauses_and_does_not_fail_over() -> None:
    refusing = FakeProvider(error=BudgetExceededError("out of credit"), paid=True)
    other = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [refusing, other]}, store)

    with pytest.raises(BudgetExceededError):
        await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert other.calls == 0  # never silently escalate past a budget refusal
    assert [r.outcome for r in store.records] == ["refusal"]


async def test_non_retryable_4xx_reraises_without_failover() -> None:
    bad_request = FakeProvider(error=_http_error(400), paid=True)
    other = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [bad_request, other]}, store)

    with pytest.raises(httpx.HTTPStatusError):
        await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert other.calls == 0
    assert [r.outcome for r in store.records] == ["failure"]


async def test_cloud_free_quota_exhaustion_pauses_and_asks() -> None:
    a = FakeProvider(error=_http_error(429))
    b = FakeProvider(error=_http_error(429))
    store = FakeCostStore()
    router = _router({"cloud_free": [a, b]}, store)

    with pytest.raises(QuotaExhaustedError):
        await router.complete(MESSAGES, weight="medium", task_type="extraction")

    assert a.calls == 1 and b.calls == 1
    assert [r.outcome for r in store.records] == ["failure", "failure"]


async def test_budget_cap_blocks_paid_before_dispatch() -> None:
    provider = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore(spend_today=10.0)
    router = _router({"cloud_strong": [provider]}, store, daily_budget_usd=10.0)

    with pytest.raises(BudgetExceededError):
        await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert provider.calls == 0  # fail-closed: never dispatched
    assert [r.outcome for r in store.records] == ["refusal"]


async def test_free_tier_not_blocked_by_paid_cap() -> None:
    provider = FakeProvider(result=_ok("cloud_free"))
    store = FakeCostStore(spend_today=999.0)  # paid budget long gone
    router = _router({"cloud_free": [provider]}, store, daily_budget_usd=10.0)

    result = await router.complete(MESSAGES, weight="medium", task_type="extraction")

    assert result.content == "ok"  # free calls keep working regardless of paid spend
    assert provider.calls == 1


async def test_records_system_derived_usage_on_success() -> None:
    provider = FakeProvider(result=_ok("cloud_strong", cost=1.05), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [provider]}, store)

    await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    row = store.records[0]
    assert row.provider == "FakeProvider"  # system-derived from the serving adapter
    assert row.model == "served-model"
    assert row.task_type == "rewrite"
    assert row.input_tokens == 10 and row.output_tokens == 5
    assert row.cost_estimate == 1.05


async def test_missing_provider_for_tier_is_a_config_error() -> None:
    store = FakeCostStore()
    router = _router({"cloud_free": [FakeProvider(result=_ok("cloud_free"))]}, store)

    with pytest.raises(RouterConfigError):
        await router.complete(MESSAGES, weight="heavy", task_type="rewrite")
