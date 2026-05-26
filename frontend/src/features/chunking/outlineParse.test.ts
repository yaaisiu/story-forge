// Unit tests for `parseManualOutline` — the frontend live-preview parser.
//
// Mirrors `backend/src/story_forge/domain/chunking.parse_manual_outline`. The
// backend re-parses the same text on submit, so the two implementations must
// agree on what becomes a chapter / scene / paragraph. These tests pin the
// rules that matter to the manual-mode UX:
//
//   - `##` opens a chapter (title = trimmed remainder).
//   - `###` opens a scene inside the current chapter.
//   - `#` is the story title — dropped, not a structural marker.
//   - Prose before any `##` lives in an implicit untitled chapter.
//   - `###` before any `##` produces an implicit untitled chapter wrapping it.
//   - Paragraph blocks are separated by blank lines (one-or-more empty lines).

import { describe, expect, it } from "vitest";

import {
  countOutline,
  parseManualOutline,
  type Outline,
  type OutlineChapter,
} from "./outlineParse";

// Tiny accessors that throw a meaningful message instead of letting `undefined`
// propagate when the parser regresses — TS strict (noUncheckedIndexedAccess)
// would otherwise require optional-chaining on every assertion.
function chapter(outline: Outline, index: number): OutlineChapter {
  const c = outline.chapters[index];
  if (c === undefined) throw new Error(`no chapter at index ${index}`);
  return c;
}

describe("parseManualOutline", () => {
  it("returns an empty outline for empty input", () => {
    expect(parseManualOutline("")).toEqual({ chapters: [] });
    expect(countOutline(parseManualOutline(""))).toEqual({
      chapters: 0,
      scenes: 0,
      paragraphs: 0,
    });
  });

  it("parses a simple chapter / scene / paragraph", () => {
    const raw = "## The Crossing\n### Dawn\nThey reached the river.\n\nThe water was high.\n";
    const outline = parseManualOutline(raw);
    expect(outline.chapters).toHaveLength(1);
    const ch = chapter(outline, 0);
    expect(ch.title).toBe("The Crossing");
    expect(ch.scenes).toHaveLength(1);
    const scene = ch.scenes[0]!;
    expect(scene.title).toBe("Dawn");
    expect(scene.paragraphs).toEqual(["They reached the river.", "The water was high."]);
    expect(countOutline(outline)).toEqual({ chapters: 1, scenes: 1, paragraphs: 2 });
  });

  it("drops `#` as the story title — not a structural boundary", () => {
    const outline = parseManualOutline("# A Novel\n## One\n### A\nBody.\n");
    expect(outline.chapters).toHaveLength(1);
    expect(chapter(outline, 0).title).toBe("One");
  });

  it("wraps preamble before any `##` in an implicit untitled chapter", () => {
    const outline = parseManualOutline("Opening line.\n\nSecond.\n\n## One\n### A\nBody.\n");
    expect(outline.chapters).toHaveLength(2);
    expect(chapter(outline, 0).title).toBeNull();
    expect(chapter(outline, 0).scenes[0]!.paragraphs).toEqual(["Opening line.", "Second."]);
    expect(chapter(outline, 1).title).toBe("One");
  });

  it("wraps a `###` before any `##` in an implicit untitled chapter", () => {
    const outline = parseManualOutline("### Cold Open\nLine.\n## One\n### A\nBody.\n");
    expect(outline.chapters).toHaveLength(2);
    expect(chapter(outline, 0).title).toBeNull();
    expect(chapter(outline, 0).scenes[0]!.title).toBe("Cold Open");
    expect(chapter(outline, 1).title).toBe("One");
  });

  it("handles CRLF line endings", () => {
    const outline = parseManualOutline("## A\r\n### S\r\nLine.\r\n");
    expect(countOutline(outline)).toEqual({ chapters: 1, scenes: 1, paragraphs: 1 });
  });
});
