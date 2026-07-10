// Retarget-relation mutation hook (Graph-quality S5b-fe — spec §3.4/§4, drives S5b-be).
//
// Edits an accepted relation edge — its predicate word and/or either endpoint — via the
// atomic re-key
//   PATCH /stories/{id}/relations/{edgeId}   body {predicate?, subject_id?, object_id?}
// at least one field required (an empty body 422s). A human-reached edge write (INV-9 as
// reworded — ADR 0006). Because the edge id is content-addressed, the re-key mints a *new*
// edge id (returned as `edge_id`) while preserving the §4 `edge_uid` surrogate handle server-
// side (INV-10, ADR 0011). A re-key that collides with an existing edge between the new pair
// folds: the response carries `merged_into_existing: true` so the UI can warn (not an error).
// A stale/gone edge or an unknown new endpoint 404s; a store outage 503s — both typed `ApiError`.
//
// On success it invalidates every entity-detail bundle for the story (a re-target moves an
// endpoint, touching up to four entities' panels — prefix `["entity-detail", storyId]`), the
// story graph (the edge re-ids/moves), and the reader (catalog consistency).
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useMutation` only, schema types from `schema.d.ts`.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, patchJsonBody } from "./client";
import type { components } from "./schema";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

export { ApiError } from "./client";

export type RetargetRelationRequest = components["schemas"]["RetargetRelationRequest"];
export type RelationEditResponse = components["schemas"]["RelationEditResponse"];

export function useRetargetRelation(
  storyId: string,
  edgeId: string,
): UseMutationResult<RelationEditResponse, ApiError, RetargetRelationRequest> {
  const queryClient = useQueryClient();
  return useMutation<RelationEditResponse, ApiError, RetargetRelationRequest>({
    mutationFn: (body) =>
      patchJsonBody<RelationEditResponse>(`/stories/${storyId}/relations/${edgeId}`, body),
    onSuccess: () => {
      // Prefix key — a re-target can move an endpoint, dirtying both old and new endpoints' panels.
      void queryClient.invalidateQueries({ queryKey: entityDetailStoryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
    },
  });
}
