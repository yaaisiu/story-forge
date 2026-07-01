// Edge-evidence query hook (Session 76 — Graph-quality S3b, DM-EE-1/2, spec §3.4).
//
// Reads all recorded provenance behind one graph edge from
// `GET /stories/{id}/relations/{edge_id}/evidence` (the focused per-edge BFF read,
// DM-EE-1a): the predicate plus every source paragraph that asserts the fact
// (`{paragraph_id, paragraph_text, evidence_quote}`). Provenance is one-to-many —
// the content-addressed edge collapses the same fact across N paragraphs to one edge,
// so `source_provenance` is a list. An edge added by hand (no staged row) resolves as
// a 200 with an empty list — the panel renders "no recorded source (added manually)",
// not an error.
//
// Fetched per tap (not baked into the /graph payload): most edges are never inspected,
// so the panel pays one small read when the author taps it rather than inflating a
// dense-graph download with one-to-many data (the DM-SP-1 / DM-EE-1 precedent). Stale-
// while-revalidate with a 30 s `staleTime` (mirrors useEntityDetail): the evidence is a
// read-only projection of committed state. Failures bubble as a typed `ApiError`.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type EdgeEvidence = components["schemas"]["EdgeEvidence"];
export type EdgeEvidenceSource = components["schemas"]["EdgeEvidenceSource"];

/** TanStack Query key for one story-scoped edge's evidence bundle. */
export function edgeEvidenceQueryKey(
  storyId: string | undefined,
  edgeId: string | undefined,
): [string, string | undefined, string | undefined] {
  return ["edge-evidence", storyId, edgeId];
}

/**
 * Fetch one edge's evidence bundle for the graph-viewer panel. Disabled until both a
 * `storyId` and an `edgeId` are known (so it never fires with `undefined` in the path
 * before the author has tapped an edge).
 */
export function useEdgeEvidence(
  storyId: string | undefined,
  edgeId: string | undefined,
): UseQueryResult<EdgeEvidence, ApiError> {
  return useQuery<EdgeEvidence, ApiError>({
    queryKey: edgeEvidenceQueryKey(storyId, edgeId),
    queryFn: () => getJson<EdgeEvidence>(`/stories/${storyId}/relations/${edgeId}/evidence`),
    enabled: Boolean(storyId) && Boolean(edgeId),
    staleTime: 30_000,
  });
}
