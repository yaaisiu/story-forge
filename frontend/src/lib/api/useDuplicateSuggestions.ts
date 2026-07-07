// Duplicate-suggestions query hook (Session 79 — Graph-quality S4b, spec/graph-quality §3 S4).
//
// Reads a story's ranked likely-duplicate pairs from `GET /stories/{id}/duplicate-suggestions`
// (S4a): each pair carries both entities enriched for verification (name/type/aliases/quote,
// DM-EE-3) plus the name/cosine/combined scores that surfaced it. The list is a computed-on-open
// derived view over the accepted graph — dismissed pairs are already suppressed server-side, and
// an accepted merge removes an entity so its pairs cannot recur (DM-CD-3). Suggests only; the
// human commits every merge (INV-1/INV-9).
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation, `useQuery` only,
// schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type DuplicateSuggestionsResponse = components["schemas"]["DuplicateSuggestionsResponse"];
export type DuplicateSuggestionView = components["schemas"]["DuplicateSuggestionView"];
export type DuplicateEntityView = components["schemas"]["DuplicateEntityView"];

/** TanStack Query key for a story's duplicate-suggestion list — shared with the dismiss/merge
 * invalidations so a committed decision drops (or restores) the affected row. */
export function duplicateSuggestionsQueryKey(
  storyId: string | undefined,
): [string, string | undefined] {
  return ["duplicate-suggestions", storyId];
}

/**
 * Fetch a story's ranked duplicate suggestions. Disabled until a `storyId` is known (so it
 * never fires with `undefined` in the path during a deep-link race).
 */
export function useDuplicateSuggestions(
  storyId: string | undefined,
): UseQueryResult<DuplicateSuggestionsResponse, ApiError> {
  return useQuery<DuplicateSuggestionsResponse, ApiError>({
    queryKey: duplicateSuggestionsQueryKey(storyId),
    queryFn: () =>
      getJson<DuplicateSuggestionsResponse>(`/stories/${storyId}/duplicate-suggestions`),
    enabled: Boolean(storyId),
  });
}
