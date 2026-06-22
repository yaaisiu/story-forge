// Change-boundaries mutation hook (Session 48 — M4.S3c-fe2, spec §3.5 "change boundaries").
//
// Adjusts a highlighted occurrence's span via
//   POST /stories/{id}/paragraphs/{pid}/boundaries   body BoundaryRequest
// `mention_id` null = an auto *search hit* to **materialize** (the route creates a manual mention
// at the new offsets and suppresses the original position so search doesn't re-surface it as a
// duplicate — DM-S3c-4); set = an existing manual mention edited in place. `old_start`/`old_end`
// carry the original span (needed to suppress it on materialize). Offsets are codepoints. A bad
// new span 400s; a store outage 503s — both typed `ApiError`.
//
// On success it invalidates the reader (the highlight moves) and every entity-detail bundle for
// the story (the occurrence's offsets changed). The graph is untouched — boundaries don't change
// entity identity — but it is invalidated too for consistency with the sibling hooks.
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

export type BoundaryRequest = components["schemas"]["BoundaryRequest"];
export type BoundaryResponse = components["schemas"]["BoundaryResponse"];

export function useChangeBoundaries(
  storyId: string,
  paragraphId: string,
): UseMutationResult<BoundaryResponse, ApiError, BoundaryRequest> {
  const queryClient = useQueryClient();
  return useMutation<BoundaryResponse, ApiError, BoundaryRequest>({
    mutationFn: (body) =>
      postJsonBody<BoundaryResponse>(
        `/stories/${storyId}/paragraphs/${paragraphId}/boundaries`,
        body,
      ),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: entityDetailStoryKey(storyId) });
    },
  });
}
