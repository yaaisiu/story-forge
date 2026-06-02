"""OllamaProvider — the local-small and cloud-free tiers (spec §6.5).

Both tiers speak the same Ollama chat API, so one adapter serves both: the only
difference is the host (and an API key for the cloud-free tier). An instance is
bound to one host/model — the router (later) holds one instance per tier. The
`model_tier` argument is recorded on the result so callers/logs see which tier
served the call.

Both tiers are free of USD charge, so `cost_per_1k_tokens` is (0, 0); the cloud
tier is metered by Ollama Cloud's GPU-time session quota, the local tier not at
all (`rate_limit_kind`). Ollama still returns `prompt_eval_count` / `eval_count`,
and we keep them on `Usage` — the §6.6 ledger records token counts for every tier
that reports them, even the free ones (INV-5).
"""

from __future__ import annotations

import httpx

from story_forge.adapters.llm.base import (
    CompletionResult,
    Message,
    ModelTier,
    RateLimitKind,
    Usage,
    estimate_cost,
)


class OllamaProvider:
    """Calls an Ollama `/api/chat` endpoint (local daemon or Ollama Cloud)."""

    def __init__(
        self,
        *,
        host: str,
        model: str,
        api_key: str | None = None,
        timeout: float = 120.0,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._host = host.rstrip("/")
        self._model = model
        self._api_key = api_key
        self._timeout = timeout
        self._transport = transport  # injected in tests; None uses the real network

    @property
    def cost_per_1k_tokens(self) -> tuple[float, float]:
        """Both the local and the Ollama Cloud free tier carry no USD charge."""
        return (0.0, 0.0)

    @property
    def rate_limit_kind(self) -> RateLimitKind:
        """Cloud-free (API key set) is metered by GPU-time session quota; local isn't."""
        return "session_gpu_time" if self._api_key else "none"

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
            # Ollama takes a JSON Schema in `format` to constrain structured output.
            payload["format"] = json_schema

        headers = {}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"

        async with httpx.AsyncClient(timeout=self._timeout, transport=self._transport) as client:
            response = await client.post(f"{self._host}/api/chat", json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()

        # Ollama reports token counts at the top level; absent on some responses,
        # so read defensively. GPU-seconds is Ollama Cloud's billing unit and is
        # not in the chat response — it's surfaced via the quota endpoint (M2.S5).
        input_tokens = data.get("prompt_eval_count")
        output_tokens = data.get("eval_count")
        usage = Usage(
            model=self._model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            gpu_seconds=None,
            cost_estimate=estimate_cost(input_tokens, output_tokens, self.cost_per_1k_tokens),
        )
        return CompletionResult(
            content=data["message"]["content"], model_tier=model_tier, usage=usage
        )
