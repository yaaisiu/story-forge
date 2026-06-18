// Pure paragraph-splitter for the text reader (M4.S1, spec §3.5, DM-IH-3).
//
// The backend resolves *where* each accepted entity sits in a paragraph
// (`domain/highlights.py`) and returns per-paragraph highlight ranges that are
// already **non-overlapping and sorted by `start`**. This module's only job is to
// turn (text + those ranges) into an ordered list of render segments — plain runs
// and `<mark>` runs — so the component stays render-and-dispatch (no logic in JSX).
//
// Kept pure (no React, no API runtime) so it unit-tests without a DOM, exactly the
// altitude the project tests hardest. Overlap arbitration (DM-IH-4 longest-match)
// already happened server-side; relying on the sorted/non-overlapping contract keeps
// this a single linear walk rather than re-implementing the resolver in TypeScript.

import type { components } from "../../lib/api/schema";

export type ReaderHighlight = components["schemas"]["ReaderHighlight"];

/** One render run of a paragraph: either unhighlighted text or a highlighted entity span. */
export type Segment =
  | { kind: "plain"; text: string }
  | { kind: "mark"; text: string; entityId: string; type: string };

/**
 * Split a paragraph's text into ordered plain/mark segments at the highlight
 * boundaries. Expects `highlights` non-overlapping and sorted by `start` (the
 * backend contract); empty plain runs (a highlight at index 0, or two adjacent
 * highlights) are never emitted.
 */
export function splitParagraph(text: string, highlights: readonly ReaderHighlight[]): Segment[] {
  const segments: Segment[] = [];
  let cursor = 0;

  for (const h of highlights) {
    if (h.start > cursor) {
      segments.push({ kind: "plain", text: text.slice(cursor, h.start) });
    }
    segments.push({
      kind: "mark",
      text: text.slice(h.start, h.end),
      entityId: h.entity_id,
      type: h.type,
    });
    cursor = h.end;
  }

  if (cursor < text.length) {
    segments.push({ kind: "plain", text: text.slice(cursor) });
  }

  return segments;
}
