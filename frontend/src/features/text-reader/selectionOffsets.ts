// Text selection → manual-tag span offsets for the reader (M4.S3c-fe2, spec §3.5).
//
// A correction addresses a `[span_start, span_end)` range within one paragraph. The selection
// arrives as paragraph-relative **UTF-16** offsets (ProseMirror document positions / DOM
// `Range` offsets both count in UTF-16 code units); the backend's tag/suppress/boundary routes
// take **codepoint** offsets (Python `str` slicing, the same units the reader's highlights use).
// This pure module owns that conversion and the client-side rejection of a degenerate span, so
// the runtime selection adapter in `ReaderEditor` (the untestable Tiptap surface) stays free of
// offset math. It is the inverse of `decorations.codepointToUtf16` (via `utf16ToCodepoint`).

import { utf16ToCodepoint } from "./decorations";

/** A manual span as codepoint offsets into its paragraph's text. */
export interface SelectionSpan {
  span_start: number;
  span_end: number;
}

/**
 * Map a paragraph-relative UTF-16 selection to codepoint span offsets, or `null` if the
 * selection is empty/reversed (the backend 400s on those, so reject client-side rather than POST
 * a guaranteed failure). `utf16Start`/`utf16End` are offsets into `paragraphText` in UTF-16 code
 * units; the result is half-open `[span_start, span_end)` in codepoints.
 */
export function selectionToSpan(
  paragraphText: string,
  utf16Start: number,
  utf16End: number,
): SelectionSpan | null {
  const span_start = utf16ToCodepoint(paragraphText, utf16Start);
  const span_end = utf16ToCodepoint(paragraphText, utf16End);
  if (span_start >= span_end) return null;
  return { span_start, span_end };
}
