// Relation-decision mutation hook (Session 30 — M3.S4f, spec §3.3's 5th human action).
//
// Commits the author's decision on one staged relation via
//   POST /stories/{id}/relations/{relationId}/decide   body {action: "commit" | "reject"}
// A "commit" writes the graph edge between the two resolved endpoints (the human gate —
// no automated stage writes an edge); a "reject" records the decision and writes nothing.
//
// On success it always invalidates the relation queue (so the decided relation drops off
// the list); a *commit* additionally invalidates the story graph (so the new edge appears
// in the §3.4 viewer) **and the reader** (whose §3.5 tooltip summary is derived from the
// project's edges — S7), while a *reject* writes nothing to the graph and skips both.
// A 409 (already decided) or 404 bubbles as a typed `ApiError` the queue surfaces.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useMutation` only, schema types from `schema.d.ts`.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postJsonBody } from "./client";
import type { components } from "./schema";
import { readerQueryKey } from "./useReader";
import { relationsQueryKey } from "./useRelations";
import { storyGraphQueryKey } from "./useStoryGraph";

export { ApiError } from "./client";

export type DecideRelationRequest = components["schemas"]["DecideRelationRequest"];
export type RelationDecisionResponse = components["schemas"]["RelationDecisionResponse"];

export interface DecideInput {
  relationId: string;
  action: DecideRelationRequest["action"];
}

export function useDecideRelation(
  storyId: string,
): UseMutationResult<RelationDecisionResponse, ApiError, DecideInput> {
  const queryClient = useQueryClient();
  return useMutation<RelationDecisionResponse, ApiError, DecideInput>({
    mutationFn: ({ relationId, action }) =>
      postJsonBody<RelationDecisionResponse>(`/stories/${storyId}/relations/${relationId}/decide`, {
        action,
      }),
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: relationsQueryKey(storyId) });
      if (variables.action === "commit") {
        void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
        // The reader's §3.5 tooltip summary is derived from the project's edges, so a committed
        // edge dirties it too — without this the reader serves a stale summary for the length of
        // its `staleTime`, disagreeing with the graph view of the same data.
        void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
      }
    },
  });
}
