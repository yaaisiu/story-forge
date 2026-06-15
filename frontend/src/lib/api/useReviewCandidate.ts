// Review-decision mutation hook (Session 25 — M3.S4b Stage 4 review UI).
//
// Commits a reviewer's decision on one staged candidate (spec §3.3 Stage 4):
//   accept → POST /stories/{id}/candidates/{cid}/accept  (the ONLY graph-writing path,
//            INV-1; body is the optional AcceptRequest — accept-as-create/merge,
//            change-target, custom-type — defaulting to the cascade's proposal)
//   reject → POST /stories/{id}/candidates/{cid}/reject   (nothing enters the graph;
//            the rejection is recorded as evidence)
//
// On success it always invalidates the queue (so the decided candidate drops off the
// list); an *accept* additionally invalidates the story graph (so it fills as the author
// commits a node), while a *reject* writes nothing to the graph and so skips that refetch.
// A 409 stale-merge-target bubbles as a typed `ApiError` the review card surfaces.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useMutation` only, schema types from `schema.d.ts`.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postJsonBody } from "./client";
import type { components } from "./schema";
import { candidatesQueryKey } from "./useCandidates";
import { storyGraphQueryKey } from "./useStoryGraph";

export { ApiError } from "./client";

export type AcceptRequest = components["schemas"]["AcceptRequest"];
export type ReviewResponse = components["schemas"]["ReviewResponse"];

export interface ReviewInput {
  candidateId: string;
  decision: "accept" | "reject";
  /** The reviewer's overrides for an accept (ignored for a reject); omit to take the
   * cascade's proposal as-is. */
  accept?: AcceptRequest;
}

export function useReviewCandidate(
  storyId: string,
): UseMutationResult<ReviewResponse, ApiError, ReviewInput> {
  const queryClient = useQueryClient();
  return useMutation<ReviewResponse, ApiError, ReviewInput>({
    mutationFn: ({ candidateId, decision, accept }) => {
      const path = `/stories/${storyId}/candidates/${candidateId}/${decision}`;
      // accept carries the optional AcceptRequest; reject takes no body (null).
      return postJsonBody<ReviewResponse>(path, decision === "accept" ? (accept ?? null) : null);
    },
    onSuccess: (_data, variables) => {
      void queryClient.invalidateQueries({ queryKey: candidatesQueryKey(storyId) });
      if (variables.decision === "accept") {
        void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      }
    },
  });
}
