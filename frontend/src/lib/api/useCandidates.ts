// Review-queue fetch hook (Session 25 — M3.S4b Stage 4 review UI).
//
// Reads a story's pending review queue from `GET /stories/{id}/candidates` — the
// staged candidates awaiting a human decision (spec §3.3 Stage 4). Each item carries
// the quote/context, the cascade's NEW-vs-MERGE proposal + stage reached, the judge's
// reasoning, and the top-3 alternative entities the reviewer can retarget to.
//
// No `staleTime`: unlike the graph, the queue mutates with every accept/reject the
// reviewer makes, so `useReviewCandidate` invalidates this key to refetch the shrinking
// list immediately. A 503 (staging store down) bubbles as a typed `ApiError`.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type CandidatesResponse = components["schemas"]["CandidatesResponse"];
export type CandidateView = components["schemas"]["CandidateView"];

/** TanStack Query key for a story's review queue — shared with the invalidation in
 * `useReviewCandidate`, so an accept/reject refetches the shrinking list. */
export function candidatesQueryKey(storyId: string | undefined): [string, string | undefined] {
  return ["candidates", storyId];
}

/**
 * Fetch a story's pending review queue. Disabled until a `storyId` is known (so it
 * never fires with `undefined` in the path during an initial render or deep-link race).
 */
export function useCandidates(
  storyId: string | undefined,
): UseQueryResult<CandidatesResponse, ApiError> {
  return useQuery<CandidatesResponse, ApiError>({
    queryKey: candidatesQueryKey(storyId),
    queryFn: () => getJson<CandidatesResponse>(`/stories/${storyId}/candidates`),
    enabled: Boolean(storyId),
  });
}
