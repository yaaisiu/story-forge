"""Unit tests for the chunking coordinator (`agents/chunking_coordinator.py`).

The coordinator dispatches the three §3.1 modes over a *mocked* agent: `manual`
is pure (no LLM), `hybrid` calls the agent only on untitled spans the author left
unmarked, and `auto` runs the agent over the whole text. No network — the stub
records its calls and returns canned `ChunkingProposal`s. Layering: the coordinator
composes the pure `domain` parser with an `LLMProvider`-backed agent; it never
touches a real provider here.
"""

from __future__ import annotations

import pytest

from story_forge.agents.chunking_agent import (
    ChapterProposal,
    ChunkingProposal,
    SceneProposal,
)
from story_forge.agents.chunking_coordinator import (
    ChunkingCoordinator,
    ChunkingTooLongError,
    OutlineRangeError,
    proposal_to_outline,
)


class _StubAgent:
    """Stands in for `ChunkingAgent`: returns queued proposals, records inputs."""

    def __init__(self, proposals: list[ChunkingProposal]) -> None:
        self._proposals = list(proposals)
        self.calls: list[str] = []

    async def propose_outline(
        self, *, raw_text: str, language: str, word_count: int | None = None
    ) -> ChunkingProposal:
        self.calls.append(raw_text)
        return self._proposals.pop(0)


def _scene(start: int, end: int, title: str | None = None) -> SceneProposal:
    return SceneProposal(title=title, summary="s", paragraph_range=(start, end))


async def test_manual_mode_does_not_call_the_agent() -> None:
    agent = _StubAgent([])
    coord = ChunkingCoordinator(agent)
    outline = await coord.build_outline(
        raw_text="## One\n### A\nBody.\n", language="en", mode="manual"
    )
    assert agent.calls == []
    assert [c.title for c in outline.chapters] == ["One"]
    assert outline.chapters[0].scenes[0].paragraphs == ["Body."]


async def test_hybrid_fills_an_untitled_scene_in_a_titled_chapter() -> None:
    # Author marked the chapter but no scenes → one implicit untitled scene the
    # agent should sub-divide; the titled chapter is preserved verbatim.
    raw = "## The Crossing\nFirst.\n\nSecond.\n\nThird.\n"
    proposal = ChunkingProposal(
        chapters=[
            ChapterProposal(
                title="ignored-collapsed",
                summary="c",
                scenes=[_scene(0, 0, "Arrival"), _scene(1, 2, "After")],
            )
        ]
    )
    agent = _StubAgent([proposal])
    coord = ChunkingCoordinator(agent)
    outline = await coord.build_outline(raw_text=raw, language="en", mode="hybrid")

    assert len(agent.calls) == 1
    assert [c.title for c in outline.chapters] == ["The Crossing"]
    scenes = outline.chapters[0].scenes
    assert [s.title for s in scenes] == ["Arrival", "After"]
    assert scenes[0].paragraphs == ["First."]
    assert scenes[1].paragraphs == ["Second.", "Third."]


async def test_hybrid_preserves_a_scene_anchor_before_the_first_chapter() -> None:
    # `### Cold Open` opens an implicit untitled chapter holding an *explicitly*
    # titled scene. Hybrid must preserve the scene anchor, not re-LLM the span.
    raw = "### Cold Open\nPrologue body.\n## One\n### A\nFirst.\n"
    agent = _StubAgent([])  # zero proposals queued — any LLM call is a regression
    coord = ChunkingCoordinator(agent)
    outline = await coord.build_outline(raw_text=raw, language="en", mode="hybrid")
    assert agent.calls == []
    assert [c.title for c in outline.chapters] == [None, "One"]
    assert [s.title for s in outline.chapters[0].scenes] == ["Cold Open"]
    assert outline.chapters[0].scenes[0].paragraphs == ["Prologue body."]
    assert [s.title for s in outline.chapters[1].scenes] == ["A"]


async def test_hybrid_with_everything_marked_makes_no_agent_call() -> None:
    raw = "## One\n### A\nBody one.\n## Two\n### B\nBody two.\n"
    agent = _StubAgent([])
    coord = ChunkingCoordinator(agent)
    outline = await coord.build_outline(raw_text=raw, language="en", mode="hybrid")
    assert agent.calls == []
    assert [c.title for c in outline.chapters] == ["One", "Two"]


async def test_auto_mode_converts_proposal_over_whole_text() -> None:
    raw = "Alpha.\n\nBeta.\n\nGamma.\n"
    proposal = ChunkingProposal(
        chapters=[ChapterProposal(title="Whole", summary="c", scenes=[_scene(0, 2, "All")])]
    )
    agent = _StubAgent([proposal])
    coord = ChunkingCoordinator(agent)
    outline = await coord.build_outline(raw_text=raw, language="en", mode="auto")
    assert len(agent.calls) == 1
    assert outline.chapters[0].title == "Whole"
    assert outline.chapters[0].scenes[0].paragraphs == ["Alpha.", "Beta.", "Gamma."]


def test_proposal_to_outline_enforces_paragraph_upper_bound() -> None:
    # Carry-forward from Session 3: the schema only checks ordered/non-negative;
    # the end-index-vs-count bound is enforced here, against the real paragraphs.
    paragraphs = ["only one paragraph"]
    proposal = ChunkingProposal(
        chapters=[ChapterProposal(title="X", summary="c", scenes=[_scene(0, 5)])]
    )
    with pytest.raises(OutlineRangeError):
        proposal_to_outline(proposal, paragraphs)


async def test_auto_mode_guards_text_over_the_word_budget() -> None:
    long_text = " ".join(["word"] * 50)
    agent = _StubAgent([])
    coord = ChunkingCoordinator(agent, max_input_words=10)
    with pytest.raises(ChunkingTooLongError):
        await coord.build_outline(raw_text=long_text, language="en", mode="auto")
    assert agent.calls == []  # guarded before any LLM call
