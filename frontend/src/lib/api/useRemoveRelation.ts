// Remove-relation mutation hook (Session 38 — M4.S3a-fe, spec §3.4 "relations editable").
//
// Removes a relation edge via
//   DELETE /stories/{id}/relations/{edgeId}   → 204 No Content
// A human-reached edge delete (INV-9 as reworded — ADR 0006): the backend deletes the Neo4j
// edge and records a before-image `graph_edits` row (INV-3 undo). A stale double-remove (the
// edge already gone, or not in this project) 404s; a store outage 503s — both typed `ApiError`.
//
// On success it invalidates the same queries as an add (both endpoints' detail panels via the
// `["entity-detail", storyId]` prefix, the story graph, the reader). A client-side re-predicate
// is a remove (this hook) followed by an add (`useAddRelation`).
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useMutation` only, schema types from `schema.d.ts`.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, del } from "./client";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

export { ApiError } from "./client";

export function useRemoveRelation(storyId: string): UseMutationResult<void, ApiError, string> {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (edgeId) => del(`/stories/${storyId}/relations/${edgeId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: ["entity-detail", storyId] });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
    },
  });
}
