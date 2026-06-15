// Story-graph query hook (Session 17 — M2.S5 graph viewer).
//
// Reads a story's entity graph from `GET /stories/{id}/graph` — the thin
// GraphNode/GraphEdge projection the read-only viewer renders (spec §3.4). The
// graph is keyed by project on the backend; the route resolves the story to its
// project, so the frontend only ever passes the story id.
//
// Stale-while-revalidate: a `staleTime` lets the cached graph paint instantly on
// revisit while TanStack refetches in the background — the graph changes only when
// an extraction run writes to it, so a 30 s window is plenty and avoids a refetch
// storm while the user pans/clicks. Failures bubble as a typed `ApiError`.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type GraphResponse = components["schemas"]["GraphResponse"];
export type GraphNode = components["schemas"]["GraphNode"];
export type GraphEdge = components["schemas"]["GraphEdge"];

/** TanStack Query key for a story's graph — shared so `useReviewCandidate` can
 * invalidate the exact same key, making the graph refetch as the author commits. */
export function storyGraphQueryKey(storyId: string | undefined): [string, string | undefined] {
  return ["story-graph", storyId];
}

/**
 * Fetch a story's entity graph. Disabled until a `storyId` is known (so it never
 * fires with `undefined` in the path during an initial render or a deep-link race).
 */
export function useStoryGraph(
  storyId: string | undefined,
): UseQueryResult<GraphResponse, ApiError> {
  return useQuery<GraphResponse, ApiError>({
    queryKey: storyGraphQueryKey(storyId),
    queryFn: () => getJson<GraphResponse>(`/stories/${storyId}/graph`),
    enabled: Boolean(storyId),
    staleTime: 30_000,
  });
}
