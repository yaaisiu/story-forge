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
(carry-forward from Session 3). After conversion `_assert_full_coverage` checks that
the proposal's ranges cover *every* paragraph: a gap or a dropped trailing paragraph
raises rather than silently shipping a truncated outline (graph-quality §3 S1).

Long input is guarded, not windowed: above `max_input_words` the LLM paths raise
`ChunkingTooLongError`. Manual mode (and hybrid with enough anchors) handles any
size; full window-and-stitch for auto is a tracked follow-up.
"""

from __future__ import annotations

from typing import Protocol

from story_forge.agents.chunking_agent import ChunkingError, ChunkingProposal
from story_forge.domain.chunking import (
    Outline,
    OutlineChapter,
    OutlineScene,
    paragraph_range_problem,
    parse_manual_outline,
)
from story_forge.domain.parsing import split_paragraphs

# Conservative default ceiling for a single LLM chunking call. Below the smallest
# tier's practical context budget; a constructor knob, not an .env setting yet.
DEFAULT_MAX_INPUT_WORDS = 8000

_MODES = ("auto", "manual", "hybrid")


class OutlineProposer(Protocol):
    """What the coordinator needs from an agent: outline-from-text, mockable.

    A structural type so the live `ChunkingAgent` satisfies it without inheritance
    and tests can pass a stub that records calls — no concrete-class coupling, no
    `type: ignore` on the test fakes.
    """

    async def propose_outline(
        self, *, raw_text: str, language: str, word_count: int | None = None
    ) -> ChunkingProposal: ...


class OutlineRangeError(ChunkingError):
    """A proposal's `paragraph_range` end index exceeds the paragraph count."""


class OutlineCoverageError(ChunkingError):
    """A proposal's scenes leave some paragraph in `[0, count)` unassigned."""


class ChunkingTooLongError(ChunkingError):
    """Input exceeds the per-call word budget for the LLM chunking paths."""


def _assert_full_coverage(proposal: ChunkingProposal, count: int) -> None:
    """Terminal backstop for the range invariant (spec graph-quality §3 S1).

    The agent's retried `check` (`paragraph_range_problem`) normally clears a gap or a
    dropped trailing paragraph by re-prompting before we reach here; this is the spec's
    "assert after `proposal_to_outline`" final guard, and the path the coordinator's own
    tests exercise (where the agent is a stub that bypasses the retry). Same rule, one
    home — overlaps are duplication, not loss, so they pass (see `paragraph_range_problem`).
    """
    ranges = [scene.paragraph_range for chapter in proposal.chapters for scene in chapter.scenes]
    problem = paragraph_range_problem(ranges, count)
    if problem is not None:
        raise OutlineCoverageError(problem)


def proposal_to_outline(proposal: ChunkingProposal, paragraphs: list[str]) -> Outline:
    """Slice `paragraphs` into an `Outline` per the proposal's ranges.

    Keeps a local slice-safety guard against an out-of-range `end` (a `paragraphs[start:
    end + 1]` over the end would silently truncate). The canonical range *validation* is
    `paragraph_range_problem`, run first by the agent's retry and again by the coordinator
    backstop, so in the live path this guard never fires — it protects a direct caller.
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
        agent: OutlineProposer,
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
        paragraphs = split_paragraphs(text)
        outline = proposal_to_outline(proposal, paragraphs)  # raises on an overshooting range
        _assert_full_coverage(proposal, len(paragraphs))  # raises on a gap / dropped tail
        return outline

    async def _fill_untitled(self, outline: Outline, language: str) -> Outline:
        """Sub-divide only untitled *scenes*; preserve every explicit anchor.

        The dispatch is per-scene, not per-chapter — an implicit (untitled) chapter
        can still hold an *explicitly* titled scene (e.g. `### Cold Open` before the
        first `##`), and that scene anchor must survive. So for every chapter (its
        title kept as-is, None or otherwise), we walk scenes and only LLM-fill the
        untitled ones; the proposed chapters from each fill are flattened back to
        their scenes under the host chapter. Chapters that end up empty (e.g. an
        implicit one whose only scene held no paragraphs) are dropped.
        """
        chapters: list[OutlineChapter] = []
        for chapter in outline.chapters:
            scenes: list[OutlineScene] = []
            for scene in chapter.scenes:
                if scene.title is None and scene.paragraphs:
                    text = "\n\n".join(scene.paragraphs)
                    proposed = await self._propose(text, language)
                    for proposed_chapter in proposed.chapters:
                        scenes.extend(proposed_chapter.scenes)
                else:
                    scenes.append(scene)
            if not scenes and chapter.title is None:
                continue
            chapters.append(
                OutlineChapter(title=chapter.title, scenes=scenes, summary=chapter.summary)
            )
        return Outline(chapters=chapters)
