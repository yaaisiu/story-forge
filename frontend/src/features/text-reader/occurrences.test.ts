import { describe, expect, it } from "vitest";

import { entityOccurrences } from "./occurrences";
import type { ReaderParagraph } from "../../lib/api/useReader";

// Occurrences (DM-SP-3) are derived from the reader's *rendered highlights*, not raw
// mentions — so the panel's timeline always agrees with what the prose actually shows.
// One occurrence per paragraph that highlights the entity, in document (array) order,
// each carrying a context snippet so the author can preview the source text without
// scrolling. These tests encode that contract.
function para(
  id: string,
  text: string,
  highlights: ReaderParagraph["highlights"],
): ReaderParagraph {
  return { id, text, highlights };
}

function hl(start: number, end: number, entity_id: string, type = "character") {
  return { start, end, entity_id, type };
}

describe("entityOccurrences", () => {
  it("returns nothing when the entity is never highlighted", () => {
    const paragraphs = [para("p1", "Janek walked home.", [hl(0, 5, "e1")])];
    expect(entityOccurrences(paragraphs, "e2")).toEqual([]);
  });

  it("returns one occurrence per paragraph that highlights the entity, in document order", () => {
    const paragraphs = [
      para("p1", "Janek walked to the mill.", [hl(0, 5, "e1")]),
      para("p2", "It was quiet.", []),
      para("p3", "Zosia met Janek there.", [hl(4, 9, "e2"), hl(10, 15, "e1")]),
    ];
    const occ = entityOccurrences(paragraphs, "e1");
    expect(occ.map((o) => o.paragraphId)).toEqual(["p1", "p3"]);
  });

  it("counts every highlight of the entity within a paragraph", () => {
    const paragraphs = [para("p1", "Janek saw Janek.", [hl(0, 5, "e1"), hl(10, 15, "e1")])];
    expect(entityOccurrences(paragraphs, "e1")[0]?.count).toBe(2);
  });

  it("builds a short snippet around the first match with no ellipses when it fits", () => {
    const paragraphs = [para("p1", "Janek ran.", [hl(0, 5, "e1")])];
    expect(entityOccurrences(paragraphs, "e1")[0]?.snippet).toBe("Janek ran.");
  });

  it("trims the snippet with leading/trailing ellipses when the paragraph is long", () => {
    // 80 chars of lead, "Janek", 80 chars of trail; pad is 60 so both sides clip.
    const lead = "x".repeat(80);
    const trail = "y".repeat(80);
    const text = `${lead}Janek${trail}`;
    const start = lead.length;
    const paragraphs = [para("p1", text, [hl(start, start + 5, "e1")])];
    const snippet = entityOccurrences(paragraphs, "e1")[0]?.snippet ?? "";
    expect(snippet.startsWith("…")).toBe(true);
    expect(snippet.endsWith("…")).toBe(true);
    expect(snippet).toContain("Janek");
    // 60 chars of lead + "Janek" + 60 chars of trail, wrapped in ellipses.
    expect(snippet).toBe(`…${"x".repeat(60)}Janek${"y".repeat(60)}…`);
  });
});
