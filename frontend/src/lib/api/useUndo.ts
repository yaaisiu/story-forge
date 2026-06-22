// Undo mutation hook (Session 43 — M4.S3b-fe, DM-S3b-1 see-what-I-undo; spec §11/§4.3).
//
// Reverses the LAST graph edit anywhere in the story (story-scoped, not per-entity) via
//   POST /stories/{id}/graph-edits/undo[?preview=true]   → UndoResponse
// The undo stack is the grouped append-only `graph_edits` log; the executor replays the last live
// operation's child rows in reverse, atomically (a merge is one user action = many writes —
// ADR 0007). A human-reached write through the same edit handlers (INV-9), so INV-3 is *executed*.
//
// The affordance previews before it reverses (DM-S3b-1): call once with `preview=true` to read the
// human-readable `description` of what *would* be undone (applied=false, graph untouched), show it,
// then call again without `preview` to apply (applied=true). Nothing left to undo 404s; the graph
// drifted since the operation 409s — both typed `ApiError`.
//
// A preview must NOT mutate cache — only a real undo invalidates the reader, the story graph, and
// every entity-detail bundle for the story (prefix `["entity-detail", storyId]`).
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation, `useMutation` only.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postJsonBody } from "./client";
import type { components } from "./schema";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

export { ApiError } from "./client";

export type UndoResponse = components["schemas"]["UndoResponse"];

export function useUndo(storyId: string): UseMutationResult<UndoResponse, ApiError, boolean> {
  const queryClient = useQueryClient();
  return useMutation<UndoResponse, ApiError, boolean>({
    // The variable is `preview`: true reads what would be undone, false applies it.
    mutationFn: (preview) =>
      postJsonBody<UndoResponse>(
        `/stories/${storyId}/graph-edits/undo${preview ? "?preview=true" : ""}`,
        undefined,
      ),
    onSuccess: (_data, preview) => {
      if (preview) return; // a preview touched nothing — don't refetch.
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: entityDetailStoryKey(storyId) });
    },
  });
}
