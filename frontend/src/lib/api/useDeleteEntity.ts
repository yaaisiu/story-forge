// Entity-delete mutation hook (Session 43 — M4.S3b-fe, spec §3.4 delete in the detail panel).
//
// Deletes an accepted entity via
//   DELETE /stories/{id}/entities/{eid}   → 204 No Content
// A human-reached graph write (INV-9 as reworded — ADR 0006/0007): the backend `DETACH DELETE`s
// the Neo4j node (and its edges) and records a full before-image snapshot so undo can restore the
// whole entity — node, edges, and mentions (INV-3 executed, DM-S3b-1). Destructive but reversible.
// A stale double-delete (already gone, or not in this project) 404s; a store outage 503s — both a
// typed `ApiError`.
//
// On success it invalidates the reader (the deleted entity's highlights vanish for free), the
// story graph, and every entity-detail bundle for the story (a neighbour's panel loses the edge —
// prefix `["entity-detail", storyId]`).
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useMutation` only.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, del } from "./client";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

export { ApiError } from "./client";

export function useDeleteEntity(storyId: string): UseMutationResult<void, ApiError, string> {
  const queryClient = useQueryClient();
  return useMutation<void, ApiError, string>({
    mutationFn: (entityId) => del(`/stories/${storyId}/entities/${entityId}`),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: entityDetailStoryKey(storyId) });
    },
  });
}
