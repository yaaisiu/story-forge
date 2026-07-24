// Single-story query hook (Grzymalin S3 — story hub).
//
// Reads one story's listing fields (title + ingested_at, no body) from
// `GET /stories/{id}` — what the story hub's header shows on a cold deep-link or
// reload. Disabled until a `storyId` is known so it never fires with `undefined`
// in the path. The route 404s an unknown story (fail-closed); that bubbles as a
// typed `ApiError` the hub can surface distinctly from a still-loading header.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type StorySummary = components["schemas"]["StorySummary"];

/** TanStack Query key for a single story's detail. */
export function storyQueryKey(storyId: string | undefined): [string, string | undefined] {
  return ["story", storyId];
}

/** Fetch a single story's detail. Disabled until a `storyId` is known. */
export function useStory(storyId: string | undefined): UseQueryResult<StorySummary, ApiError> {
  return useQuery<StorySummary, ApiError>({
    queryKey: storyQueryKey(storyId),
    queryFn: () => getJson<StorySummary>(`/stories/${storyId}`),
    enabled: Boolean(storyId),
    staleTime: 30_000,
  });
}
