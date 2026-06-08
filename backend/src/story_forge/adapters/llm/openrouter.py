"""OpenRouterProvider — the preferred paid / meta tier (spec §6.5, ADR 0003).

One OpenAI-compatible endpoint reaches most vendor models (Grok/Claude/Gemini/GPT),
so this single hand-rolled adapter is the only paid route built in M2.S2; the
direct per-vendor adapters are added later as needed. It mirrors `OllamaProvider`:
bound to one host/model, an injectable transport for tests, no vendor SDK.

Unlike the free Ollama tiers, a call here costs money, so the adapter reports a
USD `cost_estimate` from its configured per-1k price and the response's token
counts. Two error paths matter and are kept distinct: an HTTP **402** means the
account is out of credit — a spend ceiling, surfaced as `BudgetExceededError` so
the router pauses and asks rather than failing over; every other non-2xx is a
plain `HTTPStatusError` the router discriminates (429/5xx → fail over, 401 → fail
fast).
"""

from __future__ import annotations

import httpx

from story_forge.adapters.llm.base import (
    BudgetExceededError,
    CompletionResult,
    Message,
    ModelTier,
    ProviderResponseError,
    RateLimitKind,
    Usage,
    estimate_cost,
)


class OpenRouterProvider:
    """Calls OpenRouter's OpenAI-compatible `/chat/completions` endpoint."""

    def __init__(
        self,
        *,
        host: str,
        model: str,
        api_key: str,
        cost_per_1k_tokens: tuple[float, float],
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._cost_per_1k_tokens = cost_per_1k_tokens
        self._timeout = timeout
        self._transport = transport  # injected in tests; None uses the real network

    @property
    def cost_per_1k_tokens(self) -> tuple[float, float]:
        """(input, output) USD per 1k tokens for the configured model."""
        return self._cost_per_1k_tokens

    @property
    def rate_limit_kind(self) -> RateLimitKind:
        return "per_minute_tokens"

    async def complete(
        self,
        messages: list[Message],
        model_tier: ModelTier,
        json_schema: dict[str, object] | None = None,
    ) -> CompletionResult:
        payload: dict[str, object] = {
            "model": self._model,
            "messages": [m.model_dump() for m in messages],
            "stream": False,
        }
        if json_schema is not None:
            # OpenAI-compatible structured output: wrap the schema in a named,
            # strict json_schema response_format.
            payload["response_format"] = {
                "type": "json_schema",
                "json_schema": {"name": "output", "schema": json_schema, "strict": True},
            }

        headers = {"Authorization": f"Bearer {self._api_key}"}

        # PAID EGRESS POINT. The per-fragment consent gate ("sending this text to
        # OpenRouter, OK?") is deferred to M2.S5 (ADR 0003 §6 / INV-2): the PoC
        # handles no security-sensitive data, so egress is documented here, not
        # gated. When the M2.S5 panel lands, the consent check goes right here.
        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(
                f"{self._host}/chat/completions", json=payload, headers=headers
            )
            if response.status_code == 402:
                # Out of credit — a spend ceiling, not a transient error.
                raise BudgetExceededError(
                    "OpenRouter refused the call for insufficient credit (HTTP 402)"
                )
            response.raise_for_status()
            try:
                data = response.json()
            except ValueError as exc:
                raise ProviderResponseError(
                    f"OpenRouter returned HTTP 200 with an unparseable body: {exc!r}"
                ) from exc

        # A 200 whose envelope lacks the fields we must read is a malformed response,
        # not a schema-invalid one — raise so the router fails over (OQ-10), distinct
        # from JSON that parses but violates the agent's Pydantic schema.
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise ProviderResponseError(
                f"OpenRouter HTTP 200 response missing expected fields: {exc!r}"
            ) from exc
        if content is None:
            # A null `content` (a content-filter refusal or a tool-call-only reply)
            # is an unusable envelope, not text the agent can validate-and-retry —
            # raise so the router records + fails over, rather than letting a
            # CompletionResult(content=None) raise an uncaught ValidationError.
            raise ProviderResponseError("OpenRouter HTTP 200 response had null message content")

        usage_raw = data.get("usage") or {}
        input_tokens = usage_raw.get("prompt_tokens")
        output_tokens = usage_raw.get("completion_tokens")
        # The served model comes from the response (OpenRouter may route within a
        # model family); fall back to the configured model if absent.
        served_model = data.get("model") or self._model
        usage = Usage(
            model=served_model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            gpu_seconds=None,
            cost_estimate=estimate_cost(input_tokens, output_tokens, self._cost_per_1k_tokens),
        )
        return CompletionResult(content=content, model_tier=model_tier, usage=usage)
