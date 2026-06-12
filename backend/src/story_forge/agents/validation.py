"""Shared validate-and-retry loop for agents that parse structured LLM output.

Every agent that asks an LLM for JSON runs the same loop: call the model, strip any
markdown code fence, validate the body against the agent's Pydantic schema, and on a
*schema* failure retry the prompt a bounded number of times before giving up. That loop
was copied near-verbatim in `ChunkingAgent` and `ExtractionAgent`; `JudgeAgent` is the
third occurrence, so it moved here (the rule-of-three fold the M2.S3 review flagged).

Each agent still owns the parts that are genuinely its own — its *schema* (passed as
`model`), its *call shape* (the `call` thunk: a raw provider vs the router, the weight /
task_type), and its *give-up error* (`error` + `label`). Only the mechanical loop is
shared.

The loop retries *parse/schema* failures only. Transport/envelope failover is the
router's job, and the pause-and-ask control signals (`BudgetExceededError` /
`QuotaExhaustedError`) are the user's call — a `call` that raises any of these propagates
straight through, never retried (spending more or failing over is not a prompt problem).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from pydantic import BaseModel, ValidationError

from story_forge.adapters.llm.base import CompletionResult
from story_forge.agents.json_output import extract_json


async def validate_with_retry[T: BaseModel](
    model: type[T],
    call: Callable[[], Awaitable[CompletionResult]],
    *,
    max_retries: int,
    error: Callable[[str], Exception],
    label: str,
) -> T:
    """Call `call`, validate its content against `model`, retrying on schema failure.

    Returns the validated model on the first parseable + valid response. On a malformed
    or schema-invalid body, retries up to `max_retries` further times (a sampling model
    can return valid JSON on a later pass); after exhausting them, raises `error(<msg>)`
    chained from the last `ValidationError`, mirroring each agent's prior give-up.
    """
    if max_retries < 0:
        # A negative budget would make the loop never run, then raise a "0 attempts"
        # give-up chained from no error — guard it at the shared boundary instead.
        raise ValueError(f"max_retries must be non-negative, got {max_retries}")
    last_error: ValidationError | None = None
    for _ in range(max_retries + 1):
        result = await call()
        try:
            return model.model_validate_json(extract_json(result.content))
        except ValidationError as exc:  # covers malformed JSON and schema violations
            last_error = exc
    raise error(
        f"{label} output failed validation after {max_retries + 1} attempts"
    ) from last_error
