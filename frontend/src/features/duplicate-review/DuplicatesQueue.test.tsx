// Tests for the possible-duplicates list container (Session 79 — Graph-quality S4b).
//
// The query hooks and the pair card are mocked so this isolates the container's own wiring:
// the load/error/empty/list states, keyboard nav + D-dismiss (via the shared review-queue hook +
// the pure reduceDuplicateKey), and the transient Undo that reverses a dismissal (DM-CD-3).

import { act } from "react";

import { MemoryRouter, Route, Routes } from "react-router-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DuplicateSuggestionView } from "../../lib/api/useDuplicateSuggestions";
import { DuplicatesQueue } from "./DuplicatesQueue";

const h = vi.hoisted(() => ({
  mode: { value: "success" as "success" | "loading" | "error" },
  items: [] as DuplicateSuggestionView[],
  dismissMutate: vi.fn(),
  undismissMutate: vi.fn(),
  undismissFails: { value: false },
}));

vi.mock("../../lib/api/useDuplicateSuggestions", () => ({
  useDuplicateSuggestions: () => {
    if (h.mode.value === "loading")
      return { data: undefined, isPending: true, isError: false, error: null };
    if (h.mode.value === "error")
      return { data: undefined, isPending: false, isError: true, error: undefined };
    return { data: { suggestions: h.items }, isPending: false, isError: false, error: null };
  },
}));

vi.mock("../../lib/api/useDismissDuplicate", () => ({
  useDismissDuplicate: () => ({
    mutate: (vars: unknown, opts?: { onSuccess?: () => void }) => {
      h.dismissMutate(vars);
      opts?.onSuccess?.();
    },
    isPending: false,
    isError: false,
    error: null,
    variables: undefined,
  }),
  useUndismissDuplicate: () => ({
    mutate: (vars: unknown, opts?: { onSuccess?: () => void }) => {
      h.undismissMutate(vars);
      // A failed un-dismiss does not run onSuccess, so the banner is not cleared.
      if (!h.undismissFails.value) opts?.onSuccess?.();
    },
    isPending: false,
    isError: h.undismissFails.value,
    error: undefined,
  }),
}));

vi.mock("./DuplicatePairCard", () => ({
  DuplicatePairCard: ({
    suggestion,
    isSelected,
    onDismiss,
  }: {
    suggestion: DuplicateSuggestionView;
    isSelected: boolean;
    onDismiss: () => void;
  }) => (
    <div data-testid="pair-stub" data-selected={String(isSelected)}>
      <span>{suggestion.entity_a.canonical_name}</span>
      <button type="button" data-testid="stub-dismiss" onClick={onDismiss}>
        dismiss
      </button>
    </div>
  ),
}));

function suggestion(id: string): DuplicateSuggestionView {
  return {
    entity_a: {
      entity_id: `${id}-a`,
      canonical_name: `A-${id}`,
      type: "Person",
      aliases: [],
      context_quote: null,
    },
    entity_b: {
      entity_id: `${id}-b`,
      canonical_name: `B-${id}`,
      type: "Person",
      aliases: [],
      context_quote: null,
    },
    name_score: 90,
    cosine_score: 0.9,
    combined_score: 0.9,
  };
}

function renderQueue() {
  render(
    <MemoryRouter initialEntries={["/stories/s1/duplicates"]}>
      <Routes>
        <Route path="/stories/:storyId/duplicates" element={<DuplicatesQueue />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  h.mode.value = "success";
  h.items = [];
  h.undismissFails.value = false;
});

describe("DuplicatesQueue", () => {
  it("shows the loading state", () => {
    h.mode.value = "loading";
    renderQueue();
    expect(screen.getByTestId("duplicates-loading")).toBeInTheDocument();
  });

  it("shows the error state", () => {
    h.mode.value = "error";
    renderQueue();
    expect(screen.getByTestId("duplicates-error")).toBeInTheDocument();
  });

  it("shows the empty state when there are no suggestions", () => {
    h.items = [];
    renderQueue();
    expect(screen.getByTestId("duplicates-empty")).toBeInTheDocument();
  });

  it("renders one card per suggestion", () => {
    h.items = [suggestion("1"), suggestion("2")];
    renderQueue();
    expect(screen.getAllByTestId("pair-stub")).toHaveLength(2);
    // The first card is selected by default.
    expect(screen.getAllByTestId("pair-stub")[0]).toHaveAttribute("data-selected", "true");
  });

  it("navigates with J/K and dismisses the selected pair with D", () => {
    h.items = [suggestion("1"), suggestion("2")];
    renderQueue();

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "j" })));
    expect(screen.getAllByTestId("pair-stub")[1]).toHaveAttribute("data-selected", "true");

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "d" })));
    // D dismisses the *selected* (second) pair.
    expect(h.dismissMutate).toHaveBeenCalledWith({ entityIdA: "2-a", entityIdB: "2-b" });
  });

  it("dismissing shows a transient Undo that reverses the dismissal", () => {
    h.items = [suggestion("1")];
    renderQueue();

    fireEvent.click(screen.getByTestId("stub-dismiss"));
    expect(h.dismissMutate).toHaveBeenCalledWith({ entityIdA: "1-a", entityIdB: "1-b" });

    const undo = screen.getByTestId("duplicates-undo");
    expect(undo).toHaveTextContent("A-1 & B-1");

    fireEvent.click(screen.getByTestId("duplicates-undo-button"));
    expect(h.undismissMutate).toHaveBeenCalledWith({ entityIdA: "1-a", entityIdB: "1-b" });
    // Undo clears the banner.
    expect(screen.queryByTestId("duplicates-undo")).not.toBeInTheDocument();
  });

  it("surfaces a failed Undo and keeps the banner so it can be retried", () => {
    h.undismissFails.value = true;
    h.items = [suggestion("1")];
    renderQueue();

    fireEvent.click(screen.getByTestId("stub-dismiss"));
    fireEvent.click(screen.getByTestId("duplicates-undo-button"));

    expect(h.undismissMutate).toHaveBeenCalledWith({ entityIdA: "1-a", entityIdB: "1-b" });
    // The failure is shown (not swallowed) and the banner remains for a retry.
    expect(screen.getByTestId("duplicates-undismiss-error")).toBeInTheDocument();
    expect(screen.getByTestId("duplicates-undo")).toBeInTheDocument();
  });
});
