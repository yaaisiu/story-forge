import { describe, expect, it } from "vitest";

import { shouldClearSelection } from "./selectionGuard";

describe("shouldClearSelection", () => {
  const base = {
    selectedId: "n1",
    isVisible: false,
    editDirty: false,
    justEditedId: null as string | null,
  };

  it("never clears when nothing is selected", () => {
    expect(shouldClearSelection({ ...base, selectedId: null })).toBe(false);
  });

  it("never clears while the node is still visible", () => {
    expect(shouldClearSelection({ ...base, isVisible: true })).toBe(false);
  });

  it("clears a hidden node that is neither being edited nor just edited", () => {
    expect(shouldClearSelection(base)).toBe(true);
  });

  it("holds the selection while an edit form is dirty (DM-S5-6 guard)", () => {
    expect(shouldClearSelection({ ...base, editDirty: true })).toBe(false);
  });

  it("keeps the just-edited node selected even when a filter now hides it", () => {
    expect(shouldClearSelection({ ...base, justEditedId: "n1" })).toBe(false);
  });

  it("still clears when justEditedId points at a different node", () => {
    expect(shouldClearSelection({ ...base, justEditedId: "other" })).toBe(true);
  });
});
