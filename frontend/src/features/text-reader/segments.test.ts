import { describe, expect, it } from "vitest";

import { type ReaderHighlight, splitParagraph } from "./segments";

// A ReaderHighlight covers `[start, end)` of the paragraph text and names the
// entity + type to colour it by. The backend (`domain/highlights.py`) guarantees
// the highlights it returns are non-overlapping and sorted by `start`, so the
// splitter is a single linear walk — these tests encode that contract.
function hl(start: number, end: number, entity_id = "e1", type = "character"): ReaderHighlight {
  return { start, end, entity_id, type };
}

describe("splitParagraph", () => {
  it("returns a single plain segment when there are no highlights", () => {
    expect(splitParagraph("Janek walked home.", [])).toEqual([
      { kind: "plain", text: "Janek walked home." },
    ]);
  });

  it("returns nothing for empty text", () => {
    expect(splitParagraph("", [])).toEqual([]);
  });

  it("emits a single mark when one highlight covers the whole paragraph", () => {
    expect(splitParagraph("Janek", [hl(0, 5, "e7", "character")])).toEqual([
      { kind: "mark", text: "Janek", entityId: "e7", type: "character" },
    ]);
  });

  it("emits mark then plain when a highlight starts the paragraph", () => {
    expect(splitParagraph("Janek ran", [hl(0, 5)])).toEqual([
      { kind: "mark", text: "Janek", entityId: "e1", type: "character" },
      { kind: "plain", text: " ran" },
    ]);
  });

  it("emits plain then mark when a highlight ends the paragraph", () => {
    expect(splitParagraph("ran to Janek", [hl(7, 12)])).toEqual([
      { kind: "plain", text: "ran to " },
      { kind: "mark", text: "Janek", entityId: "e1", type: "character" },
    ]);
  });

  it("emits plain, mark, plain for a highlight in the middle", () => {
    expect(splitParagraph("see Janek now", [hl(4, 9, "e2", "place")])).toEqual([
      { kind: "plain", text: "see " },
      { kind: "mark", text: "Janek", entityId: "e2", type: "place" },
      { kind: "plain", text: " now" },
    ]);
  });

  it("emits no empty plain segment between adjacent highlights", () => {
    // "JanekZosia" — two highlights touching at index 5, no gap.
    expect(
      splitParagraph("JanekZosia", [hl(0, 5, "e1", "character"), hl(5, 10, "e2", "character")]),
    ).toEqual([
      { kind: "mark", text: "Janek", entityId: "e1", type: "character" },
      { kind: "mark", text: "Zosia", entityId: "e2", type: "character" },
    ]);
  });

  it("keeps the gap between two separated highlights as a plain segment", () => {
    expect(
      splitParagraph("Janek met Zosia.", [
        hl(0, 5, "e1", "character"),
        hl(10, 15, "e2", "character"),
      ]),
    ).toEqual([
      { kind: "mark", text: "Janek", entityId: "e1", type: "character" },
      { kind: "plain", text: " met " },
      { kind: "mark", text: "Zosia", entityId: "e2", type: "character" },
      { kind: "plain", text: "." },
    ]);
  });
});
