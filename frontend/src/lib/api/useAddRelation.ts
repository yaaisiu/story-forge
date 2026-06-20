// Add-relation mutation hook (Session 38 — M4.S3a-fe, spec §3.4 "relations editable").
//
// Adds a relation between two accepted entities via
//   POST /stories/{id}/relations   body {subject_id, predicate, object_id}
// A direct human-reached edge write (INV-9 as reworded — ADR 0006; DM-S3a-3 resolved to a
// direct edge-writer). A self-loop (subject == object) is allowed — a manual one is
// intentional. The deterministic `uuid5` edge id means a duplicate/colliding add folds onto
// the existing edge: the response carries `merged_into_existing: true` so the UI can warn
// (not an error). An unknown endpoint entity 404s; a store outage 503s — both typed `ApiError`.
//
// On success it invalidates every entity-detail bundle for the story (the relation touches
// two entities' panels — prefix `["entity-detail", storyId]`), the story graph (the new edge
// appears), and the reader (catalog consistency). Re-predicate is a client-side remove + add.
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

export type AddRelationRequest = components["schemas"]["AddRelationRequest"];
export type RelationEditResponse = components["schemas"]["RelationEditResponse"];

export function useAddRelation(
  storyId: string,
): UseMutationResult<RelationEditResponse, ApiError, AddRelationRequest> {
  const queryClient = useQueryClient();
  return useMutation<RelationEditResponse, ApiError, AddRelationRequest>({
    mutationFn: (body) => postJsonBody<RelationEditResponse>(`/stories/${storyId}/relations`, body),
    onSuccess: () => {
      // Prefix key — invalidates the detail bundle of *both* endpoint entities' panels.
      void queryClient.invalidateQueries({ queryKey: entityDetailStoryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
    },
  });
}
