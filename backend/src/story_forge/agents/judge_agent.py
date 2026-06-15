"""JudgeAgent — Stage 3 of the §3.3 dedupe cascade (M3.S3), the LLM-as-judge rung.

Stage 3 is reached only on candidates Stages 1–2 left *ambiguous* (a mid-confidence
fuzzy match the embedding cosine could not resolve). It is the **only** cascade rung that
burns LLM tokens, and only on those ambiguous cases (spec §3.3 cost optimization). The
agent asks the model one question — "is this candidate the same entity as this existing
one?" — and gets back a strict verdict `{match, confidence, reasoning}`.

Like `ExtractionAgent`, it is wired to the **router** (not a raw provider): it calls
`router.complete(..., weight="medium", task_type="judge")`, which spec §6.5 maps to the
`cloud_free` tier (DM5 — spec-settled). Tier selection, failover, the budget cap, and the
cost ledger live in the router; the agent owns only the *prompt-retry* axis — render →
call → parse + validate → retry on schema failure — via the shared `validate_with_retry`.

The output schema is **strict** (§3.3): a parseable-but-degenerate body (confidence out
of [0,1], blank reasoning) must *fail* validation and trigger a retry, never pass. The
agent's "couldn't judge" contract is **total**: it raises `JudgeError` on *any* failure to
produce a verdict — schema give-up after retries, **and** a terminal transport/envelope
failure (provider unreachable / unusable envelope after the router's failover). Only the
pause-and-ask control signals (`BudgetExceededError` / `QuotaExhaustedError`) propagate
untouched. The cascade maps `JudgeError` to a fail-closed "uncertain → review queue", so a
flaky *or unreachable* judge never silently drops a candidate, auto-merges, or aborts the
batch (the [[fail-closed]] rule).

Both this and the verdict→outcome mapping only *propose* (INV-1: a human commits at Stage
4). Built proposal-only and **unwired** through M3.S3 — the cascade is wired into the live
extraction path with the review queue + the DM6 write-path refactor (M3.S4).
"""

from __future__ import annotations

import json

import httpx
from pydantic import BaseModel, Field, field_validator

from story_forge.adapters.llm.base import ProviderResponseError, Router
from story_forge.agents.matching_agent import MatchOutcome
from story_forge.agents.validation import validate_with_retry
from story_forge.config import settings
from story_forge.prompts import PromptNotFound, render_messages


class ExistingEntityContext(BaseModel):
    """The existing graph entity Stage 3 judges a candidate against (spec Appendix C.3).

    Carries the entity's resolved identity plus the **aliases, type, properties, and recent
    mentions** the judge reasons over — the full existing-entity side of the C.3 prompt.
    `aliases` matters most: Stage 3 exists to resolve diminutives/variants (Bronek↔Bronisław),
    and aliases are the recorded variants the graph already knows. All free text here is
    author-derived but graph-stored — it is rendered into the trusted template body, never
    trusted to define prompt structure (spec §6.7 prompt-injection rule; see the injection test).
    """

    id: str
    canonical_name: str
    aliases: list[str] = Field(default_factory=list)
    type: str
    properties: dict[str, object] = Field(default_factory=dict)
    recent_mentions: list[str] = Field(default_factory=list)


