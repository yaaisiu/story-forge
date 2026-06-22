// Tests for the reader's right-click correction menu (Session 48 — M4.S3c-fe2).
//
// Pins: a highlight right-click offers the four corrections (not-this / re-assign / not-an-entity
// / change-boundaries); a selection right-click offers only "tag as entity"; each item dispatches
// its action; Escape and an outside click dismiss.

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import { ReaderContextMenu } from "./ReaderContextMenu";
import type { ContextMenuRequest } from "./correction";

function highlightRequest(over: Partial<ContextMenuRequest> = {}): ContextMenuRequest {
  return {
    anchor: { x: 10, y: 20 },
    target: "highlight",
    paragraphId: "p1",
    span_start: 0,
    span_end: 5,
    selectedText: "Janek",
    entityId: "e1",
    source: "search",
    mentionId: null,
    ...over,
  };
}

function selectionRequest(over: Partial<ContextMenuRequest> = {}): ContextMenuRequest {
  return {
    anchor: { x: 10, y: 20 },
    target: "selection",
    paragraphId: "p1",
    span_start: 4,
    span_end: 9,
    selectedText: "Janek",
    ...over,
  };
}

describe("ReaderContextMenu", () => {
  it("offers the four corrections on a highlight and dispatches the chosen action", () => {
    const onAction = vi.fn();
    render(
      <ReaderContextMenu request={highlightRequest()} onAction={onAction} onDismiss={vi.fn()} />,
    );

    expect(screen.getByTestId("context-not-this")).toBeInTheDocument();
    expect(screen.getByTestId("context-reassign")).toBeInTheDocument();
    expect(screen.getByTestId("context-not-an-entity")).toBeInTheDocument();
    expect(screen.getByTestId("context-change-boundaries")).toBeInTheDocument();
    // A highlight never offers "tag as entity" — that's selection-only.
    expect(screen.queryByTestId("context-tag")).toBeNull();

    fireEvent.click(screen.getByTestId("context-change-boundaries"));
    expect(onAction).toHaveBeenCalledWith("change-boundaries");
  });

  it("offers only 'tag as entity' on a selection", () => {
    const onAction = vi.fn();
    render(
      <ReaderContextMenu request={selectionRequest()} onAction={onAction} onDismiss={vi.fn()} />,
    );

    expect(screen.getByTestId("context-tag")).toBeInTheDocument();
    expect(screen.queryByTestId("context-not-this")).toBeNull();

    fireEvent.click(screen.getByTestId("context-tag"));
    expect(onAction).toHaveBeenCalledWith("tag");
  });

  it("positions the menu at the click anchor", () => {
    render(
      <ReaderContextMenu
        request={highlightRequest({ anchor: { x: 42, y: 99 } })}
        onAction={vi.fn()}
        onDismiss={vi.fn()}
      />,
    );
    const menu = screen.getByTestId("reader-context-menu");
    expect(menu.style.left).toBe("42px");
    expect(menu.style.top).toBe("99px");
  });

  it("dismisses on Escape", () => {
    const onDismiss = vi.fn();
    render(
      <ReaderContextMenu request={highlightRequest()} onAction={vi.fn()} onDismiss={onDismiss} />,
    );
    fireEvent.keyDown(document, { key: "Escape" });
    expect(onDismiss).toHaveBeenCalled();
  });

  it("dismisses on an outside click", () => {
    const onDismiss = vi.fn();
    render(
      <div>
        <button data-testid="outside">elsewhere</button>
        <ReaderContextMenu request={highlightRequest()} onAction={vi.fn()} onDismiss={onDismiss} />
      </div>,
    );
    fireEvent.mouseDown(screen.getByTestId("outside"));
    expect(onDismiss).toHaveBeenCalled();
  });

  it("does not dismiss on a click inside the menu", () => {
    const onDismiss = vi.fn();
    render(
      <ReaderContextMenu request={highlightRequest()} onAction={vi.fn()} onDismiss={onDismiss} />,
    );
    fireEvent.mouseDown(screen.getByTestId("context-not-this"));
    expect(onDismiss).not.toHaveBeenCalled();
  });
});
