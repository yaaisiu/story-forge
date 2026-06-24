// Project-stories query hook (Session 53 — M4 multi-story frontend, spec §3.4).
//
// Reads a project's stories (title + ingested_at, newest first) from
// `GET /projects/{id}/stories` — what the picker shows once a project is selected.
// Disabled until a `projectId` is known so it never fires with `undefined` in the
// path. The route 404s an unknown project (fail-closed); that bubbles as a typed
// `ApiError` the picker can distinguish from an empty story list.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type StorySummary = components["schemas"]["StorySummary"];

/** TanStack Query key for a project's story list. */
export function projectStoriesQueryKey(
  projectId: string | undefined,
): [string, string | undefined] {
  return ["project-stories", projectId];
}

/** Fetch a project's stories. Disabled until a `projectId` is known. */
export function useProjectStories(
  projectId: string | undefined,
): UseQueryResult<StorySummary[], ApiError> {
  return useQuery<StorySummary[], ApiError>({
    queryKey: projectStoriesQueryKey(projectId),
    queryFn: () => getJson<StorySummary[]>(`/projects/${projectId}/stories`),
    enabled: Boolean(projectId),
    staleTime: 30_000,
  });
}
