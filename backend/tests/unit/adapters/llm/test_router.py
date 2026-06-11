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
    ProviderResponseError,
    QuotaExhaustedError,
    Usage,
)
from story_forge.adapters.llm.cost import LlmCallRecord
from story_forge.adapters.llm.openrouter import OpenRouterProvider
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
    extra: dict[str, object] = {}
    if "clock" in kw:
        extra["clock"] = kw["clock"]
    return LLMRouter(
        providers=providers,  # type: ignore[arg-type]  # FakeProvider is structurally an LLMProvider
        cost_store=store,
        daily_budget_usd=float(kw.get("daily_budget_usd", 10.0)),
        gpu_available=bool(kw.get("gpu_available", False)),
        **extra,  # type: ignore[arg-type]
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


async def test_cloud_free_bad_key_raises_real_error_not_quota() -> None:
    # All free providers fail with 401: a misconfiguration, NOT quota exhaustion.
    # Surface the real error instead of crying "pause, quota spent".
    a = FakeProvider(error=_http_error(401))
    b = FakeProvider(error=_http_error(401))
    store = FakeCostStore()
    router = _router({"cloud_free": [a, b]}, store)

    with pytest.raises(httpx.HTTPStatusError):
        await router.complete(MESSAGES, weight="medium", task_type="extraction")


async def test_cloud_free_outage_after_rate_limit_raises_error_not_quota() -> None:
    # A 429 then a 5xx: the outage means this isn't pure quota exhaustion, so the
    # real (last) error surfaces rather than QuotaExhaustedError.
    a = FakeProvider(error=_http_error(429))
    b = FakeProvider(error=_http_error(503))
    store = FakeCostStore()
    router = _router({"cloud_free": [a, b]}, store)

    with pytest.raises(httpx.HTTPStatusError) as caught:
        await router.complete(MESSAGES, weight="medium", task_type="extraction")
    assert caught.value.response.status_code == 503


async def test_transport_error_fails_over_to_next_provider() -> None:
    # A connect/timeout error is a network failure: spec §6.5 fails over on it,
    # and the failed attempt is still recorded.
    failing = FakeProvider(error=httpx.ConnectError("connection refused"), paid=True)
    healthy = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [failing, healthy]}, store)

    result = await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert result.content == "ok"
    assert failing.calls == 1 and healthy.calls == 1
    assert [r.outcome for r in store.records] == ["failure", "success"]


async def test_transport_error_exhaustion_raises_the_transport_error() -> None:
    only = FakeProvider(error=httpx.ConnectError("connection refused"), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [only]}, store)

    with pytest.raises(httpx.ConnectError):
        await router.complete(MESSAGES, weight="heavy", task_type="rewrite")
    assert [r.outcome for r in store.records] == ["failure"]


async def test_malformed_envelope_records_failure_and_fails_over() -> None:
    # OQ-10: a 200 with a malformed envelope (the real OpenRouterProvider raising
    # ProviderResponseError) is treated like a 5xx — record a failure row and fail
    # over to the next provider, rather than crashing with no row.
    def malformed(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    fake_key = "k"  # bound to a var per backend/AGENTS.md credential-literal rule
    bad = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="m",
        api_key=fake_key,
        cost_per_1k_tokens=(3.0, 15.0),
        transport=httpx.MockTransport(malformed),
    )
    healthy = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [bad, healthy]}, store)

    result = await router.complete(MESSAGES, weight="heavy", task_type="extraction")

    assert result.content == "ok"
    assert [r.outcome for r in store.records] == ["failure", "success"]


async def test_malformed_envelope_exhaustion_is_not_quota() -> None:
    # Malformed envelopes across every cloud_free provider are NOT quota exhaustion
    # (a defective response is a provider fault, like a 5xx): the router re-raises
    # the real ProviderResponseError, never QuotaExhaustedError.
    a = FakeProvider(error=ProviderResponseError("bad envelope"))
    b = FakeProvider(error=ProviderResponseError("bad envelope"))
    store = FakeCostStore()
    router = _router({"cloud_free": [a, b]}, store)

    with pytest.raises(ProviderResponseError):
        await router.complete(MESSAGES, weight="medium", task_type="extraction")

    assert a.calls == 1 and b.calls == 1
    assert [r.outcome for r in store.records] == ["failure", "failure"]


