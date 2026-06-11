// Extraction mutation hook (Session 17 — M2.S5 graph viewer).
//
// Triggers a graph-extraction run: POST `/stories/{id}/extract`. The backend walks
// the story's paragraphs, runs the ExtractionAgent, and writes entities/relations
// into Neo4j with no dedupe (spec §9 M2). The run is resumable:
//   200 → finished (paused=false)
//   202 → paused at the budget/quota pause-and-ask (partial progress; re-POST resumes)
//   502 → hard agent/transport failure
// Budget/quota are NOT errors here by design (OQ-2) — they come back as a 202 body
// with `paused=true`, so the caller treats 202 as success and reads `paused`.
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useMutation` only, schema types from `schema.d.ts`.

import { useMutation, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postJsonBody } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type ExtractResponse = components["schemas"]["ExtractResponse"];

export interface ExtractStoryInput {
  storyId: string;
}

export function useExtractStory(): UseMutationResult<ExtractResponse, ApiError, ExtractStoryInput> {
  return useMutation<ExtractResponse, ApiError, ExtractStoryInput>({
    // No request body — the route reads the story's persisted paragraphs itself.
    mutationFn: ({ storyId }) => postJsonBody<ExtractResponse>(`/stories/${storyId}/extract`, null),
  });
}
