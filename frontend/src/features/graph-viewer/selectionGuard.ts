// The graph canvas's node-selection guard (Graph-quality S5a, DM-S5-6).
//
// The viewer drops a node's selection when a filter/scope change hides it, so the details
// panel never shows a node that isn't on the canvas. But once that panel can *edit* a node,
// a naive "hidden → clear" rips the panel away mid-edit — an edit that changes the node's
// type, saved under an active type-filter, refetches the graph with the new type, the filter
// hides it, and the selection clears the instant the edit lands. This pure predicate adds the
// two DM-S5-6 exceptions: hold the selection while an edit form is dirty, and keep the
// just-edited node selected so the author can still inspect what they changed (they clear the
// filter to see it back on the canvas). Delete still clears unconditionally (it removes the
// node); a merge keeps the survivor selected.

export interface SelectionGuardInput {
  selectedNodeId: string | null;
  /** Whether the selected node is in the currently-visible (post-filter) set. */
  isVisible: boolean;
  /** An edit form on the panel has unsaved changes. */
  editDirty: boolean;
  /** The node whose edit just succeeded — kept selected through the post-save refetch. */
  justEditedId: string | null;
}

/** Whether the viewer should clear the node selection this render. */
export function shouldClearSelection({
  selectedNodeId,
  isVisible,
  editDirty,
  justEditedId,
}: SelectionGuardInput): boolean {
  if (!selectedNodeId) return false;
  if (isVisible) return false;
  if (editDirty) return false;
  if (selectedNodeId === justEditedId) return false;
  return true;
}
