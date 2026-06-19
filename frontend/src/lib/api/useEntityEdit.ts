// Entity-edit mutation hook (Session 38 — M4.S3a-fe, spec §3.4/§3.5 manual correction).
//
// Edits an accepted entity's name / type / aliases / `properties` via
//   PATCH /stories/{id}/entities/{eid}   body EntityEditPatch
// This is a human-reached graph write (INV-9 as reworded — ADR 0006): the backend
// validates + merges the patch, writes the Neo4j node, and records a before→after
// `graph_edits` evidence row (INV-3). A blank name/type is rejected (400); a stale
// entity 404s; a store outage 503s — each bubbles as a typed `ApiError`.
//
// On success it invalidates the reader (a corrected name re-highlights / a new type
// recolours for free — render-time search, DM-S3a-4), the story graph (recolour/relabel),
// and the entity-detail bundle (the panel refetches name/aliases/type/properties + ego-graph).
//
// Conventions (frontend/src/lib/api/CLAUDE.md): one file per logical operation,
// `useMutation` only, schema types from `schema.d.ts`.

import { useMutation, useQueryClient, type UseMutationResult } from "@tanstack/react-query";

import { ApiError, patchJsonBody } from "./client";
import type { components } from "./schema";
import { entityDetailQueryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

export { ApiError } from "./client";

export type EntityEditPatch = components["schemas"]["EntityEditPatch"];
export type EntityEditResponse = components["schemas"]["EntityEditResponse"];

export function useEntityEdit(
  storyId: string,
  entityId: string,
): UseMutationResult<EntityEditResponse, ApiError, EntityEditPatch> {
  const queryClient = useQueryClient();
  return useMutation<EntityEditResponse, ApiError, EntityEditPatch>({
    mutationFn: (patch) =>
      patchJsonBody<EntityEditResponse>(`/stories/${storyId}/entities/${entityId}`, patch),
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: readerQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: storyGraphQueryKey(storyId) });
      void queryClient.invalidateQueries({ queryKey: entityDetailQueryKey(storyId, entityId) });
    },
  });
}
