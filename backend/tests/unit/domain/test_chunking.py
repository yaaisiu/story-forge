"""Unit tests for the deterministic manual/hybrid chunker (`domain/chunking.py`).

Pure functions: a story's raw text in, an `Outline` tree (chapters → scenes →
paragraphs) out. No filesystem, no network, no LLM. Markdown heading *levels* are
the structural signal — `##` opens a chapter, `###` opens a scene, the trailing
text is the title (`## The Crossing`, not the literal word "Chapter"). `#` is the
story title and is not a structural boundary. Prose between headings is split into
paragraph blocks on blank lines, exactly like `domain/parsing.py`.
"""

from __future__ import annotations

from story_forge.domain.chunking import Outline, parse_manual_outline


def test_two_chapters_two_scenes() -> None:
    raw = (
        "## The Crossing\n"
        "### Dawn\n"
        "They reached the river at first light.\n\n"
        "The water was higher than the maps promised.\n"
        "### Dusk\n"
        "By nightfall the far bank was a black line.\n"
        "## The Climb\n"
        "### Ascent\n"
        "The path narrowed to a ledge.\n"
    )
    outline = parse_manual_outline(raw)
    assert isinstance(outline, Outline)
    assert [c.title for c in outline.chapters] == ["The Crossing", "The Climb"]

    crossing = outline.chapters[0]
    assert [s.title for s in crossing.scenes] == ["Dawn", "Dusk"]
    assert crossing.scenes[0].paragraphs == [
        "They reached the river at first light.",
        "The water was higher than the maps promised.",
    ]
    assert crossing.scenes[1].paragraphs == ["By nightfall the far bank was a black line."]

    climb = outline.chapters[1]
    assert [s.title for s in climb.scenes] == ["Ascent"]
    assert climb.scenes[0].paragraphs == ["The path narrowed to a ledge."]


def test_story_title_h1_is_not_a_boundary() -> None:
    raw = "# The Long Road\n\n## One\nThe journey began.\n"
    outline = parse_manual_outline(raw)
    # `#` is the story title — it neither opens a chapter nor leaks into the body.
    assert [c.title for c in outline.chapters] == ["One"]
    assert outline.chapters[0].scenes[0].paragraphs == ["The journey began."]


def test_preamble_before_first_chapter_gets_implicit_chapter_and_scene() -> None:
    raw = "An epigraph, unmarked.\n\n## One\n### Scene\nMarked body.\n"
    outline = parse_manual_outline(raw)
    assert [c.title for c in outline.chapters] == [None, "One"]
    # The preamble lands in an implicit untitled chapter + scene, so nothing is lost.
    assert outline.chapters[0].scenes[0].title is None
    assert outline.chapters[0].scenes[0].paragraphs == ["An epigraph, unmarked."]
    assert outline.chapters[1].scenes[0].paragraphs == ["Marked body."]


def test_scene_before_any_chapter_gets_implicit_chapter() -> None:
    raw = "### Cold Open\nNo chapter heading precedes this scene.\n"
    outline = parse_manual_outline(raw)
    assert len(outline.chapters) == 1
    assert outline.chapters[0].title is None
    assert [s.title for s in outline.chapters[0].scenes] == ["Cold Open"]
    assert outline.chapters[0].scenes[0].paragraphs == [
        "No chapter heading precedes this scene.",
    ]


def test_unmarked_text_is_one_implicit_chapter_and_scene() -> None:
    raw = "First block.\n\nSecond block.\n"
    outline = parse_manual_outline(raw)
    assert len(outline.chapters) == 1
    assert outline.chapters[0].title is None
    assert len(outline.chapters[0].scenes) == 1
    assert outline.chapters[0].scenes[0].title is None
    assert outline.chapters[0].scenes[0].paragraphs == ["First block.", "Second block."]


def test_empty_text_yields_empty_outline() -> None:
    assert parse_manual_outline("   \n\n  ").chapters == []
