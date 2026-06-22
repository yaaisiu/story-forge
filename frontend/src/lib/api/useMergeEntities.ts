// Entity-merge mutation hook (Session 43 — M4.S3b-fe, spec §3.4 merge in the detail panel).
//
// Folds entity B (absorbed) into survivor A via
//   POST /stories/{id}/entities/{absorbedId}/merge   body {target_entity_id, resolved_properties}
// A human-reached graph write (INV-9 as reworded — ADR 0006/0007): the backend re-points every
// edge and mention incident to B onto A, unions aliases/properties (the author's by-hand
// `resolved_properties` win the conflicts — DM-S3b-2), deletes B last (crash-retryable), and
// records a grouped before-image so undo can reverse the whole compound op (INV-3, DM-S3b-1).
//
// The open panel entity is the survivor (kept); the picked entity is the absorbed one — so the
// POST targets the *absorbed* entity's URL with `target_entity_id` = the survivor. An unresolved
// property conflict 400s (EntityMergeInvalid); a missing entity 404s; a self-merge 409s; a store
// outage 503s — each a typed `ApiError`.
//
// On success it invalidates the reader (the absorbed entity's highlights re-point / vanish for
// free), the story graph, and every entity-detail bundle for the story (both panels — prefix
// `["entity-detail", storyId]`).
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useMutation` only, schema types from `schema.d.ts`.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postJsonBody } from "./client";
import type { components } from "./schema";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

export { ApiError } from "./client";

export type MergeSummaryResponse = components["schemas"]["MergeSummaryResponse"];

export interface MergeEntitiesVars {
  /** Entity B — the one absorbed and deleted (the merge route's path id). */
  absorbedId: string;
  /** Entity A — the survivor kept (the request body's `target_entity_id`). */
  targetEntityId: string;
  /** The author's chosen value for each conflicting property key (DM-S3b-2). */
  resolvedProperties: Record<string, unknown>;
}

export function useMergeEntities(
  storyId: string,
): UseMutationResult<MergeSummaryResponse, ApiError, MergeEntitiesVars> {
  const queryClient = useQueryClient();
  return useMutation<MergeSummaryResponse, ApiError, MergeEntitiesVars>({
    mutationFn: ({ absorbedId, targetEntityId, resolvedProperties }) =>
      postJsonBody<MergeSummaryResponse>(`/stories/${storyId}/entities/${absorbedId}/merge`, {
        target_entity_id: targetEntityId,
        resolved_properties: resolvedProperties,
      }),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: entityDetailStoryKey(storyId) });
    },
  });
}
