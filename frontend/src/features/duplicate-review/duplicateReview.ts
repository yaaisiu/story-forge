// Duplicate-review pure logic (Session 79 — Graph-quality S4b, spec/graph-quality §3 S4).
//
// Keeps the DuplicatesQueue/DuplicatePairCard components render-and-dispatch (frontend/src/CLAUDE.md):
// the stable pair key, the honest score labels (DM-EE-4 — a score is never an identity verdict), the
// survivor→merge-vars mapping, and the keyboard scheme (nav + dismiss) all live here as pure,
// unit-tested functions. The merge itself reuses the existing endpoint (INV-1/INV-9 — suggests only).

import type { DuplicateSuggestionView } from "../../lib/api/useDuplicateSuggestions";

/** Which side of an unordered pair the author kept as the survivor. */
export type SurvivorSide = "a" | "b";

/** Navigation state of the list — just the cursor (a pair has no merge target to cycle;
 * the survivor is picked per card, not by keyboard). */
export interface NavState {
  selectedIndex: number;
}

/** What a committing keypress tells the queue to do. Merge needs a survivor pick, so it is
 * mouse-driven; the only keyboard decision is dismiss. */
export type DuplicateIntent = "dismiss";

export interface KeyResult {
  state: NavState;
  intent?: DuplicateIntent;
}

/** A stable, order-independent key for a pair (React keys + local dismiss/undo tracking):
 * the two entity ids sorted and joined, so `(a,b)` and `(b,a)` collapse to one key. */
export function pairKey(entityIdA: string, entityIdB: string): string {
  return [entityIdA, entityIdB].sort().join("::");
}

/** Honest, human-readable score labels for a suggested pair. The RapidFuzz name score is an
 * integer 0–100; the cosine score is a 0–1 float, or `null` when neither side had a usable
 * mention vector (a name-only suggestion). Never phrased as "identical" — the human judges. */
export function scoreLabels(suggestion: DuplicateSuggestionView): {
  nameLabel: string;
  similarityLabel: string;
} {
  const nameLabel = `name match ${Math.round(suggestion.name_score)}`;
  const similarityLabel =
    suggestion.cosine_score === null
      ? "name-only"
      : `embedding ${suggestion.cosine_score.toFixed(2)}`;
  return { nameLabel, similarityLabel };
}

/** Map the chosen survivor side to the merge endpoint's vars: the survivor is kept
 * (`targetEntityId`, the request body's target), the other side is absorbed (`absorbedId`,
 * the merge route's path id). */
export function mergeVarsFor(
  survivor: SurvivorSide,
  suggestion: DuplicateSuggestionView,
): { targetEntityId: string; absorbedId: string } {
  const survivorEntity = survivor === "a" ? suggestion.entity_a : suggestion.entity_b;
  const absorbedEntity = survivor === "a" ? suggestion.entity_b : suggestion.entity_a;
  return { targetEntityId: survivorEntity.entity_id, absorbedId: absorbedEntity.entity_id };
}

/** One run of a context quote, flagged whether it is a mention of the entity being judged. */
export interface QuoteSegment {
  text: string;
  match: boolean;
}

function escapeRegExp(term: string): string {
  return term.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

/**
 * Split a context quote into runs, marking every occurrence of the entity's own names (its
 * canonical name + aliases) so the UI can highlight the mention the pair was surfaced on —
 * the author shouldn't have to hunt for it. Case-insensitive, longest-term-first so a
 * multi-word alias wins over a substring of it. Best-effort: an inflected mention that doesn't
 * match verbatim simply stays unmarked (the quote still renders), never throws.
 */
export function markMentions(quote: string, terms: string[]): QuoteSegment[] {
  const cleaned = [...new Set(terms.map((t) => t.trim()).filter(Boolean))].sort(
    (a, b) => b.length - a.length,
  );
  if (cleaned.length === 0) return quote ? [{ text: quote, match: false }] : [];

  const pattern = cleaned.map(escapeRegExp).join("|");
  // One capturing group → String.split interleaves the matched delimiters at odd indices.
  const parts = quote.split(new RegExp(`(${pattern})`, "gi"));
  const segments: QuoteSegment[] = [];
  for (let i = 0; i < parts.length; i++) {
    const part = parts[i];
    if (!part) continue; // skip the empty runs split yields at match boundaries
    segments.push({ text: part, match: i % 2 === 1 });
  }
  return segments;
}

function clamp(index: number, length: number): number {
  if (length === 0) return 0;
  return Math.min(Math.max(index, 0), length - 1);
}

/**
 * Map a keypress to the next list state (+ an optional dismiss intent). J/K (or ↓/↑) navigate;
 * D dismisses the selected pair. Merge is mouse-driven (it needs a survivor pick), so no key
 * commits a merge. Pure — the component owns the mutation and refetch.
 */
export function reduceDuplicateKey(
  key: string,
  state: NavState,
  suggestions: DuplicateSuggestionView[],
): KeyResult | null {
  switch (key) {
    case "j":
    case "J":
    case "ArrowDown":
      return { state: { selectedIndex: clamp(state.selectedIndex + 1, suggestions.length) } };
    case "k":
    case "K":
    case "ArrowUp":
      return { state: { selectedIndex: clamp(state.selectedIndex - 1, suggestions.length) } };
    case "d":
    case "D":
      return { state, intent: "dismiss" };
    default:
      return null;
  }
}
