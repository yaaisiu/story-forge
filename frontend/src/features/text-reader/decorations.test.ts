import { describe, expect, it } from "vitest";

import {
  codepointToUtf16,
  decorationAttrs,
  paragraphHighlightRanges,
  utf16ToCodepoint,
} from "./decorations";
import type { ReaderEntity, ReaderHighlight } from "../../lib/api/useReader";

// The backend emits highlight `start`/`end` as **codepoint** offsets (Python `re` match
// indices over the original paragraph text). ProseMirror measures document positions in
// **UTF-16 code units**. The two coincide for Basic-Multilingual-Plane text and diverge by
// one unit per preceding astral character (emoji, rare CJK extensions) — so a BMP-only
// assumption would silently mis-place a decoration after an emoji. These tests pin the
// conversion, with an explicit astral case so that bug can't pass green.

function hl(start: number, end: number, entity_id = "e1", type = "character"): ReaderHighlight {
  return { start, end, entity_id, type, source: "search" };
}

describe("codepointToUtf16", () => {
  it("is the identity for ASCII / BMP-only text", () => {
    expect(codepointToUtf16("Janek walked", 0)).toBe(0);
    expect(codepointToUtf16("Janek walked", 5)).toBe(5);
    expect(codepointToUtf16("Janek walked", 12)).toBe(12);
  });

  it("is the identity across Polish diacritics (all BMP, one code unit each)", () => {
    // "Łódź" — Ł U+0141, ó U+00F3, d, ź U+017A: four codepoints, four UTF-16 units.
    expect(codepointToUtf16("Łódź", 4)).toBe(4);
    expect(codepointToUtf16("Łódź nad rzeką", 5)).toBe(5);
  });

  it("expands by one unit per preceding astral character (surrogate pair)", () => {
    // "a😀b": a(cp0), 😀 U+1F600 = 2 UTF-16 units (cp1), b(cp2). Codepoint→UTF-16:
    const text = "a😀b";
    expect(codepointToUtf16(text, 0)).toBe(0); // before "a"
    expect(codepointToUtf16(text, 1)).toBe(1); // before the emoji
    expect(codepointToUtf16(text, 2)).toBe(3); // after the emoji (1 + 2 surrogate units)
    expect(codepointToUtf16(text, 3)).toBe(4); // after "b" (full UTF-16 length)
  });
});

describe("utf16ToCodepoint", () => {
  it("is the identity for ASCII / BMP-only text", () => {
    expect(utf16ToCodepoint("Janek walked", 0)).toBe(0);
    expect(utf16ToCodepoint("Janek walked", 5)).toBe(5);
    expect(utf16ToCodepoint("Janek walked", 12)).toBe(12);
  });

  it("is the identity across Polish diacritics (all BMP, one code unit each)", () => {
    expect(utf16ToCodepoint("Łódź", 4)).toBe(4);
    expect(utf16ToCodepoint("Łódź nad rzeką", 5)).toBe(5);
  });

  it("contracts by one codepoint per preceding astral character (surrogate pair)", () => {
    // "a😀b": a(u16 0), 😀 U+1F600 = 2 UTF-16 units, b. UTF-16→codepoint:
    const text = "a😀b";
    expect(utf16ToCodepoint(text, 0)).toBe(0); // before "a"
    expect(utf16ToCodepoint(text, 1)).toBe(1); // before the emoji
    expect(utf16ToCodepoint(text, 3)).toBe(2); // after the emoji (2 surrogate units → 1 codepoint)
    expect(utf16ToCodepoint(text, 4)).toBe(3); // after "b" (full codepoint length)
  });

  it("round-trips codepointToUtf16 for every codepoint boundary (incl. astral)", () => {
    for (const text of ["Janek walked", "Łódź nad rzeką", "a😀b", "😀😀"]) {
      const codepoints = Array.from(text).length;
      for (let n = 0; n <= codepoints; n += 1) {
        expect(utf16ToCodepoint(text, codepointToUtf16(text, n))).toBe(n);
      }
    }
  });
});