async def test_schema_invalid_body_is_a_success_for_the_router() -> None:
    # The envelope-vs-schema split (OQ-10): a *well-formed* envelope whose `content`
    # is JSON that would violate an agent's Pydantic schema is the agent's concern
    # (prompt retry), not the router's. The router records a SUCCESS and returns the
    # content unchanged — it never inspects the body's domain shape.
    def well_formed_but_schema_invalid(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "m",
                "choices": [{"message": {"content": '{"entities": "not-a-list"}'}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 1},
            },
        )

    fake_key = "k"  # bound to a var per backend/AGENTS.md credential-literal rule
    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="m",
        api_key=fake_key,
        cost_per_1k_tokens=(3.0, 15.0),
        transport=httpx.MockTransport(well_formed_but_schema_invalid),
    )
    store = FakeCostStore()
    router = _router({"cloud_strong": [provider]}, store)

    result = await router.complete(MESSAGES, weight="heavy", task_type="extraction")

    assert result.content == '{"entities": "not-a-list"}'
    assert [r.outcome for r in store.records] == ["success"]


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


def _clock(*ticks: float) -> object:
    """A fake monotonic clock yielding the given readings (seconds) in order."""
    it = iter(ticks)
    return lambda: next(it)


async def test_records_latency_ms_around_the_provider_call() -> None:
    # OQ-9: every dispatched call records wall-clock latency (ms) measured around
    # provider.complete. A fake monotonic clock advances 0.25 s across the call.
    provider = FakeProvider(result=_ok("cloud_strong", cost=1.05), paid=True)
    store = FakeCostStore()
    router = _router({"cloud_strong": [provider]}, store, clock=_clock(1.0, 1.25))

    await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert store.records[0].latency_ms == 250


async def test_records_latency_for_each_attempt_including_the_failed_one() -> None:
    # Each provider attempt is timed independently: the failed attempt's failure
    # row carries the time it took to fail, the successful failover its own.
    failing = FakeProvider(error=_http_error(503), paid=True)
    healthy = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore()
    router = _router(
        {"cloud_strong": [failing, healthy]},
        store,
        clock=_clock(1.0, 1.1, 5.0, 5.2),  # fail in 100 ms, succeed in 200 ms
    )

    await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert [r.latency_ms for r in store.records] == [100, 200]


async def test_predispatch_budget_refusal_records_no_latency() -> None:
    # The fail-closed cap refuses *before* any provider call, so there is no
    # wall-clock to measure: latency_ms is None and the clock is never read.
    provider = FakeProvider(result=_ok("cloud_strong"), paid=True)
    store = FakeCostStore(spend_today=10.0)

    def forbidden_clock() -> float:
        raise AssertionError("clock must not be read when nothing was dispatched")

    router = _router(
        {"cloud_strong": [provider]}, store, daily_budget_usd=10.0, clock=forbidden_clock
    )

    with pytest.raises(BudgetExceededError):
        await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert store.records[0].latency_ms is None


async def test_missing_provider_for_tier_is_a_config_error() -> None:
    store = FakeCostStore()
    router = _router({"cloud_free": [FakeProvider(result=_ok("cloud_free"))]}, store)

    with pytest.raises(RouterConfigError):
        await router.complete(MESSAGES, weight="heavy", task_type="rewrite")


async def test_routes_a_real_openrouter_provider_and_records_the_row() -> None:
    # The M2.S2 "Done when": a routed cloud_strong call via the real
    # OpenRouterProvider (mock transport) returns and records a usage row whose
    # tokens/cost were parsed from the provider's response — the full chain, not
    # a fake provider.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "anthropic/claude-3.5-sonnet",
                "choices": [{"message": {"role": "assistant", "content": "rewritten"}}],
                "usage": {"prompt_tokens": 100, "completion_tokens": 50},
            },
        )

    fake_key = "k"  # bound to a var per backend/AGENTS.md credential-literal rule
    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="anthropic/claude-3.5-sonnet",
        api_key=fake_key,
        cost_per_1k_tokens=(3.0, 15.0),
        transport=httpx.MockTransport(handler),
    )
    store = FakeCostStore()
    router = _router({"cloud_strong": [provider]}, store)

    result = await router.complete(MESSAGES, weight="heavy", task_type="rewrite")

    assert result.content == "rewritten"
    row = store.records[0]
    assert row.outcome == "success"
    assert row.provider == "OpenRouterProvider"
    assert row.model == "anthropic/claude-3.5-sonnet"
    assert row.input_tokens == 100 and row.output_tokens == 50
    assert row.cost_estimate == pytest.approx(1.05)  # 100/1k*3 + 50/1k*15
