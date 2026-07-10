// The edge-edit form's React state (Graph-quality S5b-fe). A thin wrapper around the pure
// `edgeEditForm` module so `EdgeEvidencePanel` stays render-and-dispatch (no business logic
// in the component — frontend/src/AGENTS.md). The edge analogue of `useEntityEditForm`.

import { useState } from "react";

import type { RetargetRelationRequest } from "../../lib/api/useRetargetRelation";
import type { GraphEdge } from "../../lib/api/useStoryGraph";
import {
  buildRetargetPatch,
  canSaveEdgeForm,
  initialEdgeFormState,
  isEdgeFormDirty,
  type EdgeFormState,
  type EndpointDraft,
} from "./edgeEditForm";

const EMPTY_STATE: EdgeFormState = {
  predicateDraft: "",
  subject: { entity_id: "", canonical_name: "" },
  object: { entity_id: "", canonical_name: "" },
};

export interface EdgeEditForm {
  editing: boolean;
  state: EdgeFormState;
  dirty: boolean;
  canSave: boolean;
  startEditing: () => void;
  cancel: () => void;
  setPredicate: (value: string) => void;
  setSubject: (endpoint: EndpointDraft) => void;
  setObject: (endpoint: EndpointDraft) => void;
  buildPatch: () => RetargetRelationRequest;
}

export function useEdgeEditForm(
  edge: GraphEdge | undefined,
  nameOf: (id: string) => string,
): EdgeEditForm {
  const [editing, setEditing] = useState(false);
  const [state, setState] = useState<EdgeFormState>(EMPTY_STATE);

  function startEditing() {
    if (!edge) return;
    setState(initialEdgeFormState(edge, nameOf));
    setEditing(true);
  }

  return {
    editing,
    state,
    dirty: editing && edge ? isEdgeFormDirty(state, edge) : false,
    canSave: editing && edge ? canSaveEdgeForm(state, edge) : false,
    startEditing,
    cancel: () => setEditing(false),
    setPredicate: (value) => setState((s) => ({ ...s, predicateDraft: value })),
    setSubject: (endpoint) => setState((s) => ({ ...s, subject: endpoint })),
    setObject: (endpoint) => setState((s) => ({ ...s, object: endpoint })),
    buildPatch: () => (edge ? buildRetargetPatch(state, edge) : {}),
  };
}
