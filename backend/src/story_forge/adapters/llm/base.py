"""The `LLMProvider` Protocol and its data types (spec §6.5/§6.6).

Agents depend on this Protocol, never on a concrete adapter — that is what keeps
an agent unit-testable against a mock. The three tiers (`local_small`,
`cloud_free`, `cloud_strong`) are a `ModelTier` literal; the caller (today an
agent, later the router) picks one per call.

Every call returns `Usage` alongside the text: the §6.6 cost ledger records one
row per call, so the provider reports what it actually spent (tokens whenever the
provider returns them, GPU-seconds for Ollama Cloud, an estimated USD cost for
paid tiers). Usage is **system-derived** by the adapter that served the call — it
is never echoed from the caller, so the ledger can't be lied to. The Protocol also
exposes `cost_per_1k_tokens` and `rate_limit_kind` so the router can pick and the
dashboard can show price/quota without calling the provider.
"""

from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

ModelTier = Literal["local_small", "cloud_free", "cloud_strong"]
RateLimitKind = Literal["none", "session_gpu_time", "per_minute_tokens"]

# A task's relative weight; the router maps it to a `ModelTier` (spec §6.5). It lives
# here, beside `ModelTier`, rather than in the concrete `router` module so agents can
# type against the orchestrating `Router` Protocol below without importing the adapter
# (the layering rule keeps agents free of concrete adapters). Promoted here when the
# third router-driven agent appeared (JudgeAgent) — the rule-of-three trigger noted in
# the agents that previously kept a local mirror.
TaskWeight = Literal["light", "medium", "heavy"]


class BudgetExceededError(RuntimeError):
    """A spend ceiling was hit — the caller must pause and ask the user, not retry.

    Control-first (spec §6.6, ADR 0003): the router raises this from its
    fail-closed pre-dispatch check when `DAILY_BUDGET_USD` is reached, and a paid
    adapter raises it when the provider itself refuses for lack of credit (e.g.
    OpenRouter's HTTP 402). It is deliberately *not* an HTTP error: 429/5xx mean
    "fail over to the next provider", but a budget refusal means "stop and ask" —
    the router never silently escalates to more spend.
    """


class ProviderResponseError(RuntimeError):
    """A provider returned HTTP 200 but an unparseable / malformed envelope.

    The body isn't JSON, or it lacks the fields the adapter must read (e.g.
    `choices[0].message.content`), or `content` is null. This is a poison-message:
    retrying the same request breaks the consumer identically every time, so the
    cure is quarantine-and-move-on, not retry. The adapter raises it at the envelope-unwrap
    point; the router treats it like a 5xx — record a failure row, mark it non-quota,
    and fail over to the next provider (spec §6.5/§11 envelope-vs-schema split, OQ-10).

    Distinct from a *schema-invalid* body: a well-formed envelope whose `content` is
    JSON that violates the agent's Pydantic schema is the agent's concern (prompt
    retry), not the router's. Keep the offending body out of the message — it may
    contain the API key (INV-6) or story text (OQ-4); carry only the structural cause.
    """


class QuotaExhaustedError(RuntimeError):
    """The free tier's quota is spent across every configured provider.

    Control-first (spec §6.5, ADR 0003): when `cloud_free` exhausts its Ollama
    Cloud GPU-time quota and no sibling free provider can serve the call, the
    router raises this to pause and ask the user — it never silently escalates to
    a paid tier. Distinct from `BudgetExceededError`, which is the USD cap.
    """


class Message(BaseModel):
    """One chat turn, matching the Ollama / OpenAI chat-message shape."""

    role: Literal["system", "user", "assistant"]
    content: str


class Usage(BaseModel):
    """Per-call accounting for the §6.6 cost ledger, system-derived by the adapter.

    All counts are nullable because not every tier reports every unit: free Ollama
    returns token counts but no USD cost; Ollama Cloud bills in GPU-seconds, not
    tokens; a provider may omit usage entirely on an error response.
    """

    model: str  # the concrete model string the adapter sent (not the caller's label)
    input_tokens: int | None = None
    output_tokens: int | None = None
    gpu_seconds: float | None = None  # Ollama Cloud's billing unit
    cost_estimate: float | None = None  # USD, paid tiers only


class CompletionResult(BaseModel):
    """What a provider returns: the text, which tier served it, and what it cost."""

    content: str
    model_tier: ModelTier
    usage: Usage


def estimate_cost(
    input_tokens: int | None,
    output_tokens: int | None,
    cost_per_1k_tokens: tuple[float, float],
) -> float | None:
    """USD estimate from token counts and a provider's (input, output) per-1k price.

    Returns `None` when either token count is missing (no honest figure to record)
    or the provider is free (zero price → no cost row to clutter the ledger).
    """
    if input_tokens is None or output_tokens is None:
        return None
    price_in, price_out = cost_per_1k_tokens
    if price_in == 0 and price_out == 0:
        return None
    return (input_tokens / 1000) * price_in + (output_tokens / 1000) * price_out


class Router(Protocol):
    """The orchestrating completion contract an agent calls — the router's public face.

    Agents type against this, never the concrete `LLMRouter`, so they stay unit-testable
    against a mock and free of the adapter module; `LLMRouter` structurally satisfies it.
    Distinct from `LLMProvider`: a provider runs one concrete model at a *given* tier,
    while the router picks the tier from `weight`, fails over across providers within it,
    enforces the budget cap, and writes the cost ledger (spec §6.5/§6.6). The schema-retry
    on invalid output stays the *agent's* job, not the router's (the M2.S3 split).
    """

    async def complete(
        self,
        messages: list[Message],
        *,
        weight: TaskWeight,
        task_type: str,
        json_schema: dict[str, object] | None = None,
    ) -> CompletionResult:
        """Run a completion for `task_type` at the tier implied by `weight`."""
        ...


@runtime_checkable
class LLMProvider(Protocol):
    """Async chat-completion contract every provider implements."""

    @property
    def cost_per_1k_tokens(self) -> tuple[float, float]:
        """(input, output) USD per 1k tokens; (0, 0) for free tiers."""
        ...

    @property
    def rate_limit_kind(self) -> RateLimitKind:
        """How this provider rate-limits — drives the router's quota handling."""
        ...

    async def complete(
        self,
        messages: list[Message],
        model_tier: ModelTier,
        json_schema: dict[str, object] | None = None,
    ) -> CompletionResult:
        """Run a completion. `json_schema`, when given, asks for structured output."""
        ...
