"""OllamaProvider — the local-small and cloud-free tiers (spec §6.5).

Both tiers speak the same Ollama chat API, so one adapter serves both: the only
difference is the host (and an API key for the cloud-free tier). An instance is
bound to one host/model — the router (later) holds one instance per tier. The
`model_tier` argument is recorded on the result so callers/logs see which tier
served the call.
"""

from __future__ import annotations

import httpx

from story_forge.adapters.llm.base import CompletionResult, Message, ModelTier


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

        return CompletionResult(content=data["message"]["content"], model_tier=model_tier)
