// Highlight → ProseMirror decoration mapping for the reader (M4.S3c-fe1, spec §3.5).
//
// The reader draws accepted-entity highlights as ProseMirror *inline decorations* over a
// read-only document, rather than baking <mark> elements into the markup. Decorations are
// a render-time overlay: they don't change the document, so the same paragraph text maps to
// stable positions whatever is highlighted. This module owns the two pure, fiddly halves of
// that mapping so the editor mount (`ReaderEditor`, an untestable surface like the graph's
// cytoscape canvas) stays thin:
//
//   1. Offset units. The backend emits highlight `start`/`end` as **codepoint** offsets
//      (Python `re` indices over the original paragraph text). ProseMirror counts document
//      positions in **UTF-16 code units**. They agree for BMP text and drift by one unit per
//      preceding astral character — so we convert against the original text (`codepointToUtf16`),
//      the same expanding-codepoint care `domain/highlights.py` takes server-side.
//   2. The decoration's DOM attributes — colour-by-type, the name+aliases tooltip, and the
//      `data-*` the editor's click handler and the occurrence-flash read.
//
// `ReaderEditor` supplies the per-paragraph document base position (it knows the live doc);
// everything here is pure and unit-tested, including the astral case.

import type { ReaderEntity, ReaderHighlight } from "../../lib/api/useReader";
import { colorForType } from "./palette";

/**
 * Convert a codepoint offset into the matching UTF-16 code-unit offset within `text`.
 * Identity for BMP-only text; grows by one per preceding astral character. `Array.from`
 * iterates by codepoint, so the first `codepointOffset` codepoints, re-joined, give the
 * UTF-16 length up to that point.
 */
export function codepointToUtf16(text: string, codepointOffset: number): number {
  return Array.from(text).slice(0, codepointOffset).join("").length;
}

/** A highlight's span as UTF-16 offsets relative to its paragraph's content start. */
export interface HighlightRange {
  from: number;
  to: number;
  highlight: ReaderHighlight;
}

/**
 * Map a paragraph's highlights to UTF-16 ranges relative to the paragraph's content start
 * (position 0 = just inside the paragraph node). `ReaderEditor` adds the live document base
 * position to turn these into absolute decoration positions.
 */
export function paragraphHighlightRanges(
  text: string,
  highlights: readonly ReaderHighlight[],
): HighlightRange[] {
  return highlights.map((highlight) => ({
    from: codepointToUtf16(text, highlight.start),
    to: codepointToUtf16(text, highlight.end),
    highlight,
  }));
}

const BASE_CLASS = "sf-highlight cursor-pointer rounded-sm px-0.5";
const FLASH_CLASS = "animate-pulse ring-2 ring-offset-1";

/** Tooltip text for a highlight: "Name — type", plus an aliases line if the entity has any. */
function tooltipText(entity: ReaderEntity): string {
  const head = `${entity.canonical_name} — ${entity.type}`;
  return entity.aliases.length > 0 ? `${head}\nAliases: ${entity.aliases.join(", ")}` : head;
}

/**
 * The DOM attributes for a highlight's inline decoration. `colorForType` is open-world-safe
 * (INV-4) and an inline `style` is required because the colour can't map to a Tailwind class.
 * `entity` comes from the reader's catalog (the entities that appear); it is only ever absent
 * defensively, in which case the tooltip falls back to the bare type.
 */
export function decorationAttrs(
  highlight: ReaderHighlight,
  entity: ReaderEntity | undefined,
  flashing: boolean,
): Record<string, string> {
  const color = colorForType(highlight.type);
  const attrs: Record<string, string> = {
    "data-testid": "highlight",
    "data-entity-id": highlight.entity_id,
    "data-entity-type": highlight.type,
    title: entity ? tooltipText(entity) : highlight.type,
    class: flashing ? `${BASE_CLASS} ${FLASH_CLASS}` : BASE_CLASS,
    style: `background-color: ${color}1a; border-bottom: 2px solid ${color}`,
  };
  if (flashing) attrs["data-flash"] = "true";
  return attrs;
}
