// Tests for the reader's correction input popover (Session 48 — M4.S3c-fe2).
//
// Pins: tag mode pre-fills the new-entity name from the selection, toggles existing/new, disables
// "create" until name+type are non-blank, and dispatches the right callback; re-assign mode only
// ever picks an existing entity; the container's error.detail renders inline. EntityPicker is
// mocked to a fixed-pick button, exactly as ReaderEntityPanel.test.tsx mocks it.

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReaderCorrectionPopover } from "./ReaderCorrectionPopover";
import type { ContextMenuRequest } from "./correction";
import type { ApiError } from "../../lib/api/client";

const PICKED_ID = "22222222-2222-2222-2222-222222222222";

vi.mock("../extraction-review/EntityPicker", () => ({
  EntityPicker: ({ onPick }: { onPick: (r: { entity_id: string }) => void }) => (
    <button data-testid="entity-picker-pick" onClick={() => onPick({ entity_id: PICKED_ID })}>
      pick
    </button>
  ),
}));

function request(over: Partial<ContextMenuRequest> = {}): ContextMenuRequest {
  return {
    anchor: { x: 10, y: 20 },
    target: "selection",
    paragraphId: "p1",
    span_start: 0,
    span_end: 5,
    selectedText: "Janek",
    ...over,
  };
}

function renderPopover(props: Partial<Parameters<typeof ReaderCorrectionPopover>[0]> = {}) {
  const onSubmitExisting = vi.fn();
  const onSubmitNew = vi.fn();
  const onCancel = vi.fn();
  render(
    <ReaderCorrectionPopover
      storyId="s1"
      mode="tag"
      request={request()}
      pending={false}
      error={null}
      onSubmitExisting={onSubmitExisting}
      onSubmitNew={onSubmitNew}
      onCancel={onCancel}
      {...props}
    />,
  );
  return { onSubmitExisting, onSubmitNew, onCancel };
}

describe("ReaderCorrectionPopover", () => {
  it("tags an existing entity via the reused picker", () => {
    const { onSubmitExisting } = renderPopover();
    fireEvent.click(screen.getByTestId("entity-picker-pick"));
    expect(onSubmitExisting).toHaveBeenCalledWith(PICKED_ID);
  });

  it("pre-fills the new-entity name from the selection and creates with an open-world type", () => {
    const { onSubmitNew } = renderPopover();
    fireEvent.click(screen.getByTestId("tag-mode-new"));

    const name = screen.getByTestId("new-entity-name") as HTMLInputElement;
    expect(name.value).toBe("Janek"); // pre-filled from request.selectedText

    // Type is free text (no enum) — submit stays disabled until it is filled.
    const submit = screen.getByTestId("new-entity-submit") as HTMLButtonElement;
    expect(submit.disabled).toBe(true);

    fireEvent.change(screen.getByTestId("new-entity-type"), { target: { value: "ghost" } });
    expect(submit.disabled).toBe(false);
    fireEvent.click(submit);
    expect(onSubmitNew).toHaveBeenCalledWith("Janek", "ghost");
  });

  it("keeps the create button disabled when the name is blanked", () => {
    renderPopover();
    fireEvent.click(screen.getByTestId("tag-mode-new"));
    fireEvent.change(screen.getByTestId("new-entity-type"), { target: { value: "ghost" } });
    fireEvent.change(screen.getByTestId("new-entity-name"), { target: { value: "  " } });
    expect((screen.getByTestId("new-entity-submit") as HTMLButtonElement).disabled).toBe(true);
  });

  it("re-assign mode offers only the existing-entity picker (no new-entity path)", () => {
    const { onSubmitExisting } = renderPopover({ mode: "reassign" });
    expect(screen.queryByTestId("tag-mode-new")).toBeNull();
    fireEvent.click(screen.getByTestId("entity-picker-pick"));
    expect(onSubmitExisting).toHaveBeenCalledWith(PICKED_ID);
  });

  it("renders the container's error detail inline", () => {
    renderPopover({ error: { status: 400, detail: "span is empty" } as ApiError });
    expect(screen.getByTestId("correction-error")).toHaveTextContent("span is empty");
  });

  it("cancels", () => {
    const { onCancel } = renderPopover();
    fireEvent.click(screen.getByTestId("correction-cancel"));
    expect(onCancel).toHaveBeenCalled();
  });
});
