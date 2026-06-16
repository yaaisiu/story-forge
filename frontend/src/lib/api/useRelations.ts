// Relation-queue fetch hook (Session 30 — M3.S4f, spec §3.3's 5th human action).
//
// Reads a story's committable relations from `GET /stories/{id}/relations` — the
// staged relations whose subject and object both resolve to entities already accepted
// in that paragraph (the backend filters out held/self-loop endpoints). Each item
// carries the surface triple (subject/predicate/object), the cascade's confidence, and
// the resolved subject/object entity ids.
//
// No `staleTime`: like the candidate queue, the list mutates with every commit/reject
// the author makes, so `useDecideRelation` invalidates this key to refetch the shrinking
// list immediately. A 503 (relation store down) bubbles as a typed `ApiError`.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type RelationsResponse = components["schemas"]["RelationsResponse"];
export type RelationView = components["schemas"]["RelationView"];

/** TanStack Query key for a story's relation queue — shared with the invalidation in
 * `useDecideRelation`, so a commit/reject refetches the shrinking list. */
export function relationsQueryKey(storyId: string | undefined): [string, string | undefined] {
  return ["relations", storyId];
}

/**
 * Fetch a story's committable relations. Disabled until a `storyId` is known (so it
 * never fires with `undefined` in the path during an initial render or deep-link race).
 */
export function useRelations(
  storyId: string | undefined,
): UseQueryResult<RelationsResponse, ApiError> {
  return useQuery<RelationsResponse, ApiError>({
    queryKey: relationsQueryKey(storyId),
    queryFn: () => getJson<RelationsResponse>(`/stories/${storyId}/relations`),
    enabled: Boolean(storyId),
  });
}