class JudgeVerdict(BaseModel):
    """The strict §3.3 Stage-3 LLM output: `{match, confidence, reasoning}`.

    `confidence` is the model's certainty that the two are the *same* entity (the prompt
    defines it so), bounded to [0, 1] — an out-of-range value is a degenerate body that
    must fail and retry, not pass. `reasoning` must be non-empty: a blank justification is
    useless to the Stage-4 reviewer, so it is rejected like a blank candidate name.
    """

    match: bool
    confidence: float = Field(ge=0.0, le=1.0)
    reasoning: str

    @field_validator("reasoning")
    @classmethod
    def _reasoning_non_empty(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("reasoning must be a non-empty justification")
        return value


class Stage3Result(BaseModel):
    """Stage 3's proposal for one candidate — merge or new/uncertain, never a write.

    `outcome` is only ever `auto-merge-proposed` or `new-proposed`: the judge is the
    cascade's last automated rung, so it never produces `ambiguous` (nothing further to
    escalate to). `target_entity_id` carries the judged entity on a merge proposal and is
    `None` on `new-proposed`, mirroring Stage 1/2. `verdict` keeps the model's reasoning
    for the Stage-4 review queue (§3.3 "Reasoning from LLM").
    """

    outcome: MatchOutcome
    target_entity_id: str | None = None
    verdict: JudgeVerdict


class JudgeError(RuntimeError):
    """Raised when no valid verdict could be produced (bad language or bad output)."""


# The output schema is constant for the class — build it once, not per judged candidate.
_SCHEMA = JudgeVerdict.model_json_schema()


def classify_verdict(verdict: JudgeVerdict, *, confidence_merge: float) -> MatchOutcome:
    """Map a judge verdict to a §3.3 lifecycle state.

    Merge only on a confident YES: `match` true AND `confidence` strictly above the
    threshold (spec §3.3: confidence > 0.8). Everything else — a NO at any confidence, or
    an uncertain YES at/below the threshold — is `new-proposed` ("new or uncertain"), the
    fail-closed branch toward the human. The strict `>` edge mirrors Stage 1/2.

    This is *stricter* than the spec's literal "confidence > 0.8 → merge": a self-declared
    non-match (`match=false`) never merges however confident, because high confidence there
    means "confidently NOT the same entity" — merging it would be the exact duplicate-
    smuggling the cascade exists to prevent.
    """
    if verdict.match and verdict.confidence > confidence_merge:
        return "auto-merge-proposed"
    return "new-proposed"


class JudgeAgent:
    """Stage-3 LLM judge: verdict on whether a candidate is an existing entity, via the router."""

    def __init__(
        self, router: Router, *, confidence_merge: float | None = None, max_retries: int = 2
    ) -> None:
        self._router = router
        # The §3.3 threshold defaults from the one config home (DM1); the constructor
        # override keeps the agent unit-testable without touching global settings.
        self._confidence_merge = (
            settings.match_stage3_confidence if confidence_merge is None else confidence_merge
        )
        self._max_retries = max_retries

    async def judge(
        self,
        *,
        candidate_name: str,
        candidate_context: str,
        candidate_type: str,
        candidate_properties: dict[str, object] | None = None,
        existing: ExistingEntityContext,
        language: str,
    ) -> Stage3Result:
        """Judge whether `candidate` is `existing`, retrying on malformed/invalid output.

        Renders the injection-safe prompt (the full spec Appendix C.3 field set — both the
        candidate's name/context/type/properties and the existing entity's
        id/canonical_name/aliases/type/properties/recent-mentions — as untrusted text in the
        trusted template body), routes the call at `medium` weight → cloud_free (§6.5),
        validates the strict verdict schema with retry, and maps the verdict to a §3.3
        routing outcome. A merge proposal carries the judged entity as its target.
        """
        try:
            messages = render_messages(
                "judge",
                language,
                candidate_name=candidate_name,
                candidate_context=candidate_context,
                candidate_type=candidate_type,
                candidate_properties_json=json.dumps(
                    candidate_properties or {}, ensure_ascii=False
                ),
                existing_id=existing.id,
                existing_canonical_name=existing.canonical_name,
                existing_aliases=", ".join(existing.aliases),
                existing_type=existing.type,
                existing_properties_json=json.dumps(existing.properties, ensure_ascii=False),
                existing_recent_mentions="\n".join(existing.recent_mentions),
            )
        except PromptNotFound as exc:
            raise JudgeError(f"no judge prompt for language {language!r}") from exc

        # The router owns transport/envelope failover and the budget cap, so its
        # `BudgetExceededError` / `QuotaExhaustedError` fall straight through to the
        # caller (the cascade pauses on them); the shared loop retries only schema failures.
        # A terminal transport/envelope failure (provider unreachable, or an unusable
        # envelope after failover) is *not* a prompt problem and not a pause signal — it
        # means no verdict can be produced, so convert it to `JudgeError` (this agent's
        # "couldn't judge" contract). The cascade fail-closes JudgeError toward the human,
        # so a judge outage routes the candidate to review rather than aborting the batch.
        try:
            verdict = await validate_with_retry(
                JudgeVerdict,
                lambda: self._router.complete(
                    messages, weight="medium", task_type="judge", json_schema=_SCHEMA
                ),
                max_retries=self._max_retries,
                error=JudgeError,
                label="judge",
            )
        except (ProviderResponseError, httpx.HTTPError) as exc:
            raise JudgeError(
                "judge unavailable — provider unreachable or unusable response"
            ) from exc
        outcome = classify_verdict(verdict, confidence_merge=self._confidence_merge)
        # A NEW/uncertain proposal has no merge target; only a merge carries the entity.
        target = existing.id if outcome == "auto-merge-proposed" else None
        return Stage3Result(outcome=outcome, target_entity_id=target, verdict=verdict)
