"""Deterministic manual/hybrid chunking (spec §3.1, modes 2 and 3).

Pure and I/O-free: a story's raw text in, an `Outline` tree (chapters → scenes →
paragraphs) out. This is the everyday primary path — manual mode when the author
has marked the whole text, hybrid mode when they marked only some of it and the
`ChunkingAgent` (an adapter-backed agent, wired in `main.py`) fills the gaps.

Markdown heading *levels* are the structural signal, not literal words:

- `##` opens a chapter; the trailing text is its title (`## The Crossing`).
- `###` opens a scene; the trailing text is its title.
- `#` is the story title — not a structural boundary; the line is dropped.

Prose between headings is split into paragraph blocks on blank lines, the same
rule `domain/parsing.py` uses. Prose that appears before the first `##` (or before
the first `###` inside a chapter) lands in an implicit untitled chapter/scene, so
no text is ever lost. Titles are assigned here; DB ids and `order_index` are not —
those belong to persistence, which walks this tree.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from uuid import UUID

from story_forge.domain.models import Chapter, Paragraph, Scene
from story_forge.domain.parsing import split_paragraphs

# A heading line: one-to-three leading hashes, at least one space, then the title.
# CommonMark requires the space, so "###Dawn" is body text, not a heading.
_HEADING = re.compile(r"^(#{1,3})[ \t]+(.*)$")


@dataclass(frozen=True)
class OutlineScene:
    """A scene: an optional title/summary and its ordered paragraph blocks."""

    title: str | None
    paragraphs: list[str] = field(default_factory=list)
    summary: str | None = None


@dataclass(frozen=True)
class OutlineChapter:
    """A chapter: an optional title/summary and its ordered scenes."""

    title: str | None
    scenes: list[OutlineScene] = field(default_factory=list)
    summary: str | None = None


@dataclass(frozen=True)
class Outline:
    """A parsed document tree: the ordered chapters of a story."""

    chapters: list[OutlineChapter] = field(default_factory=list)


def parse_manual_outline(raw_text: str) -> Outline:
    """Parse markdown-anchored `raw_text` into an `Outline` tree (modes 2 & 3)."""
    text = raw_text.replace("\r\n", "\n").replace("\r", "\n")
    outline = Outline()
    buffer: list[str] = []

    def current_chapter() -> OutlineChapter:
        if not outline.chapters:
            outline.chapters.append(OutlineChapter(title=None))
        return outline.chapters[-1]

    def current_scene() -> OutlineScene:
        chapter = current_chapter()
        if not chapter.scenes:
            chapter.scenes.append(OutlineScene(title=None))
        return chapter.scenes[-1]

    def flush() -> None:
        nonlocal buffer
        paragraphs = split_paragraphs("\n".join(buffer))
        buffer = []
        if paragraphs:
            current_scene().paragraphs.extend(paragraphs)

    for line in text.split("\n"):
        match = _HEADING.match(line)
        if match is None:
            buffer.append(line)
            continue
        hashes, title = match.group(1), match.group(2).strip()
        if hashes == "#":
            # Story title — not a chapter/scene boundary. Drop the marker line.
            continue
        flush()
        if hashes == "##":
            outline.chapters.append(OutlineChapter(title=title or None))
        else:  # "###"
            current_chapter().scenes.append(OutlineScene(title=title or None))
    flush()
    return outline


def outline_to_tree(
    outline: Outline, story_id: UUID
) -> tuple[list[Chapter], list[Scene], list[Paragraph]]:
    """Flatten an `Outline` into persistable rows under `story_id`.

    Pure: assigns `order_index` from sibling position and threads the generated
    parent ids down (chapter → scene → paragraph) so the caller can insert the
    three lists in order. No I/O — persistence is the adapter's job.
    """
    chapters: list[Chapter] = []
    scenes: list[Scene] = []
    paragraphs: list[Paragraph] = []
    for chapter_index, chapter_node in enumerate(outline.chapters):
        chapter = Chapter(
            story_id=story_id,
            order_index=chapter_index,
            title=chapter_node.title,
            summary=chapter_node.summary,
        )
        chapters.append(chapter)
        for scene_index, scene_node in enumerate(chapter_node.scenes):
            scene = Scene(
                chapter_id=chapter.id,
                order_index=scene_index,
                title=scene_node.title,
                summary=scene_node.summary,
            )
            scenes.append(scene)
            for paragraph_index, content in enumerate(scene_node.paragraphs):
                paragraphs.append(
                    Paragraph(scene_id=scene.id, order_index=paragraph_index, content=content)
                )
    return chapters, scenes, paragraphs
