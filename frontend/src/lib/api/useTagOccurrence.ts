// Manual-tag mutation hook (Session 48 — M4.S3c-fe2, spec §3.5 "manual tagging").
//
// Tags a `[span_start, span_end)` occurrence in a paragraph as an entity via
//   POST /stories/{id}/paragraphs/{pid}/tags   body TagRequest
// Exactly one of `entity_id` (attach to an existing accepted entity) or `new_entity`
// ({name, type}, create one) — the XOR is enforced server-side (a request-shape 400 otherwise).
// Creating a new entity is a human-reached graph write (INV-9 as reworded — ADR 0008 §3,
// reusing `create_entity`); attaching to an existing one writes only the Postgres mention.
// Offsets are codepoints (the units the reader's highlights use). A bad span 400s; a store
// outage 503s — both typed `ApiError`.
//
// On success it invalidates the reader (the new highlight renders), the story graph (a minted
// new entity becomes a node), and every entity-detail bundle for the story (the occurrence list
// reflects the new mention). All invalidated unconditionally — cheap, and avoids branching on
// whether a new entity was minted.
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

export type TagRequest = components["schemas"]["TagRequest"];
export type TagResponse = components["schemas"]["TagResponse"];

export function useTagOccurrence(
  storyId: string,
  paragraphId: string,
): UseMutationResult<TagResponse, ApiError, TagRequest> {
  const queryClient = useQueryClient();
  return useMutation<TagResponse, ApiError, TagRequest>({
    mutationFn: (body) =>
      postJsonBody<TagResponse>(`/stories/${storyId}/paragraphs/${paragraphId}/tags`, body),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: entityDetailStoryKey(storyId) });
    },
  });
}
