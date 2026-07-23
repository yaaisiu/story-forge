// Optimistic edits to the cached label-vocabulary list (Session 100).
//
// The normalise-names queue reloads the whole vocabulary after every decision, and the suggest
// pass is a whole-vocabulary recompute — a two-rung self-join over every label pair. Even with
// the backend's embedding cache that is ~1.7 s on the real Oakhaven vocabulary, so waiting for
// the refetch before repainting means a visible stall after each of 300 decisions.
//
// These pure helpers let the rename/dismiss hooks drop the decided rows from the cache
// immediately; the invalidation still fires, so the refetch remains authoritative and corrects
// anything these got wrong. They only decide what the author sees in between — which is why the
// rules below mirror what the server will actually return rather than guessing.
//
// Pure and total: no store, no query client, `undefined` in → `undefined` out (nothing cached
// yet is not an error).

import type { LabelSynonymView, LabelVocabularyResponse } from "./useLabelVocabulary";

/** Which vocabulary a decision applies to — a predicate is never a synonym of a type (DM-NN-1). */
export type LabelSurface = "predicate" | "type";

function edit(
  data: LabelVocabularyResponse | undefined,
  surface: LabelSurface,
  keep: (suggestion: LabelSynonymView) => boolean,
): LabelVocabularyResponse | undefined {
  if (!data) return undefined;
  return surface === "predicate"
    ? { ...data, predicate_suggestions: data.predicate_suggestions.filter(keep) }
    : { ...data, type_suggestions: data.type_suggestions.filter(keep) };
}

/**
 * Drop every pair naming `label` on `surface` — the shape a **rename** leaves behind.
 *
 * A rename folds `label` into another form, so the label ceases to exist and every suggestion
 * mentioning it goes with it. Removing a label cannot *create* a pair (pairs are scored per label
 * pair, and merging the counts doesn't change which labels exist), so this is exactly the server's
 * next answer minus the surviving labels' unchanged counts.
 */
export function dropPairsInvolving(
  data: LabelVocabularyResponse | undefined,
  surface: LabelSurface,
  label: string,
): LabelVocabularyResponse | undefined {
  return edit(data, surface, (s) => s.label_lo !== label && s.label_hi !== label);
}

/**
 * Drop the single pair `{a, b}` on `surface` — the shape a **dismissal** leaves behind.
 *
 * Unlike a rename, both labels survive: the author said "these two are not synonyms", which says
 * nothing about either label's other pairings, so only the one row goes. The pair is unordered,
 * so either argument order matches.
 */
export function dropPair(
  data: LabelVocabularyResponse | undefined,
  surface: LabelSurface,
  a: string,
  b: string,
): LabelVocabularyResponse | undefined {
  return edit(
    data,
    surface,
    (s) =>
      !(
        (s.label_lo === a && s.label_hi === b) || //
        (s.label_lo === b && s.label_hi === a)
      ),
  );
}
