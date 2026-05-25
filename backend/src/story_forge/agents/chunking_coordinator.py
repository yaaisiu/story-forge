"""Chunking coordinator — dispatch the three §3.1 modes into an `Outline`.

Step 2 of the ingest pipeline (spec §7) has three modes; this composes them:

- **manual** — pure `domain.chunking.parse_manual_outline`, no LLM at all.
- **hybrid** — parse the author's anchors, then ask the `ChunkingAgent` to
  sub-divide only the *untitled* spans the author left unmarked, splicing the
  proposal back in. Every explicit `##` / `###` is preserved verbatim.
- **auto** — run the agent over the whole text (the fallback for unmarked input).

This module is the agent-layer seam wired in `main.py`: it composes the pure
domain parser with the `LLMProvider`-backed `ChunkingAgent`. The agent's
`paragraph_range` indexes into the blank-line paragraph blocks of the text it was
given (spec prompt: "paragraphs numbered from 0"), so `proposal_to_outline` slices
that same list — and enforces the end-index-vs-count upper bound the schema can't
(carry-forward from Session 3).

Long input is guarded, not windowed: above `max_input_words` the LLM paths raise
`ChunkingTooLongError`. Manual mode (and hybrid with enough anchors) handles any
size; full window-and-stitch for auto is a tracked follow-up.
"""

from __future__ import annotations

from story_forge.agents.chunking_agent import ChunkingAgent, ChunkingError, ChunkingProposal
from story_forge.domain.chunking import (
    Outline,
    OutlineChapter,
    OutlineScene,
    parse_manual_outline,
)
from story_forge.domain.parsing import split_paragraphs

# Conservative default ceiling for a single LLM chunking call. Below the smallest
# tier's practical context budget; a constructor knob, not an .env setting yet.
DEFAULT_MAX_INPUT_WORDS = 8000

_MODES = ("auto", "manual", "hybrid")


class OutlineRangeError(ChunkingError):
    """A proposal's `paragraph_range` end index exceeds the paragraph count."""


class ChunkingTooLongError(ChunkingError):
    """Input exceeds the per-call word budget for the LLM chunking paths."""


def proposal_to_outline(proposal: ChunkingProposal, paragraphs: list[str]) -> Outline:
    """Slice `paragraphs` into an `Outline` per the proposal's ranges.

    Enforces the upper bound the schema validator deferred: an `end` index at or
    beyond the paragraph count is unpersistable, so it raises here rather than
    silently dropping or duplicating text.
    """
    count = len(paragraphs)
    chapters: list[OutlineChapter] = []
    for chapter in proposal.chapters:
        scenes: list[OutlineScene] = []
        for scene in chapter.scenes:
            start, end = scene.paragraph_range
            if end >= count:
                raise OutlineRangeError(
                    f"paragraph_range {scene.paragraph_range} exceeds paragraph count {count}"
                )
            scenes.append(
                OutlineScene(
                    title=scene.title,
                    paragraphs=list(paragraphs[start : end + 1]),
                    summary=scene.summary,
                )
            )
        chapters.append(OutlineChapter(title=chapter.title, scenes=scenes, summary=chapter.summary))
    return Outline(chapters=chapters)


class ChunkingCoordinator:
    """Build an `Outline` for a story in any of the three §3.1 modes."""

    def __init__(
        self,
        agent: ChunkingAgent,
        *,
        max_input_words: int = DEFAULT_MAX_INPUT_WORDS,
    ) -> None:
        self._agent = agent
        self._max_input_words = max_input_words

    async def build_outline(self, *, raw_text: str, language: str, mode: str) -> Outline:
        """Dispatch on `mode` ("auto" | "manual" | "hybrid")."""
        if mode == "manual":
            return parse_manual_outline(raw_text)
        if mode == "auto":
            return await self._propose(raw_text, language)
        if mode == "hybrid":
            return await self._fill_untitled(parse_manual_outline(raw_text), language)
        raise ValueError(f"unknown chunking mode {mode!r}; expected one of {_MODES}")

    async def _propose(self, text: str, language: str) -> Outline:
        """Guard length, run the agent, convert the proposal over `text`'s blocks."""
        word_count = len(text.split())
        if word_count > self._max_input_words:
            raise ChunkingTooLongError(
                f"{word_count} words exceeds the {self._max_input_words}-word chunking "
                "budget; use manual/hybrid mode or add anchors"
            )
        proposal = await self._agent.propose_outline(
            raw_text=text, language=language, word_count=word_count
        )
        return proposal_to_outline(proposal, split_paragraphs(text))

    async def _fill_untitled(self, outline: Outline, language: str) -> Outline:
        """Sub-divide only untitled nodes; preserve every explicit anchor."""
        chapters: list[OutlineChapter] = []
        for chapter in outline.chapters:
            if chapter.title is None:
                # The author did not mark this span at all — propose its full
                # chapter/scene structure and splice the chapters in.
                text = "\n\n".join(p for scene in chapter.scenes for p in scene.paragraphs)
                if not text:
                    continue
                chapters.extend((await self._propose(text, language)).chapters)
                continue
            # Titled chapter: keep it, but fill any untitled scenes within it.
            scenes: list[OutlineScene] = []
            for scene in chapter.scenes:
                if scene.title is None and scene.paragraphs:
                    text = "\n\n".join(scene.paragraphs)
                    proposed = await self._propose(text, language)
                    for proposed_chapter in proposed.chapters:
                        scenes.extend(proposed_chapter.scenes)
                else:
                    scenes.append(scene)
            chapters.append(OutlineChapter(title=chapter.title, scenes=scenes))
        return Outline(chapters=chapters)