describe("paragraphHighlightRanges", () => {
  it("maps each highlight to UTF-16 offsets relative to the paragraph content start", () => {
    expect(paragraphHighlightRanges("see Janek now", [hl(4, 9, "e2", "place")])).toEqual([
      { from: 4, to: 9, highlight: hl(4, 9, "e2", "place") },
    ]);
  });

  it("shifts offsets past an astral character", () => {
    // "😀 Janek" — emoji(cp0, 2 UTF-16 units) + space(cp1) → "Janek" at codepoints [2, 7),
    // which is UTF-16 [3, 8) because the emoji counts as two units before the span.
    const ranges = paragraphHighlightRanges("😀 Janek", [hl(2, 7)]);
    expect(ranges).toEqual([{ from: 3, to: 8, highlight: hl(2, 7) }]);
  });

  it("preserves multiple highlights in order", () => {
    const ranges = paragraphHighlightRanges("Janek met Zosia.", [hl(0, 5, "e1"), hl(10, 15, "e2")]);
    expect(ranges.map((r) => [r.from, r.to])).toEqual([
      [0, 5],
      [10, 15],
    ]);
  });

  it("keeps adjacent (touching) highlights as separate ranges", () => {
    // "JanekZosia" — two highlights meeting at offset 5; each maps to its own range (no merge,
    // no gap — ProseMirror renders the two inline decorations side by side).
    const ranges = paragraphHighlightRanges("JanekZosia", [hl(0, 5, "e1"), hl(5, 10, "e2")]);
    expect(ranges.map((r) => [r.from, r.to])).toEqual([
      [0, 5],
      [5, 10],
    ]);
  });

  it("maps a whole-paragraph highlight to the full range", () => {
    expect(paragraphHighlightRanges("Janek", [hl(0, 5)])).toEqual([
      { from: 0, to: 5, highlight: hl(0, 5) },
    ]);
  });
});

describe("decorationAttrs", () => {
  const entity: ReaderEntity = {
    entity_id: "e1",
    canonical_name: "Janek",
    type: "character",
    aliases: ["Jan"],
  };

  it("carries the highlight identity, type colour, and a name+aliases tooltip", () => {
    const attrs = decorationAttrs(hl(0, 5, "e1", "character"), entity, false, "Janek");
    expect(attrs["data-testid"]).toBe("highlight");
    expect(attrs["data-entity-id"]).toBe("e1");
    expect(attrs["data-entity-type"]).toBe("character");
    // A search hit carries its source + codepoint span but no mention id (it has no stored row).
    expect(attrs["data-source"]).toBe("search");
    expect(attrs["data-start"]).toBe("0");
    expect(attrs["data-end"]).toBe("5");
    expect(attrs["data-mention-id"]).toBeUndefined();
    // Keyboard-activatable (parity with the prior <mark role=button tabIndex=0>).
    expect(attrs.role).toBe("button");
    expect(attrs.tabindex).toBe("0");
    expect(attrs.title).toBe("Janek — character\nAliases: Jan");
    expect(attrs.class).toContain("cursor-pointer");
    expect(attrs.style).toContain("background-color");
    expect(attrs["data-flash"]).toBeUndefined();
  });

  it("drops the aliases line when the entity has no aliases", () => {
    const attrs = decorationAttrs(hl(0, 5), { ...entity, aliases: [] }, false, "Janek");
    expect(attrs.title).toBe("Janek — character");
  });

  it("adds the flash marker and pulse class when flashing", () => {
    const attrs = decorationAttrs(hl(0, 5), entity, true, "Janek");
    expect(attrs["data-flash"]).toBe("true");
    expect(attrs.class).toContain("animate-pulse");
  });

  it("carries a manual highlight's source + mention id so a correction can address it", () => {
    const manual: ReaderHighlight = {
      start: 0,
      end: 5,
      entity_id: "e1",
      type: "character",
      source: "manual",
      mention_id: "m-123",
    };
    const attrs = decorationAttrs(manual, entity, false, "Janek");
    expect(attrs["data-source"]).toBe("manual");
    expect(attrs["data-mention-id"]).toBe("m-123");
  });

  it("falls back to the highlighted surface text when the entity is absent from the catalog", () => {
    // Parity with the prior <mark> renderer, which titled a catalog-missing highlight with its text.
    const attrs = decorationAttrs(hl(0, 5, "e9", "place"), undefined, false, "Janek");
    expect(attrs.title).toBe("Janek");
  });
});
