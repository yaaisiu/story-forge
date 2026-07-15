// Label-rename mutation hook (Session 96 — Graph-quality S6b, S6a-2 apply, DM-NN-4/5).
//
// Renames one label graph-wide on its surface: a predicate rename re-keys every bearing edge in one
// grouped reversible op (folding identical triples, reported via `folded_count`); a type rename bulk-
// relabels every node of that type (never merges nodes, `folded_count` always 0). Human-gated
// (INV-1/INV-9), reversible via the graph-edit undo log (INV-3). `from_label` is sent VERBATIM — the
// backend matches the stored label exactly (S95 strip-bug fix), so callers must not trim it. Returns
// the summary so the card can report how many edges/nodes were renamed and folded. Invalidates the
// vocabulary list so the resolved pair drops.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation, `useMutation` only,
// and a mutation invalidates every cache its write dirties.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postJsonBody } from "./client";
import { labelVocabularyQueryKey } from "./useLabelVocabulary";
import type { components } from "./schema";

export { ApiError } from "./client";

export type RenameSummaryResponse = components["schemas"]["RenameSummaryResponse"];

/** A graph-wide rename of one label on a surface: `fromLabel` → `toLabel`. `fromLabel` must be the
 * stored label verbatim (the backend matches it exactly). */
export interface RenameLabelVars {
  surface: components["schemas"]["RenameLabelRequest"]["surface"];
  fromLabel: string;
  toLabel: string;
}

const RENAME_PATH = (storyId: string) => `/stories/${storyId}/label-vocabulary/rename`;

/** Rename a label graph-wide on its surface, returning the renamed/folded counts. */
export function useRenameLabel(
  storyId: string,
): UseMutationResult<RenameSummaryResponse, ApiError, RenameLabelVars> {
  const queryClient = useQueryClient();
  return useMutation<RenameSummaryResponse, ApiError, RenameLabelVars>({
    mutationFn: ({ surface, fromLabel, toLabel }) =>
      postJsonBody<RenameSummaryResponse>(RENAME_PATH(storyId), {
        surface,
        from_label: fromLabel,
        to_label: toLabel,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: labelVocabularyQueryKey(storyId) });
    },
  });
}
