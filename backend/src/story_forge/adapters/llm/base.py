"""The `LLMProvider` Protocol and its data types (spec §6.5).

Agents depend on this Protocol, never on a concrete adapter — that is what keeps
an agent unit-testable against a mock. The three tiers (`local_small`,
`cloud_free`, `cloud_strong`) are a `ModelTier` literal; the caller (today an
agent, later the router) picks one per call.

Scope note: spec §6.5 also lists `cost_per_1k_tokens` and `rate_limit_kind` on
the Protocol. Those exist to feed the cascade router and the token-budget
dashboard (§6.6), neither of which exists yet — adding them now would be an
unused abstraction, so they land with the router/budget work. For now the
Protocol carries only what an agent actually calls: `complete`.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

ModelTier = Literal["local_small", "cloud_free", "cloud_strong"]


class Message(BaseModel):
    """One chat turn, matching the Ollama / OpenAI chat-message shape."""

    role: Literal["system", "user", "assistant"]
    content: str


class CompletionResult(BaseModel):
    """What a provider returns: the text plus which tier actually served it."""

    content: str
    model_tier: ModelTier


@runtime_checkable
class LLMProvider(Protocol):
    """Async chat-completion contract every provider implements."""

    async def complete(
        self,
        messages: list[Message],
        model_tier: ModelTier,
        json_schema: dict[str, object] | None = None,
    ) -> CompletionResult:
        """Run a completion. `json_schema`, when given, asks for structured output."""
        ...
