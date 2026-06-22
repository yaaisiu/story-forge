import { describe, expect, it } from "vitest";

import { selectionToSpan } from "./selectionOffsets";

// `selectionToSpan` is the *inverse* of the reader's render-time `codepointToUtf16`
// (decorations.ts): a text selection arrives as paragraph-relative **UTF-16** offsets (what
// ProseMirror / the DOM count in), and the backend's tag/suppress/boundary routes take
// **codepoint** offsets (Python `str` slicing). This module owns that one conversion + the
// client-side rejection of a degenerate selection, so the runtime selection adapter
// (ReaderEditor, the untestable Tiptap surface) stays free of offset math.

describe("selectionToSpan", () => {
  it("returns codepoint offsets unchanged for ASCII / BMP-only text", () => {
    expect(selectionToSpan("Janek walked to the mill.", 0, 5)).toEqual({
      span_start: 0,
      span_end: 5,
    });
    expect(selectionToSpan("Janek walked to the mill.", 6, 12)).toEqual({
      span_start: 6,
      span_end: 12,
    });
  });

  it("returns codepoint offsets unchanged across Polish diacritics (all BMP)", () => {
    // "Łódź nad rzeką" — every character is one UTF-16 unit and one codepoint.
    expect(selectionToSpan("Łódź nad rzeką", 0, 4)).toEqual({ span_start: 0, span_end: 4 });
  });

  it("contracts the UTF-16 offsets to codepoints past an astral character", () => {
    // "😀 Janek" — emoji is 2 UTF-16 units but 1 codepoint. Selecting "Janek" is UTF-16 [3, 8),
    // which is codepoints [2, 7).
    expect(selectionToSpan("😀 Janek", 3, 8)).toEqual({ span_start: 2, span_end: 7 });
  });

  it("rejects a zero-length (collapsed) selection", () => {
    // The backend 400s on an empty span — reject client-side so we never POST a guaranteed-400.
    expect(selectionToSpan("Janek walked", 5, 5)).toBeNull();
  });

  it("rejects a reversed selection", () => {
    expect(selectionToSpan("Janek walked", 9, 4)).toBeNull();
  });

  it("rejects a selection that collapses to zero length after codepoint conversion", () => {
    // A pathological UTF-16 range inside a single surrogate pair would map start==end.
    expect(selectionToSpan("😀", 0, 0)).toBeNull();
  });
});
