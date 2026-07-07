// Duplicate dismiss / un-dismiss mutation hooks (Session 79 — Graph-quality S4b, DM-CD-3).
//
// The author's "these two are NOT a duplicate" decision, and its reversal. Dismiss POSTs the
// unordered pair to `/duplicate-suggestions/dismiss` (persisted staging-side so the pair stops
// being re-suggested — INV-9 holds, it writes Postgres, never the graph); un-dismiss DELETEs the
// same route with the pair in the body, so a mistaken "no" is not a one-way door. Both reply 204.
// Each invalidates the suggestions list so the row drops on dismiss and reappears on un-dismiss.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation, `useMutation`
// only, and a mutation invalidates every cache its write dirties.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, delJsonBody, postJsonBody } from "./client";
import { duplicateSuggestionsQueryKey } from "./useDuplicateSuggestions";

export { ApiError } from "./client";

/** The unordered pair the author is (un-)marking as not-a-duplicate. */
export interface DismissDuplicateVars {
  entityIdA: string;
  entityIdB: string;
}

const DISMISS_PATH = (storyId: string) => `/stories/${storyId}/duplicate-suggestions/dismiss`;

function requestBody({ entityIdA, entityIdB }: DismissDuplicateVars) {
  return { entity_id_a: entityIdA, entity_id_b: entityIdB };
}

/** Record a pair as "not a duplicate" (suppresses re-suggestion). */
export function useDismissDuplicate(
  storyId: string,
): UseMutationResult<null, ApiError, DismissDuplicateVars> {
  const queryClient = useQueryClient();
  return useMutation<null, ApiError, DismissDuplicateVars>({
    mutationFn: (vars) => postJsonBody<null>(DISMISS_PATH(storyId), requestBody(vars)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: duplicateSuggestionsQueryKey(storyId) });
    },
  });
}

/** Reverse a dismissal — the pair becomes eligible to be suggested again. */
export function useUndismissDuplicate(
  storyId: string,
): UseMutationResult<null, ApiError, DismissDuplicateVars> {
  const queryClient = useQueryClient();
  return useMutation<null, ApiError, DismissDuplicateVars>({
    mutationFn: (vars) => delJsonBody<null>(DISMISS_PATH(storyId), requestBody(vars)),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: duplicateSuggestionsQueryKey(storyId) });
    },
  });
}
