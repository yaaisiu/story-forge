// Suppress / re-assign mutation hook (Session 48 — M4.S3c-fe2, spec §3.5 manual correction).
//
// Hides or re-assigns a highlighted occurrence via
//   POST /stories/{id}/paragraphs/{pid}/suppressions   body SuppressRequest
// Per ADR 0008 §4 *both* rejections write a suppression, never a delete:
//   - "not an entity"  → entity_id null  (clears all claimants at the span)
//   - "not this entity"→ entity_id set   (clears just that entity)
//   - re-assign        → entity_id set + retag_to set (atomic suppress-then-tag, one grouped op)
// `retag_to` requires `entity_id` (the entity being corrected) — enforced server-side. Offsets
// are codepoints. A bad span 400s; a store outage 503s — both typed `ApiError`.
//
// On success it invalidates the reader (the highlight disappears / re-colours), the story graph
// (a re-assign's new mention may surface a node), and every entity-detail bundle for the story.
// All invalidated unconditionally, consistent with the sibling tag/edit hooks.
//
// Conventions (frontend/src/lib/api/AGENTS.md): one file per logical operation,
// `useMutation` only, schema types from `schema.d.ts`.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postJsonBody } from "./client";
import type { components } from "./schema";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

export { ApiError } from "./client";

export type SuppressRequest = components["schemas"]["SuppressRequest"];
export type SuppressResponse = components["schemas"]["SuppressResponse"];

export function useSuppressOccurrence(
  storyId: string,
  paragraphId: string,
): UseMutationResult<SuppressResponse, ApiError, SuppressRequest> {
  const queryClient = useQueryClient();
  return useMutation<SuppressResponse, ApiError, SuppressRequest>({
    mutationFn: (body) =>
      postJsonBody<SuppressResponse>(
        `/stories/${storyId}/paragraphs/${paragraphId}/suppressions`,
        body,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: entityDetailStoryKey(storyId) });
    },
  });
}
