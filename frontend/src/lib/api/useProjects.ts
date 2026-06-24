// Projects-listing query hook (Session 53 — M4 multi-story frontend, spec §3.4).
//
// Reads every project with its derived story_count from `GET /projects` — the
// project list the picker renders so the author can return to an existing project
// (and its stories) instead of re-uploading. A read-only projection; failures
// bubble as a typed `ApiError`.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useQuery` only (no `useEffect(fetch...)`), schema types from `schema.d.ts`.

import { useQuery, type UseQueryResult } from "@tanstack/react-query";

import { ApiError, getJson } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type ProjectSummary = components["schemas"]["ProjectSummary"];

/** TanStack Query key for the project list. */
export function projectsQueryKey(): [string] {
  return ["projects"];
}

/** Fetch every project (newest first), each with its derived story count. */
export function useProjects(): UseQueryResult<ProjectSummary[], ApiError> {
  return useQuery<ProjectSummary[], ApiError>({
    queryKey: projectsQueryKey(),
    queryFn: () => getJson<ProjectSummary[]>("/projects"),
    staleTime: 30_000,
  });
}
