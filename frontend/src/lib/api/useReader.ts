// Reader query hook (Session 33 — M4.S1 inline highlights, spec §3.5).
//
// Reads a story's text with resolved inline highlights from `GET /stories/{id}/reader`
// (DM-IH-2): paragraphs in document order, each with non-overlapping highlight ranges
// over its `text`, plus a tooltip catalog of the entities that appeared (DM-IH-8). The
// backend does the cross-store join (Postgres paragraphs+mentions × Neo4j entities) and
// the span resolution; the frontend only splits + renders.
//
// Stale-while-revalidate (mirrors `useStoryGraph`): the reader is a read-only projection
// of the accepted graph, which changes only when an extraction/accept writes to it — so a
// 30 s `staleTime` paints the cached text instantly on revisit and avoids a refetch storm
// while the author scrolls/hovers. Failures bubble as a typed `ApiError`.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type ReaderResponse = components["schemas"]["ReaderResponse"];
export type ReaderParagraph = components["schemas"]["ReaderParagraph"];
export type ReaderHighlight = components["schemas"]["ReaderHighlight"];
export type ReaderEntity = components["schemas"]["ReaderEntity"];

/** TanStack Query key for a story's reader view. */
export function readerQueryKey(storyId: string | undefined): [string, string | undefined] {
  return ["reader", storyId];
}

/**
 * Fetch a story's text + inline highlights. Disabled until a `storyId` is known (so it
 * never fires with `undefined` in the path during an initial render or a deep-link race).
 */
export function useReader(storyId: string | undefined): UseQueryResult<ReaderResponse, ApiError> {
  return useQuery<ReaderResponse, ApiError>({
    queryKey: readerQueryKey(storyId),
    queryFn: () => getJson<ReaderResponse>(`/stories/${storyId}/reader`),
    enabled: Boolean(storyId),
    staleTime: 30_000,
  });
}
