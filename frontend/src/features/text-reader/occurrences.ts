// Pure occurrence-deriver for the reader side panel (M4.S2b, spec §3.4, DM-SP-3).
//
// "Occurrences" = where the entity appears in *this story's* prose, shown as a timeline
// in the panel. By DM-SP-3 they are derived from the reader's already-rendered highlights
// (not raw mentions), so the timeline can never claim an appearance the prose doesn't
// visibly highlight — the panel and the text always agree, and we reuse the backend's
// span resolution instead of re-deriving it. One entry per paragraph that highlights the
// entity, in document (array) order; each carries a context snippet so the author can
// preview the source text before drilling in.
//
// Kept pure (no React, no API runtime) so it unit-tests without a DOM — the altitude the
// project tests hardest. The panel calls it; the click-to-scroll wiring lives in the
// reader container.

import type { ReaderParagraph } from "../../lib/api/useReader";

/** One place the entity is highlighted: a paragraph, a preview snippet, the match count. */
export interface Occurrence {
  paragraphId: string;
  snippet: string;
  count: number;
}

// Characters of context shown on each side of the first match in the timeline snippet.
// Wide enough to read the occurrence in situ (the panel clamps to a few lines); finer
// "expand to full paragraph" is a post-PoC refinement (docs/BACKLOG.md).
const SNIPPET_PAD = 60;

/** A short excerpt of `text` centred on `[start, end)`, with `…` where it was clipped. */
function snippetAround(text: string, start: number, end: number): string {
  const from = Math.max(0, start - SNIPPET_PAD);
  const to = Math.min(text.length, end + SNIPPET_PAD);
  const prefix = from > 0 ? "…" : "";
  const suffix = to < text.length ? "…" : "";
  return `${prefix}${text.slice(from, to)}${suffix}`;
}

/**
 * Occurrences of `entityId` across the reader's paragraphs, one per highlighting
 * paragraph, in document order. A paragraph the entity never highlights is skipped.
 */
export function entityOccurrences(
  paragraphs: readonly ReaderParagraph[],
  entityId: string,
): Occurrence[] {
  const occurrences: Occurrence[] = [];

  for (const paragraph of paragraphs) {
    const matches = paragraph.highlights.filter((h) => h.entity_id === entityId);
    if (matches.length === 0) continue;

    const first = matches[0]!;
    occurrences.push({
      paragraphId: paragraph.id,
      snippet: snippetAround(paragraph.text, first.start, first.end),
      count: matches.length,
    });
  }

  return occurrences;
}
