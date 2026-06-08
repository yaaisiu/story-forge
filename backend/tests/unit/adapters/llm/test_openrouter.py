"""Unit tests for `OpenRouterProvider` — request shape, usage parsing, refusals.

No network: `httpx.MockTransport` intercepts the call, so we assert what the
provider *sends* (endpoint, model, structured-output `response_format`, bearer
auth) and how it parses the OpenAI-compatible response — including the
system-derived usage fields and the control-first cap-refusal path (HTTP 402 →
`BudgetExceededError`, the "pause and ask" signal, not a fail-over error).
"""

from __future__ import annotations

import json

import httpx
import pytest

from story_forge.adapters.llm.base import (
    BudgetExceededError,
    Message,
    ProviderResponseError,
)
from story_forge.adapters.llm.openrouter import OpenRouterProvider

FAKE_KEY = "k"  # non-keyword var name so detect-secrets ignores the literal


def _chat_response(content: str = "hi there") -> dict[str, object]:
    return {
        "model": "anthropic/claude-3.5-sonnet",
        "choices": [{"message": {"role": "assistant", "content": content}}],
        "usage": {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150},
    }


async def test_posts_chat_completions_and_parses_content_and_usage() -> None:
    captured: dict[str, object] = {}
    bearer_value = "or-key-value"  # non-keyword var name so detect-secrets ignores the literal

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json=_chat_response())

    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1/",  # trailing slash should be normalized away
        model="anthropic/claude-3.5-sonnet",
        api_key=bearer_value,
        cost_per_1k_tokens=(3.0, 15.0),
        transport=httpx.MockTransport(handler),
    )
    result = await provider.complete(
        [Message(role="user", content="hello")],
        "cloud_strong",
        {"type": "object"},
    )

    assert result.content == "hi there"
    assert result.model_tier == "cloud_strong"
    assert captured["url"] == "https://openrouter.ai/api/v1/chat/completions"
    assert captured["auth"] == "Bearer or-key-value"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "anthropic/claude-3.5-sonnet"
    assert body["stream"] is False
    assert body["messages"] == [{"role": "user", "content": "hello"}]

    # Usage is system-derived: the served model comes from the response, token
    # counts from `usage`, and cost from this provider's price (100/1k*3 + 50/1k*15).
    assert result.usage.model == "anthropic/claude-3.5-sonnet"
    assert result.usage.input_tokens == 100
    assert result.usage.output_tokens == 50
    assert result.usage.gpu_seconds is None
    assert result.usage.cost_estimate == pytest.approx(1.05)


async def test_sends_response_format_when_schema_given() -> None:
    captured: dict[str, object] = {}
    schema = {"type": "object", "properties": {"name": {"type": "string"}}}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_chat_response())

    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="x",
        api_key=FAKE_KEY,
        cost_per_1k_tokens=(1.0, 1.0),
        transport=httpx.MockTransport(handler),
    )
    await provider.complete([Message(role="user", content="hi")], "cloud_strong", schema)

    body = captured["body"]
    assert isinstance(body, dict)
    response_format = body["response_format"]
    assert isinstance(response_format, dict)
    assert response_format["type"] == "json_schema"
    assert response_format["json_schema"]["schema"] == schema


async def test_omits_response_format_when_no_schema() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json=_chat_response())

    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="x",
        api_key=FAKE_KEY,
        cost_per_1k_tokens=(1.0, 1.0),
        transport=httpx.MockTransport(handler),
    )
    await provider.complete([Message(role="user", content="hi")], "cloud_strong")

    body = captured["body"]
    assert isinstance(body, dict)
    assert "response_format" not in body


async def test_402_credit_exhaustion_raises_budget_exceeded() -> None:
    # OpenRouter returns 402 when the account is out of credit. That is a spend
    # ceiling, not a transient failure: surface the pause-and-ask signal, never a
    # fail-over HTTP error (control-first, ADR 0003).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"error": {"message": "Insufficient credits"}})

    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="x",
        api_key=FAKE_KEY,
        cost_per_1k_tokens=(1.0, 1.0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(BudgetExceededError):
        await provider.complete([Message(role="user", content="hi")], "cloud_strong")


async def test_other_http_error_raises_status_error() -> None:
    # A 5xx (or 429/401) is the router's discrimination job (fail over / fail
    # fast) — the adapter surfaces it as a plain HTTP error, like OllamaProvider.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "upstream unavailable"})

    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="x",
        api_key=FAKE_KEY,
        cost_per_1k_tokens=(1.0, 1.0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.complete([Message(role="user", content="hi")], "cloud_strong")


async def test_malformed_200_envelope_raises_provider_response_error() -> None:
    # A 200 whose body lacks `choices[0].message.content` is a malformed envelope
    # (OQ-10), distinct from a 5xx and from schema-invalid content. The adapter must
    # raise ProviderResponseError so the router records + fails over, not crash with
    # a raw KeyError the router doesn't catch.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape", "usage": {}})

    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="x",
        api_key=FAKE_KEY,
        cost_per_1k_tokens=(1.0, 1.0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderResponseError):
        await provider.complete([Message(role="user", content="hi")], "cloud_strong")


async def test_null_content_200_raises_provider_response_error() -> None:
    # A 200 whose `message.content` is null (a content-filter refusal or a
    # tool-call-only reply) is an unusable envelope: it must raise so the router
    # records + fails over, NOT pass content=None through to CompletionResult where
    # it would raise an uncaught ValidationError (no ledger row, no failover).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "model": "m",
                "choices": [{"message": {"role": "assistant", "content": None}}],
                "usage": {"prompt_tokens": 1, "completion_tokens": 0},
            },
        )

    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="x",
        api_key=FAKE_KEY,
        cost_per_1k_tokens=(1.0, 1.0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderResponseError):
        await provider.complete([Message(role="user", content="hi")], "cloud_strong")


async def test_unparseable_200_body_raises_provider_response_error() -> None:
    # A 200 with a non-JSON body (e.g. an HTML error page) is also a malformed
    # envelope — same handling, raised at the parse step.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>not json</html>")

    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="x",
        api_key=FAKE_KEY,
        cost_per_1k_tokens=(1.0, 1.0),
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderResponseError):
        await provider.complete([Message(role="user", content="hi")], "cloud_strong")


def test_cost_and_rate_limit_properties() -> None:
    provider = OpenRouterProvider(
        host="https://openrouter.ai/api/v1",
        model="x",
        api_key=FAKE_KEY,
        cost_per_1k_tokens=(3.0, 15.0),
    )
    assert provider.cost_per_1k_tokens == (3.0, 15.0)
    assert provider.rate_limit_kind == "per_minute_tokens"
