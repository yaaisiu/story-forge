// Label dismiss / un-dismiss mutation hooks (Session 96 — Graph-quality S6b, DM-NN-3).
//
// The author's "these two labels are NOT synonyms" decision, and its reversal. Dismiss POSTs the
// unordered pair (on its surface) to /label-vocabulary/dismiss (persisted staging-side so the pair
// stops being re-suggested — INV-9 holds, it writes Postgres, never the graph); un-dismiss DELETEs
// the same route with the pair in the body, so a mistaken "no" is not a one-way door. Both reply 204.
// Each invalidates the vocabulary list so the row drops on dismiss and reappears on un-dismiss.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation, `useMutation` only,
// and a mutation invalidates every cache its write dirties.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, delJsonBody, postJsonBody } from "./client";
import { dropPair } from "./labelVocabularyCache";
import { labelVocabularyQueryKey, type LabelVocabularyResponse } from "./useLabelVocabulary";
import type { components } from "./schema";

export { ApiError } from "./client";

/** The unordered label pair the author is (un-)marking as not-synonyms, on its surface. */
export interface DismissLabelVars {
  surface: components["schemas"]["DismissLabelRequest"]["surface"];
  labelA: string;
  labelB: string;
}

const DISMISS_PATH = (storyId: string) => `/stories/${storyId}/label-vocabulary/dismiss`;

function requestBody({ surface, labelA, labelB }: DismissLabelVars) {
  return { surface, label_a: labelA, label_b: labelB };
}

/** Record a label pair as "not synonyms" (suppresses re-suggestion). */
export function useDismissLabel(
  storyId: string,
): UseMutationResult<null, ApiError, DismissLabelVars> {
  const queryClient = useQueryClient();
  return useMutation<null, ApiError, DismissLabelVars>({
    mutationFn: (vars) => postJsonBody<null>(DISMISS_PATH(storyId), requestBody(vars)),
    onSuccess: (_data, { surface, labelA, labelB }) => {
      // Drop the row now so the queue repaints immediately; the refetch below re-derives the
      // list (a ~1.7 s whole-vocabulary recompute) and remains authoritative. Only this pair
      // goes — both labels survive a dismissal, so their other pairings are untouched.
      queryClient.setQueryData<LabelVocabularyResponse>(
        labelVocabularyQueryKey(storyId),
        (current) => dropPair(current, surface, labelA, labelB),
      );
      void queryClient.invalidateQueries({ queryKey: labelVocabularyQueryKey(storyId) });
    },
  });
}

/** Reverse a dismissal — the label pair becomes eligible to be suggested again. */
export function useUndismissLabel(
  storyId: string,
): UseMutationResult<null, ApiError, DismissLabelVars> {
  const queryClient = useQueryClient();
  return useMutation<null, ApiError, DismissLabelVars>({
    mutationFn: (vars) => delJsonBody<null>(DISMISS_PATH(storyId), requestBody(vars)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: labelVocabularyQueryKey(storyId) });
    },
  });
}
