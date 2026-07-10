// The shared entity-edit form's React state (Graph-quality S5a). A thin wrapper around the
// pure `entityEditForm` module so `EntityEditPanel` stays render-and-dispatch (no business
// logic in the component — frontend/src/AGENTS.md). Both the reader and the graph canvas
// drive their edit form through this hook.

import { useState } from "react";

import type { EntityDetailResponse } from "../../lib/api/useEntityDetail";
import type { EntityEditPatch } from "../../lib/api/useEntityEdit";
import {
  buildEntityEditPatch,
  canSaveForm,
  initialFormState,
  isFormDirty,
  type EditFormState,
} from "./entityEditForm";
import type { PropertyRow } from "./propertiesEditor";

const EMPTY_STATE: EditFormState = { nameDraft: "", typeDraft: "", aliasDrafts: [], propRows: [] };

export interface EntityEditForm {
  editing: boolean;
  state: EditFormState;
  dirty: boolean;
  canSave: boolean;
  startEditing: () => void;
  cancel: () => void;
  setName: (value: string) => void;
  setType: (value: string) => void;
  setAliases: (next: string[] | ((prev: string[]) => string[])) => void;
  setPropRows: (next: PropertyRow[] | ((prev: PropertyRow[]) => PropertyRow[])) => void;
  buildPatch: (language: string) => EntityEditPatch;
}

export function useEntityEditForm(
  detail: EntityDetailResponse | undefined,
  hasStory: boolean,
): EntityEditForm {
  const [editing, setEditing] = useState(false);
  const [state, setState] = useState<EditFormState>(EMPTY_STATE);

  function startEditing() {
    if (!detail) return;
    setState(initialFormState(detail));
    setEditing(true);
  }

  return {
    editing,
    state,
    dirty: editing && detail ? isFormDirty(state, detail) : false,
    canSave: canSaveForm(state, hasStory),
    startEditing,
    cancel: () => setEditing(false),
    setName: (value) => setState((s) => ({ ...s, nameDraft: value })),
    setType: (value) => setState((s) => ({ ...s, typeDraft: value })),
    setAliases: (next) =>
      setState((s) => ({
        ...s,
        aliasDrafts: typeof next === "function" ? next(s.aliasDrafts) : next,
      })),
    setPropRows: (next) =>
      setState((s) => ({ ...s, propRows: typeof next === "function" ? next(s.propRows) : next })),
    buildPatch: (language) => buildEntityEditPatch(state, language),
  };
}
