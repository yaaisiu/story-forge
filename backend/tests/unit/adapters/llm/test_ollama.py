"""Unit tests for `OllamaProvider` — request shape + response parsing.

No network: `httpx.MockTransport` intercepts the call, so we assert what the
provider *sends* (endpoint, model, structured-output `format`, auth header) and
that it parses the chat response back into a `CompletionResult`.
"""

from __future__ import annotations

import json

import httpx
import pytest

from story_forge.adapters.llm.base import Message, ProviderResponseError
from story_forge.adapters.llm.ollama import OllamaProvider


async def test_posts_chat_request_and_parses_content() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["body"] = json.loads(request.content)
        captured["has_auth"] = "authorization" in {k.lower() for k in request.headers}
        return httpx.Response(200, json={"message": {"role": "assistant", "content": "hi there"}})

    provider = OllamaProvider(
        host="http://127.0.0.1:11434/",  # trailing slash should be normalized away
        model="qwen3.5",
        transport=httpx.MockTransport(handler),
    )
    result = await provider.complete(
        [Message(role="user", content="hello")],
        "local_small",
        {"type": "object"},
    )

    assert result.content == "hi there"
    assert result.model_tier == "local_small"
    assert captured["url"] == "http://127.0.0.1:11434/api/chat"
    body = captured["body"]
    assert isinstance(body, dict)
    assert body["model"] == "qwen3.5"
    assert body["stream"] is False
    assert body["format"] == {"type": "object"}
    assert body["messages"] == [{"role": "user", "content": "hello"}]
    # No API key configured → no Authorization header leaks out.
    assert captured["has_auth"] is False


async def test_omits_format_when_no_schema() -> None:
    captured: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(200, json={"message": {"content": "x"}})

    provider = OllamaProvider(
        host="http://127.0.0.1:11434",
        model="qwen3.5",
        transport=httpx.MockTransport(handler),
    )
    await provider.complete([Message(role="user", content="hi")], "local_small")

    body = captured["body"]
    assert isinstance(body, dict)
    assert "format" not in body


async def test_sends_bearer_token_for_cloud_free() -> None:
    seen: dict[str, str | None] = {}
    cloud_key = "abc123-token-value"  # bound to a var so detect-secrets ignores it

    def handler(request: httpx.Request) -> httpx.Response:
        seen["auth"] = request.headers.get("authorization")
        return httpx.Response(200, json={"message": {"content": "x"}})

    provider = OllamaProvider(
        host="https://ollama.com",
        model="gpt-oss:120b-cloud",
        api_key=cloud_key,
        transport=httpx.MockTransport(handler),
    )
    await provider.complete([Message(role="user", content="hi")], "cloud_free")

    assert seen["auth"] == f"Bearer {cloud_key}"


async def test_keeps_token_counts_from_response() -> None:
    # Ollama reports prompt_eval_count / eval_count; the §6.6 ledger keeps them
    # even though this tier is free (INV-5) — they are not discarded.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "message": {"content": "x"},
                "prompt_eval_count": 42,
                "eval_count": 17,
            },
        )

    provider = OllamaProvider(
        host="http://127.0.0.1:11434",
        model="qwen3.5",
        transport=httpx.MockTransport(handler),
    )
    result = await provider.complete([Message(role="user", content="hi")], "local_small")

    assert result.usage.model == "qwen3.5"
    assert result.usage.input_tokens == 42
    assert result.usage.output_tokens == 17
    assert result.usage.gpu_seconds is None
    # Free tier → no USD figure even though tokens are known.
    assert result.usage.cost_estimate is None


async def test_usage_tokens_none_when_response_omits_them() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"content": "x"}})

    provider = OllamaProvider(
        host="http://127.0.0.1:11434",
        model="qwen3.5",
        transport=httpx.MockTransport(handler),
    )
    result = await provider.complete([Message(role="user", content="hi")], "local_small")

    assert result.usage.input_tokens is None
    assert result.usage.output_tokens is None


def test_cost_and_rate_limit_reflect_tier() -> None:
    fake_key = "k"  # bound to a var per backend/AGENTS.md credential-literal rule
    local = OllamaProvider(host="http://127.0.0.1:11434", model="qwen3.5")
    cloud = OllamaProvider(host="https://ollama.com", model="gpt-oss:120b-cloud", api_key=fake_key)

    assert local.cost_per_1k_tokens == (0.0, 0.0)
    assert cloud.cost_per_1k_tokens == (0.0, 0.0)
    assert local.rate_limit_kind == "none"
    assert cloud.rate_limit_kind == "session_gpu_time"


async def test_raises_on_http_error_status() -> None:
    # A 5xx from Ollama surfaces as an HTTP error (the router handles failover
    # later; the provider does not silently swallow it).
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "model loading"})

    provider = OllamaProvider(
        host="http://127.0.0.1:11434",
        model="qwen3.5",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(httpx.HTTPStatusError):
        await provider.complete([Message(role="user", content="hi")], "local_small")


async def test_malformed_200_envelope_raises_provider_response_error() -> None:
    # A 200 lacking `message.content` is a malformed envelope (OQ-10): raise the
    # typed error so the router records + fails over, not a raw KeyError it can't
    # catch.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"unexpected": "shape"})

    provider = OllamaProvider(
        host="http://127.0.0.1:11434",
        model="qwen3.5",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderResponseError):
        await provider.complete([Message(role="user", content="hi")], "local_small")


async def test_null_content_200_raises_provider_response_error() -> None:
    # A 200 whose `message.content` is null is an unusable envelope: raise so the
    # router records + fails over, not pass content=None through to a
    # CompletionResult that raises an uncaught ValidationError.
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"message": {"role": "assistant", "content": None}})

    provider = OllamaProvider(
        host="http://127.0.0.1:11434",
        model="qwen3.5",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(ProviderResponseError):
        await provider.complete([Message(role="user", content="hi")], "local_small")
