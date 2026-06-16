// Manual-handpick entity-search hook (M3.S4d — Stage 4 review UI).
//
// Reads the project's accepted entities matching a query from
// `GET /stories/{id}/entities?q=<query>` — the safety net the reviewer reaches for when a
// true duplicate slipped past the cascade's top-3 alternatives (spec §3.3 *Manual
// handpick*). The backend ranks by the same RapidFuzz signal the matcher uses, so a hit's
// `entity_id` feeds the existing merge-accept path (`useReviewCandidate`, action="merge").
//
// Disabled until BOTH a story id and a non-blank query exist: an empty box is not a search
// (the backend returns [] anyway, but skipping the request avoids a needless round-trip and
// keeps the picker quiet until the author types). The query is keyed into the cache so each
// distinct search is memoised; a 404 (unknown story) bubbles as a typed `ApiError`.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type EntitySearchResponse = components["schemas"]["EntitySearchResponse"];
export type EntitySearchResult = components["schemas"]["EntitySearchResult"];

/** TanStack Query key for one story's entity search — keyed on the query so distinct
 * searches are cached independently. */
export function entitySearchQueryKey(
  storyId: string | undefined,
  query: string,
): [string, string | undefined, string] {
  return ["entity-search", storyId, query];
}

/**
 * Search a project's accepted entities for the manual-handpick picker. Disabled until a
 * `storyId` is known and the trimmed query is non-empty, so it never fires with `undefined`
 * in the path nor searches an empty box.
 */
export function useEntitySearch(
  storyId: string | undefined,
  query: string,
): UseQueryResult<EntitySearchResponse, ApiError> {
  const trimmed = query.trim();
  return useQuery<EntitySearchResponse, ApiError>({
    queryKey: entitySearchQueryKey(storyId, trimmed),
    queryFn: () =>
      getJson<EntitySearchResponse>(
        `/stories/${storyId}/entities?q=${encodeURIComponent(trimmed)}`,
      ),
    enabled: Boolean(storyId) && trimmed.length > 0,
  });
}
