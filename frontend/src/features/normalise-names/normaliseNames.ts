// Name-normalisation pure logic (Session 96 — Graph-quality S6b, spec/graph-quality §3 S6).
//
// Keeps the NormaliseNamesQueue/LabelPairCard components render-and-dispatch (frontend/src/CLAUDE.md):
// the flat cursor list over both vocabularies, the stable per-surface pair key, the honest score
// labels (DM-EE-4 — a score is never an identity verdict), the armed-rename direction mapping (which
// sends the stored label VERBATIM — S95 strip-bug guard), and the keyboard scheme (nav + dismiss) all
// live here as pure, unit-tested functions. The rename itself calls the existing endpoint graph-wide
// (INV-1/INV-9 — suggests only, the human commits).

import type { LabelSynonymView, LabelVocabularyResponse } from "../../lib/api/useLabelVocabulary";
import type { RenameSummaryResponse } from "../../lib/api/useRenameLabel";

/** The two vocabularies a label can belong to. A predicate is never a synonym of a type. */
export type Surface = "predicate" | "type";

/** One synonym pair tagged with its vocabulary surface, for the shared flat cursor. */
export interface LabelPairItem {
  surface: Surface;
  pair: LabelSynonymView;
}

/** Navigation state of the list — just the cursor (a pair has no target to cycle by keyboard;
 * the rename direction is picked per card). */
export interface NavState {
  selectedIndex: number;
}

/** What a committing keypress tells the queue to do. Rename needs a direction pick, so it is
 * mouse-driven; the only keyboard decision is dismiss. */
export type NormaliseIntent = "dismiss";

export interface KeyResult {
  state: NavState;
  intent?: NormaliseIntent;
}

/**
 * Flatten both vocabularies into one cursor-indexable list — predicates first, then types (each
 * already ranked strongest-first by the backend). The screen renders this grouped by surface, but
 * the shared `useReviewQueue` cursor walks the flat array so J/K moves continuously across both.
 */
export function flattenVocabulary(response: LabelVocabularyResponse): LabelPairItem[] {
  return [
    ...response.predicate_suggestions.map((pair) => ({ surface: "predicate" as const, pair })),
    ...response.type_suggestions.map((pair) => ({ surface: "type" as const, pair })),
  ];
}

/** A stable, order-independent key for a pair within a surface (React keys + local dismiss/undo
 * tracking): the surface plus the two labels sorted and joined, so `(a,b)` and `(b,a)` collapse to
 * one key and a predicate pair never collides with an identically-named type pair. */
export function pairKey(surface: Surface, labelA: string, labelB: string): string {
  return [surface, ...[labelA, labelB].sort()].join("::");
}

/** Honest, human-readable score labels for a suggested pair. The RapidFuzz name score is an integer
 * 0–100; the cosine score is a 0–1 float, or `null` when neither label carried a usable embedding
 * (a name-only suggestion). Never phrased as "identical" — the human judges (DM-EE-4). */
export function scoreLabels(pair: LabelSynonymView): {
  nameLabel: string;
  similarityLabel: string;
} {
  const nameLabel = `name match ${Math.round(pair.name_score)}`;
  const similarityLabel =
    pair.cosine_score === null ? "name-only" : `embedding ${pair.cosine_score.toFixed(2)}`;
  return { nameLabel, similarityLabel };
}

/** An armed rename direction: the author keeps `toLabel`, and the pair's OTHER label is renamed into
 * it graph-wide. `fromCount` is that other label's edge/node count (what folds into the kept form). */
export interface ArmedRename {
  surface: Surface;
  fromLabel: string;
  toLabel: string;
  fromCount: number;
}

/**
 * Map an armed direction (the label the author chose to keep) to the rename it commits. The kept
 * form is `toLabel`; the pair's OTHER label becomes `fromLabel` and its count `fromCount`. `fromLabel`
 * is one of the two stored labels passed through **verbatim** — the backend matches the stored label
 * exactly (S95 fixed a strip-bug), so this never trims or normalises it.
 */
export function armRename(item: LabelPairItem, toLabel: string): ArmedRename {
  const { label_lo, label_hi, count_lo, count_hi } = item.pair;
  const keepLo = toLabel === label_lo;
  return {
    surface: item.surface,
    fromLabel: keepLo ? label_hi : label_lo,
    toLabel,
    fromCount: keepLo ? count_hi : count_lo,
  };
}

/** The graph object a surface's rename touches, pluralised: predicate renames re-key edges, type
 * renames relabel entities. */
function surfaceNoun(surface: Surface, count: number): string {
  const singular = surface === "predicate" ? "edge" : "entity";
  const plural = surface === "predicate" ? "edges" : "entities";
  return count === 1 ? singular : plural;
}

/** The confirm-step hint shown once a direction is armed: what the rename will do, and that nothing
 * commits until the author presses Rename. */
export function armedRenameHint(armed: ArmedRename): string {
  return `Rename ${armed.fromCount} ${surfaceNoun(armed.surface, armed.fromCount)} from “${armed.fromLabel}” to “${armed.toLabel}”. Nothing happens until you press Rename.`;
}

/** The post-rename summary line: how many edges/nodes were renamed, and (predicates only) how many
 * identical triples folded onto a pre-existing target — the reported side-effect, never the goal. */
export function renameSummaryMessage(
  summary: RenameSummaryResponse,
  fromLabel: string,
  toLabel: string,
): string {
  const base = `Renamed ${summary.renamed_count} ${surfaceNoun(summary.surface, summary.renamed_count)} from “${fromLabel}” to “${toLabel}”`;
  const folded =
    summary.folded_count > 0
      ? `, folding ${summary.folded_count} duplicate ${summary.folded_count === 1 ? "edge" : "edges"}`
      : "";
  return `${base}${folded}.`;
}

function clamp(index: number, length: number): number {
  if (length === 0) return 0;
  return Math.min(Math.max(index, 0), length - 1);
}

/**
 * Map a keypress to the next list state (+ an optional dismiss intent). J/K (or ↓/↑) navigate; D
 * dismisses the selected pair. Rename is mouse-driven (it needs a direction pick), so no key commits
 * a rename. Pure — the component owns the mutation and refetch.
 */
export function reduceNormaliseKey(
  key: string,
  state: NavState,
  items: LabelPairItem[],
): KeyResult | null {
  switch (key) {
    case "j":
    case "J":
    case "ArrowDown":
      return { state: { selectedIndex: clamp(state.selectedIndex + 1, items.length) } };
    case "k":
    case "K":
    case "ArrowUp":
      return { state: { selectedIndex: clamp(state.selectedIndex - 1, items.length) } };
    case "d":
    case "D":
      return { state, intent: "dismiss" };
    default:
      return null;
  }
}
