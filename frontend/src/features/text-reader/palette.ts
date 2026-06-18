// Colour-by-type for the text reader (M4.S1, spec §3.5, DM-IH-5).
//
// Entity `type` is open-world (INV-4): a free string, not an enum, so a hand-built
// colour map can never be exhaustive and must never throw on a never-before-seen
// type. So: a small **fixed** palette for the common types the corpus is dominated by
// (readable, stable colours), and a deterministic **hash** fallback for the long tail.
//
// Reader-local by the owner's call (Session 33): the graph viewer keeps its own
// pure-hash `colorForType` (graph-viewer/graphElements.ts), so the same long-tail
// type may colour differently across the two views. Reconciling the two colour
// helpers into one shared module is a flagged follow-up, deferred to keep this slice
// surgical (it would change the shipped graph's colours).

/** Fixed, readable colours for the common entity types. Keyed by normalised type. */
const FIXED_TYPE_COLORS: Record<string, string> = {
  character: "#2563eb", // blue
  place: "#16a34a", // green
  object: "#d97706", // amber
  concept: "#7c3aed", // violet
};

// Hash-fallback palette for the open-world long tail. Distinct from the fixed hues
// above to reduce collision; capped + hand-picked for contrast on a light background.
const FALLBACK_PALETTE = [
  "#db2777", // pink
  "#0891b2", // cyan
  "#dc2626", // red
  "#4b5563", // gray
  "#ca8a04", // yellow-700
  "#0d9488", // teal
  "#9333ea", // purple
  "#e11d48", // rose
] as const;

function normalize(type: string): string {
  return type.trim().toLowerCase();
}

/**
 * Stable colour for an entity type: a fixed colour for the common types, else a
 * deterministic hash into the fallback palette. Case-insensitive; never throws.
 */
export function colorForType(type: string): string {
  const key = normalize(type);
  const fixed = FIXED_TYPE_COLORS[key];
  if (fixed) return fixed;

  let hash = 0;
  for (let i = 0; i < key.length; i++) {
    hash = (hash * 31 + key.charCodeAt(i)) | 0;
  }
  // `% length` is always in range; the `?? [0]` satisfies noUncheckedIndexedAccess.
  return FALLBACK_PALETTE[Math.abs(hash) % FALLBACK_PALETTE.length] ?? FALLBACK_PALETTE[0];
}

/** One legend row: a type label and the colour the reader paints it. */
export interface LegendEntry {
  type: string;
  color: string;
}

/**
 * Distinct (type, colour) pairs for the legend, deduped case-insensitively in
 * first-seen order, preserving the original label and skipping blank types.
 */
export function legendEntries(types: readonly string[]): LegendEntry[] {
  const seen = new Set<string>();
  const entries: LegendEntry[] = [];
  for (const type of types) {
    const key = normalize(type);
    if (key === "" || seen.has(key)) continue;
    seen.add(key);
    entries.push({ type, color: colorForType(type) });
  }
  return entries;
}
