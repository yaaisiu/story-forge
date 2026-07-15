// Label-vocabulary query hook (Session 96 — Graph-quality S6b, spec/graph-quality §3 S6).
//
// Reads a story's ranked synonym suggestions over both vocabularies from
// `GET /stories/{id}/label-vocabulary` (S6a-1): `predicate_suggestions` (edge predicate names) and
// `type_suggestions` (entity-type names), each a `LabelSynonymView` carrying the pair, their counts,
// and the name/cosine/combined scores that surfaced it. A predicate is never a synonym of a type, so
// the two surfaces are returned — and renamed — separately (DM-NN-1). Dismissed pairs are already
// suppressed server-side. Suggests only; the human renames graph-wide (S6a-2) or dismisses
// (INV-1/INV-4).
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation, `useQuery` only,
// schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type LabelVocabularyResponse = components["schemas"]["LabelVocabularyResponse"];
export type LabelSynonymView = components["schemas"]["LabelSynonymView"];

/** TanStack Query key for a story's label-vocabulary list — shared with the rename/dismiss
 * invalidations so a committed decision refetches the list. */
export function labelVocabularyQueryKey(storyId: string | undefined): [string, string | undefined] {
  return ["label-vocabulary", storyId];
}

/**
 * Fetch a story's ranked label-synonym suggestions. Disabled until a `storyId` is known (so it
 * never fires with `undefined` in the path during a deep-link race).
 */
export function useLabelVocabulary(
  storyId: string | undefined,
): UseQueryResult<LabelVocabularyResponse, ApiError> {
  return useQuery<LabelVocabularyResponse, ApiError>({
    queryKey: labelVocabularyQueryKey(storyId),
    queryFn: () => getJson<LabelVocabularyResponse>(`/stories/${storyId}/label-vocabulary`),
    enabled: Boolean(storyId),
  });
}
