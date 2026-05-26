// Structure mutation hook (Session 6 — Outline editor).
//
// Builds and persists the document tree for a story: POST
// `/stories/{id}/structure?mode=auto|manual|hybrid`, optionally with a JSON
// body `{raw_text}` carrying the manual editor's edited source. The backend
// uses the override when provided and updates `story.raw_text` in the same
// transaction, so the user's source-marker edits survive a later re-read
// (spec §7 step 2 "user accepts/edits").
//
// Error mapping mirrors the backend route's declared responses:
//   404 → story missing (a soft race: deleted between upload and submit)
//   409 → story already has a structure (the re-structure refusal)
//   422 → either FastAPI validation (e.g. mode not in the enum) or the domain-
//         level ChunkingTooLongError. The hook returns the raw body via
//         ApiError.body so the editor can discriminate by shape — tracked as
//         a cross-cutting follow-up in PLAN_SHORT.md.
//   502 → chunking agent failed (LLM unreachable or unusable output)

import { useMutation, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, postJsonBody } from "./client";
import type { components } from "./schema";

export { ApiError } from "./client";

export type StructureResponse = components["schemas"]["StructureResponse"];
export type ChunkingMode = StructureResponse["mode"];

export interface StructureStoryInput {
  storyId: string;
  mode: ChunkingMode;
  /** Manual editor's edited source. Omit (or pass null) for auto/hybrid. */
  rawText?: string;
}

export function useStructureStory(): UseMutationResult<
  StructureResponse,
  ApiError,
  StructureStoryInput
> {
  return useMutation<StructureResponse, ApiError, StructureStoryInput>({
    mutationFn: async ({ storyId, mode, rawText }) => {
      const query = new URLSearchParams({ mode });
      const path = `/stories/${storyId}/structure?${query.toString()}`;
      // Always send the body (even when the editor wasn't involved) so the
      // backend route signature stays consistent; the field is optional and
      // `null` means "use the stored raw_text".
      return postJsonBody<StructureResponse>(path, { raw_text: rawText ?? null });
    },
  });
}
