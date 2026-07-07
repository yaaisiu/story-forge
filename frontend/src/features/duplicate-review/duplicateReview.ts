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
