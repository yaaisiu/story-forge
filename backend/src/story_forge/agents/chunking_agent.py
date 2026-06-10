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

from pydantic import BaseModel, ValidationError, field_validator

from story_forge.adapters.llm.base import LLMProvider, ModelTier, ProviderResponseError
from story_forge.agents.json_output import extract_json
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

        # Retry covers parse/schema failures only — a sampling model can return
        # valid JSON on a second pass. Network errors and rate limits are not
        # retried here; cross-provider failover is the router's job (spec §6.5,
        # later milestone), so a provider HTTP error propagates to the caller.
        last_error: ValidationError | None = None
        for _ in range(self._max_retries + 1):
            try:
                result = await self._provider.complete(messages, tier, _SCHEMA)
            except ProviderResponseError as exc:
                # A malformed-200 envelope (missing fields / null content). Unlike a
                # schema violation, retrying the same raw provider won't help (no
                # router failover here), so surface it as a ChunkingError → the route
                # maps that to 502 rather than letting it escape as an unhandled 500.
                raise ChunkingError(
                    f"chunking provider returned an unusable response: {exc}"
                ) from exc
            try:
                return ChunkingProposal.model_validate_json(extract_json(result.content))
            except ValidationError as exc:  # covers malformed JSON and schema violations
                last_error = exc
        raise ChunkingError(
            f"chunking output failed validation after {self._max_retries + 1} attempts"
        ) from last_error
