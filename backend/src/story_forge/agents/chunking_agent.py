"""ChunkingAgent — raw story text → proposed chapter/scene/paragraph outline.

Step 2 of the ingest pipeline (spec §7), the auto/fallback path of §3.1. The
everyday primary path is deterministic manual/hybrid chunking (later session);
this agent handles *unmarked* text and doubles as the canonical example of the
agent pattern: load prompt → call provider → parse + validate → retry.

Tier routing (spec §6.5): on a GPU-less host the local small model is
impractical, so chunking defaults to `cloud_free`. `select_chunking_tier` only
picks `local_small` when a local tier is configured *and* the text is short
enough — the `local_max_words` knob. The output is a *proposal*: it carries no
database identities (those are assigned when the outline is persisted).
"""

from __future__ import annotations

from pydantic import BaseModel, field_validator

from story_forge.adapters.llm.base import (
    CompletionResult,
    LLMProvider,
    ModelTier,
    ProviderResponseError,
)
from story_forge.agents.validation import validate_with_retry
from story_forge.domain.chunking import paragraph_range_problem
from story_forge.domain.parsing import split_paragraphs
from story_forge.prompts import PromptNotFound, render_messages

DEFAULT_LOCAL_MAX_WORDS = 4000


class SceneProposal(BaseModel):
    """A proposed scene: a paragraph range plus optional title and a summary."""

    title: str | None = None
    summary: str
    paragraph_range: tuple[int, int]  # [start_index, end_index], paragraphs 0-based

    @field_validator("paragraph_range")
    @classmethod
    def _ordered_and_non_negative(cls, value: tuple[int, int]) -> tuple[int, int]:
        # Reject malformed ranges so they trigger a retry rather than passing as a
        # successful outline. The upper bound (end < paragraph count) needs the
        # document's paragraph count and is enforced at persistence (Session 4).
        start, end = value
        if start < 0 or end < start:
            raise ValueError(f"paragraph_range must be ordered and non-negative, got {value}")
        return value


class ChapterProposal(BaseModel):
    """A proposed chapter holding one or more scenes."""

    title: str | None = None
    summary: str
    scenes: list[SceneProposal]


class ChunkingProposal(BaseModel):
    """The agent's output: a hierarchy the user reviews before it is persisted."""

    chapters: list[ChapterProposal]


class ChunkingError(RuntimeError):
    """Raised when no usable outline could be produced (bad language or bad output)."""


# The output schema is constant for the class — build it once, not per call.
_SCHEMA = ChunkingProposal.model_json_schema()


def select_chunking_tier(
    word_count: int, *, local_available: bool, local_max_words: int
) -> ModelTier:
    """Pick the model tier for a chunking call.

    `local_small` only when a local tier is configured and the text fits under
    the threshold; otherwise `cloud_free` (the default on a GPU-less host).
    """
    if local_available and word_count <= local_max_words:
        return "local_small"
    return "cloud_free"


class ChunkingAgent:
    """Turns raw text into a proposed outline via an `LLMProvider`."""

    def __init__(
        self,
        provider: LLMProvider,
        *,
        local_available: bool = False,
        local_max_words: int = DEFAULT_LOCAL_MAX_WORDS,
        max_retries: int = 2,
    ) -> None:
        self._provider = provider
        self._local_available = local_available
        self._local_max_words = local_max_words
        self._max_retries = max_retries

    async def propose_outline(
        self, *, raw_text: str, language: str, word_count: int | None = None
    ) -> ChunkingProposal:
        """Propose an outline for `raw_text`, retrying on malformed/invalid output."""
        if word_count is None:
            word_count = len(raw_text.split())
        try:
            messages = render_messages("chunking", language, raw_text=raw_text)
        except PromptNotFound as exc:
            raise ChunkingError(f"no chunking prompt for language {language!r}") from exc

        tier = select_chunking_tier(
            word_count,
            local_available=self._local_available,
            local_max_words=self._local_max_words,
        )

        # The schema validator (`_ordered_and_non_negative`) can't see the document, so
        # the range invariant — every paragraph in `[0, count)` covered, nothing past the
        # end — is checked here against the real paragraph count and folded into the
        # retried validation: a one-off LLM slip (an off-by-one overshoot, or a dropped
        # trailing paragraph) re-prompts rather than failing the request (spec
        # graph-quality §3 S1). The rule lives once in `paragraph_range_problem`; the
        # coordinator re-asserts it as a terminal backstop. The count matches the
        # coordinator's, since both split the same `raw_text` with `split_paragraphs`.
        count = len(split_paragraphs(raw_text))

        def check_ranges(proposal: ChunkingProposal) -> None:
            ranges = [
                scene.paragraph_range for chapter in proposal.chapters for scene in chapter.scenes
            ]
            problem = paragraph_range_problem(ranges, count)
            if problem is not None:
                raise ValueError(problem)

        async def call() -> CompletionResult:
            try:
                return await self._provider.complete(messages, tier, _SCHEMA)
            except ProviderResponseError as exc:
                # A malformed-200 envelope (missing fields / null content). Unlike a
                # schema violation, retrying the same raw provider won't help (no router
                # failover here — chunking holds a raw provider), so surface it as a
                # ChunkingError → the route maps that to 502, not an unhandled 500. Raised
                # from inside the thunk, it propagates past the shared loop (which retries
                # only a failed parse/schema/check), so it is not retried.
                raise ChunkingError(
                    f"chunking provider returned an unusable response: {exc}"
                ) from exc

        # The shared loop retries parse/schema failures and the `check_ranges` bound
        # check — a sampling model can return valid JSON (or fix an off-by-one) on a
        # second pass. Network errors and rate limits are not retried here; cross-provider
        # failover is the router's job (spec §6.5), so a provider HTTP error propagates.
        return await validate_with_retry(
            ChunkingProposal,
            call,
            max_retries=self._max_retries,
            error=ChunkingError,
            label="chunking",
            check=check_ranges,
        )
