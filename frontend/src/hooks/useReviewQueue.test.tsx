// Tests for the shared review-queue hook (Session 79 — Graph-quality S4b).
//
// Extracted from the identical inline skeleton the extraction- and relation-review
// queues each carried: a clamped `selectedIndex` cursor + a window `keydown` that skips
// editable targets and delegates to a pure per-feature reducer. These pins encode the
// behaviour both screens depended on, so the migration onto the hook is provably faithful.

import { act, renderHook } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { isEditableTarget, useReviewQueue } from "./useReviewQueue";

interface Nav {
  selectedIndex: number;
}

/** A toy reducer: j advances, a commits an "ACCEPT" intent, everything else is ignored. */
function reduceToy(key: string, state: Nav): { state: Nav; intent?: string } | null {
  if (key === "j") return { state: { selectedIndex: state.selectedIndex + 1 } };
  if (key === "a") return { state, intent: "ACCEPT" };
  return null;
}

function press(key: string) {
  act(() => {
    window.dispatchEvent(new KeyboardEvent("keydown", { key }));
  });
}

describe("isEditableTarget", () => {
  it("is true for INPUT/TEXTAREA/SELECT, false for a plain element or null", () => {
    // (contentEditable is also editable in a real browser, but jsdom doesn't implement
    // `isContentEditable`, so it isn't asserted here — the production guard still checks it.)
    const input = document.createElement("input");
    const textarea = document.createElement("textarea");
    const select = document.createElement("select");
    const div = document.createElement("div");

    expect(isEditableTarget(input)).toBe(true);
    expect(isEditableTarget(textarea)).toBe(true);
    expect(isEditableTarget(select)).toBe(true);
    expect(isEditableTarget(div)).toBe(false);
    expect(isEditableTarget(null)).toBe(false);
  });
});

describe("useReviewQueue", () => {
  it("clamps selectedIndex into range as the list shrinks", () => {
    const { result, rerender } = renderHook(
      ({ items }) =>
        useReviewQueue<number, Nav, string>({
          items,
          initialState: { selectedIndex: 5 },
          reduceKey: reduceToy,
          onCommit: () => {},
        }),
      { initialProps: { items: [10, 20, 30] } },
    );

    // selectedIndex 5 against a length-3 list clamps to 2.
    expect(result.current.state.selectedIndex).toBe(2);

    rerender({ items: [10] });
    expect(result.current.state.selectedIndex).toBe(0);

    rerender({ items: [] });
    expect(result.current.state.selectedIndex).toBe(0);
  });

  it("dispatches a keypress through the reducer and advances the cursor", () => {
    const onCommit = vi.fn();
    const { result } = renderHook(() =>
      useReviewQueue<number, Nav, string>({
        items: [10, 20, 30],
        initialState: { selectedIndex: 0 },
        reduceKey: reduceToy,
        onCommit,
      }),
    );

    press("j");
    expect(result.current.state.selectedIndex).toBe(1);
    expect(onCommit).not.toHaveBeenCalled();
  });

  it("calls onCommit with the reduced state and intent on a committing key", () => {
    const onCommit = vi.fn();
    renderHook(() =>
      useReviewQueue<number, Nav, string>({
        items: [10, 20, 30],
        initialState: { selectedIndex: 1 },
        reduceKey: reduceToy,
        onCommit,
      }),
    );

    press("a");
    expect(onCommit).toHaveBeenCalledWith({ selectedIndex: 1 }, "ACCEPT");
  });

  it("ignores a keypress originating from an editable field", () => {
    const onCommit = vi.fn();
    const input = document.createElement("input");
    document.body.appendChild(input);

    const { result } = renderHook(() =>
      useReviewQueue<number, Nav, string>({
        items: [10, 20, 30],
        initialState: { selectedIndex: 0 },
        reduceKey: reduceToy,
        onCommit,
      }),
    );

    act(() => {
      input.dispatchEvent(new KeyboardEvent("keydown", { key: "j", bubbles: true }));
    });

    expect(result.current.state.selectedIndex).toBe(0);
    expect(onCommit).not.toHaveBeenCalled();
    document.body.removeChild(input);
  });

  it("ignores keys the reducer does not recognise", () => {
    const onCommit = vi.fn();
    const { result } = renderHook(() =>
      useReviewQueue<number, Nav, string>({
        items: [10, 20, 30],
        initialState: { selectedIndex: 0 },
        reduceKey: reduceToy,
        onCommit,
      }),
    );

    press("z");
    expect(result.current.state.selectedIndex).toBe(0);
    expect(onCommit).not.toHaveBeenCalled();
  });
});
