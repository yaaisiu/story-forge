// The edge-edit form's pure logic (Graph-quality S5b-fe — the edge analogue of
// `entity-panel/entityEditForm.ts`). No React, no I/O — unit-tested like a pure module.
//
// The canvas edge panel edits an accepted relation edge: its predicate word and/or either
// endpoint, driving the atomic `PATCH …/relations/{edge_id}` (S5b-be). This module owns:
// seeding the form from the tapped `GraphEdge` (`initialEdgeFormState`), building the
// changed-fields-only PATCH body (`buildRetargetPatch`), gating the save (`canSaveEdgeForm`),
// and a `isEdgeFormDirty` predicate powering the panel-vanish guard (DM-S5-6): a dirty edit
// holds the selection so a background refetch/filter can't yank the panel mid-edit.
//
// The re-key changes the content-addressed edge id, so a saved edit re-points the selection
// (handled in the panel/GraphViewer); the pure form only produces the PATCH body.

import type { RetargetRelationRequest } from "../../lib/api/useRetargetRelation";
import type { GraphEdge } from "../../lib/api/useStoryGraph";

/** A chosen endpoint: the entity id the patch needs plus its display name for the UI. */
export interface EndpointDraft {
  entity_id: string;
  canonical_name: string;
}

export interface EdgeFormState {
  predicateDraft: string;
  subject: EndpointDraft;
  object: EndpointDraft;
}

/** Seed the editable drafts from the tapped edge, resolving endpoint names via `nameOf`. */
export function initialEdgeFormState(
  edge: GraphEdge,
  nameOf: (id: string) => string,
): EdgeFormState {
  return {
    predicateDraft: edge.type,
    subject: { entity_id: edge.subject_id, canonical_name: nameOf(edge.subject_id) },
    object: { entity_id: edge.object_id, canonical_name: nameOf(edge.object_id) },
  };
}

/** Build the PATCH body from the current drafts — only the fields that actually changed
 * (the backend requires at least one; an unchanged form yields `{}`). Predicate is trimmed. */
export function buildRetargetPatch(state: EdgeFormState, edge: GraphEdge): RetargetRelationRequest {
  const patch: RetargetRelationRequest = {};
  const predicate = state.predicateDraft.trim();
  if (predicate !== edge.type) patch.predicate = predicate;
  if (state.subject.entity_id !== edge.subject_id) patch.subject_id = state.subject.entity_id;
  if (state.object.entity_id !== edge.object_id) patch.object_id = state.object.entity_id;
  return patch;
}

/** Whether the form differs from the seeded edge — the guard's signal. A blanked predicate
 * still reads as dirty (an unsaved change is in flight), mirroring `isFormDirty`. */
export function isEdgeFormDirty(state: EdgeFormState, edge: GraphEdge): boolean {
  return hasChange(buildRetargetPatch(state, edge));
}

/** Whether the form is saveable: at least one field changed AND — if the predicate is being
 * changed — it is non-blank (the backend's S82 blank-predicate guard would reject a blank). */
export function canSaveEdgeForm(state: EdgeFormState, edge: GraphEdge): boolean {
  const patch = buildRetargetPatch(state, edge);
  const predicateOk = patch.predicate === undefined || patch.predicate !== "";
  return hasChange(patch) && predicateOk;
}

function hasChange(patch: RetargetRelationRequest): boolean {
  return (
    patch.predicate !== undefined || patch.subject_id !== undefined || patch.object_id !== undefined
  );
}
