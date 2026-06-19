// Entity-detail query hook (Session 35 — M4.S2b, spec §3.4/§3.5).
//
// Reads one accepted entity's detail bundle from `GET /stories/{id}/entities/{eid}`
// (DM-SP-1a, the BFF endpoint): the entity's free-form `properties` (surfaced by no
// other endpoint) and its 1-hop `ego_graph` (the "local graph around that entity",
// §3.5), plus name/type/aliases so the side panel is self-contained. Occurrences are
// *not* here — by DM-SP-3 they are derived frontend-side from the reader's already-
// rendered highlights (see features/text-reader/occurrences.ts).
//
// Fetched per click (not per page): most entities are never inspected, so the panel
// pays one small read when the author opens it rather than fattening the reader payload.
// Stale-while-revalidate (mirrors `useReader`/`useStoryGraph`): the bundle is a read-only
// projection of the accepted graph, so a 30 s `staleTime` paints instantly when the
// author re-opens the same entity. Failures bubble as a typed `ApiError`.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type EntityDetailResponse = components["schemas"]["EntityDetailResponse"];
export type EgoGraph = components["schemas"]["EgoGraph"];
export type EgoNeighbour = components["schemas"]["EgoNeighbour"];
export type EgoEdge = components["schemas"]["EgoEdge"];

/** TanStack Query key for one story-scoped entity's detail bundle. */
export function entityDetailQueryKey(
  storyId: string | undefined,
  entityId: string | undefined,
): [string, string | undefined, string | undefined] {
  return ["entity-detail", storyId, entityId];
}

/**
 * Prefix key matching *every* entity's detail bundle in a story — for a mutation that touches
 * more than one entity (a relation add/remove hits both endpoints' panels). `invalidateQueries`
 * fuzzy-matches by default, so this prefix invalidates all `entityDetailQueryKey(storyId, *)`.
 */
export function entityDetailStoryKey(storyId: string | undefined): [string, string | undefined] {
  return ["entity-detail", storyId];
}

/**
 * Fetch one entity's detail bundle for the reader side panel. Disabled until both a
 * `storyId` and an `entityId` are known (so it never fires with `undefined` in the path
 * before the author has clicked a highlight, or during a deep-link race).
 */
export function useEntityDetail(
  storyId: string | undefined,
  entityId: string | undefined,
): UseQueryResult<EntityDetailResponse, ApiError> {
  return useQuery<EntityDetailResponse, ApiError>({
    queryKey: entityDetailQueryKey(storyId, entityId),
    queryFn: () => getJson<EntityDetailResponse>(`/stories/${storyId}/entities/${entityId}`),
    enabled: Boolean(storyId) && Boolean(entityId),
    staleTime: 30_000,
  });
}
