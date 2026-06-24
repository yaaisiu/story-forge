// First hand-written TanStack Query hook (Session 6 — Frontend upload UI).
//
// Posts a story file (.txt / .md / .docx) to `POST /stories/upload`. The backend
// validates the extension and content type (415), the size (413), and the
// parsed-content non-emptiness (400). On success it returns a typed
// `StoryUploadResponse` carrying the new project_id / story_id / language /
// paragraph_count. Failures bubble up as a typed `ApiError`, discriminated by
// status code — the upload screen renders distinct messages without ever
// string-matching the backend's detail text.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useMutation` only (no `useEffect(fetch...)`), schema types imported from the
// generated `schema.d.ts` (never hand-edited).

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postFormJson } from "./client";
import { projectsQueryKey } from "./useProjects";
import { projectStoriesQueryKey } from "./useProjectStories";
import type { components } from "./schema";

export { ApiError } from "./client";

export type StoryUploadResponse = components["schemas"]["StoryUploadResponse"];

export interface UploadStoryInput {
  file: File;
  /**
   * Optional target project (M4 multi-story): when set, the new story joins this
   * existing project instead of getting a fresh one. Sent as the `?project_id=`
   * query param; the route 404s a dangling project.
   */
  projectId?: string;
}

/**
 * Upload a story file to the backend. The form field name (`file`) matches the
 * FastAPI parameter in `backend/src/story_forge/api/stories.py:upload_story`.
 */
export function useUploadStory(): UseMutationResult<
  StoryUploadResponse,
  ApiError,
  UploadStoryInput
> {
  const queryClient = useQueryClient();
  return useMutation<StoryUploadResponse, ApiError, UploadStoryInput>({
    mutationFn: async ({ file, projectId }) => {
      const body = new FormData();
      body.append("file", file);
      const path = projectId
        ? `/stories/upload?project_id=${encodeURIComponent(projectId)}`
        : "/stories/upload";
      return postFormJson<StoryUploadResponse>(path, body);
    },
    onSuccess: (data) => {
      // The upload changes what the picker shows: a new project appears, or an
      // existing project's story_count and story list grow. Invalidate both lists
      // (keyed off the response's project_id, which is correct for the new-project
      // and add-into-existing cases alike) so a return to /projects is fresh, not
      // stale for the 30 s staleTime window.
      void queryClient.invalidateQueries({ queryKey: projectsQueryKey() });
      void queryClient.invalidateQueries({ queryKey: projectStoriesQueryKey(data.project_id) });
    },
  });
}
