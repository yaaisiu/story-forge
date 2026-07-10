// The graph canvas's selection guard (Graph-quality S5a node, DM-S5-6; extended S5b-fe edge).
//
// The viewer drops a node's/edge's selection when a filter/scope change (or a re-keying edit)
// hides it, so the details panel never shows an element that isn't on the canvas. But once that
// panel can *edit* the element, a naive "hidden → clear" rips the panel away mid-edit — an edit
// that changes a node's type (or re-predicates/re-targets an edge), saved under an active
// filter, refetches the graph, the filter/re-key hides the old element, and the selection clears
// the instant the edit lands. This pure predicate adds the two DM-S5-6 exceptions: hold the
// selection while an edit form is dirty, and keep the just-edited element selected so the author
// can still inspect what they changed (they clear the filter to see it back on the canvas). It is
// shared by both the node and the edge selection (each passes its own id/visibility/guard state).
// Delete still clears unconditionally (it removes the element); a merge keeps the survivor.

export interface SelectionGuardInput {
  /** The selected node or edge id, or null when nothing is selected. */
  selectedId: string | null;
  /** Whether the selected element is in the currently-visible (post-filter) set. */
  isVisible: boolean;
  /** An edit form on the panel has unsaved changes. */
  editDirty: boolean;
  /** The element whose edit just succeeded — kept selected through the post-save refetch
   * (for an edge re-key, this is the *new* content id the selection re-points to). */
  justEditedId: string | null;
}

/** Whether the viewer should clear the selection this render. */
export function shouldClearSelection({
  selectedId,
  isVisible,
  editDirty,
  justEditedId,
}: SelectionGuardInput): boolean {
  if (!selectedId) return false;
  if (isVisible) return false;
  if (editDirty) return false;
  if (selectedId === justEditedId) return false;
  return true;
}
