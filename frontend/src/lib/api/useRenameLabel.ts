// Label-rename mutation hook (Session 96 — Graph-quality S6b, S6a-2 apply, DM-NN-4/5).
//
// Renames one label graph-wide on its surface: a predicate rename re-keys every bearing edge in one
// grouped reversible op (folding identical triples, reported via `folded_count`); a type rename bulk-
// relabels every node of that type (never merges nodes, `folded_count` always 0). Human-gated
// (INV-1/INV-9), reversible via the graph-edit undo log (INV-3). `from_label` is sent VERBATIM — the
// backend matches the stored label exactly (S95 strip-bug fix), so callers must not trim it. Returns
// the summary so the card can report how many edges/nodes were renamed and folded.
//
// A rename is a graph write, so — like useMergeEntities — it dirties more than its own list: the
// story graph (edge predicates / node types), the reader (an entity's type), and every entity-detail
// bundle (the type shown in the panel). onSuccess invalidates all of those plus the vocabulary list.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation, `useMutation` only,
// and a mutation invalidates every cache its write dirties.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postJsonBody } from "./client";
import { dropPairsInvolving } from "./labelVocabularyCache";
import { entityDetailStoryKey } from "./useEntityDetail";
import { labelVocabularyQueryKey, type LabelVocabularyResponse } from "./useLabelVocabulary";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";
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
    onSuccess: (_data, { surface, fromLabel }) => {
      // Repaint the queue now: the refetch below is a whole-vocabulary recompute (~1.7 s), and
      // waiting for it stalls the list after every decision. `fromLabel` no longer exists after
      // the rename, so every pair naming it is gone; the refetch still reconciles the counts.
      queryClient.setQueryData<LabelVocabularyResponse>(
        labelVocabularyQueryKey(storyId),
        (current) => dropPairsInvolving(current, surface, fromLabel),
      );
      void queryClient.invalidateQueries({ queryKey: labelVocabularyQueryKey(storyId) });
      // The rename wrote the graph — refresh the views that render its edges/types, mirroring
      // useMergeEntities (the other graph-write hook).
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: entityDetailStoryKey(storyId) });
    },
  });
}
