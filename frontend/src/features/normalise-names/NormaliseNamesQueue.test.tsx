// Tests for the name-normalisation list container (Session 96 — Graph-quality S6b).
//
// The query/mutation hooks and the pair card are mocked so this isolates the container's own wiring:
// the load/error/empty states, the two grouped sections over one flat cursor, keyboard nav + D-dismiss
// (via the shared review-queue hook + the pure reduceNormaliseKey), the transient Undo that reverses a
// dismissal (DM-NN-3), and the post-rename status banner.

import { act } from "react";

import { MemoryRouter, Route, Routes } from "react-router-dom";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { LabelVocabularyResponse } from "../../lib/api/useLabelVocabulary";
import type { LabelPairItem } from "./normaliseNames";
import type { RenameOutcome } from "./LabelPairCard";
import { NormaliseNamesQueue } from "./NormaliseNamesQueue";

const h = vi.hoisted(() => ({
  mode: { value: "success" as "success" | "loading" | "error" },
  data: { value: null as LabelVocabularyResponse | null },
  dismissMutate: vi.fn(),
  undismissMutate: vi.fn(),
  undismissFails: { value: false },
}));

vi.mock("../../lib/api/useLabelVocabulary", () => ({
  useLabelVocabulary: () => {
    if (h.mode.value === "loading")
      return { data: undefined, isPending: true, isError: false, error: null };
    if (h.mode.value === "error")
      return { data: undefined, isPending: false, isError: true, error: undefined };
    return { data: h.data.value, isPending: false, isError: false, error: null };
  },
}));

vi.mock("../../lib/api/useDismissLabel", () => ({
  useDismissLabel: () => ({
    mutate: (vars: unknown, opts?: { onSuccess?: () => void }) => {
      h.dismissMutate(vars);
      opts?.onSuccess?.();
    },
    isPending: false,
    isError: false,
    error: null,
    variables: undefined,
  }),
  useUndismissLabel: () => ({
    mutate: (vars: unknown, opts?: { onSuccess?: () => void }) => {
      h.undismissMutate(vars);
      if (!h.undismissFails.value) opts?.onSuccess?.();
    },
    isPending: false,
    isError: h.undismissFails.value,
    error: undefined,
  }),
}));

vi.mock("./LabelPairCard", () => ({
  LabelPairCard: ({
    item,
    isSelected,
    onDismiss,
    onRenamed,
  }: {
    item: LabelPairItem;
    isSelected: boolean;
    onDismiss: () => void;
    onRenamed: (o: RenameOutcome) => void;
  }) => (
    <div data-testid="pair-stub" data-surface={item.surface} data-selected={String(isSelected)}>
      <span>{item.pair.label_hi}</span>
      <button type="button" data-testid="stub-dismiss" onClick={onDismiss}>
        dismiss
      </button>
      <button
        type="button"
        data-testid="stub-rename"
        onClick={() =>
          onRenamed({
            summary: { surface: item.surface, renamed_count: 2, folded_count: 0 },
            fromLabel: item.pair.label_lo,
            toLabel: item.pair.label_hi,
          })
        }
      >
        rename
      </button>
    </div>
  ),
}));

function synonym(lo: string, hi: string): LabelPairItem["pair"] {
  return {
    label_lo: lo,
    label_hi: hi,
    count_lo: 2,
    count_hi: 5,
    name_score: 90,
    cosine_score: 0.9,
    combined_score: 0.9,
  };
}

function renderQueue() {
  render(
    <MemoryRouter initialEntries={["/stories/s1/normalise-names"]}>
      <Routes>
        <Route path="/stories/:storyId/normalise-names" element={<NormaliseNamesQueue />} />
      </Routes>
    </MemoryRouter>,
  );
}

afterEach(() => {
  vi.clearAllMocks();
  h.mode.value = "success";
  h.data.value = null;
  h.undismissFails.value = false;
});

describe("NormaliseNamesQueue", () => {
  it("shows the loading state", () => {
    h.mode.value = "loading";
    renderQueue();
    expect(screen.getByTestId("normalise-loading")).toBeInTheDocument();
  });

  it("shows the error state", () => {
    h.mode.value = "error";
    renderQueue();
    expect(screen.getByTestId("normalise-error")).toBeInTheDocument();
  });

  it("shows the empty state when both vocabularies are empty", () => {
    h.data.value = { predicate_suggestions: [], type_suggestions: [] };
    renderQueue();
    expect(screen.getByTestId("normalise-empty")).toBeInTheDocument();
  });

  it("renders both grouped sections with counts and a back-link", () => {
    h.data.value = {
      predicate_suggestions: [synonym("LOCATED_AT", "LOCATED_IN"), synonym("PART_OF", "MEMBER_OF")],
      type_suggestions: [synonym("Place", "Location")],
    };
    renderQueue();
    expect(screen.getByTestId("normalise-count")).toHaveTextContent("3");
    expect(screen.getByTestId("normalise-section-predicate")).toHaveTextContent("Predicates");
    expect(screen.getByTestId("normalise-section-type")).toHaveTextContent("Types");
    expect(screen.getAllByTestId("pair-stub")).toHaveLength(3);
    expect(screen.getByTestId("graph-link")).toHaveAttribute("href", "/stories/s1/graph");
    // The first pair (predicate) is selected by default.
    expect(screen.getAllByTestId("pair-stub")[0]).toHaveAttribute("data-selected", "true");
  });

  it("moves one continuous J/K cursor across both sections and dismisses with D", () => {
    h.data.value = {
      predicate_suggestions: [synonym("LOCATED_AT", "LOCATED_IN")],
      type_suggestions: [synonym("Place", "Location")],
    };
    renderQueue();

    // J moves from the predicate (index 0) into the type section (index 1).
    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "j" })));
    const stubs = screen.getAllByTestId("pair-stub");
    expect(stubs[1]).toHaveAttribute("data-surface", "type");
    expect(stubs[1]).toHaveAttribute("data-selected", "true");

    act(() => window.dispatchEvent(new KeyboardEvent("keydown", { key: "d" })));
    expect(h.dismissMutate).toHaveBeenCalledWith({
      surface: "type",
      labelA: "Place",
      labelB: "Location",
    });
  });

  it("dismissing shows a transient Undo that reverses the dismissal", () => {
    h.data.value = {
      predicate_suggestions: [synonym("LOCATED_AT", "LOCATED_IN")],
      type_suggestions: [],
    };
    renderQueue();

    fireEvent.click(screen.getByTestId("stub-dismiss"));
    expect(h.dismissMutate).toHaveBeenCalledWith({
      surface: "predicate",
      labelA: "LOCATED_AT",
      labelB: "LOCATED_IN",
    });

    expect(screen.getByTestId("normalise-undo")).toHaveTextContent("LOCATED_AT & LOCATED_IN");

    fireEvent.click(screen.getByTestId("normalise-undo-button"));
    expect(h.undismissMutate).toHaveBeenCalledWith({
      surface: "predicate",
      labelA: "LOCATED_AT",
      labelB: "LOCATED_IN",
    });
    expect(screen.queryByTestId("normalise-undo")).not.toBeInTheDocument();
  });

  it("surfaces a rename summary reported up from a card", () => {
    h.data.value = {
      predicate_suggestions: [synonym("LOCATED_AT", "LOCATED_IN")],
      type_suggestions: [],
    };
    renderQueue();

    fireEvent.click(screen.getByTestId("stub-rename"));
    expect(screen.getByTestId("normalise-renamed")).toHaveTextContent(
      "Renamed 2 edges from “LOCATED_AT” to “LOCATED_IN”.",
    );
  });

  it("surfaces a failed Undo and keeps the banner so it can be retried", () => {
    h.undismissFails.value = true;
    h.data.value = {
      predicate_suggestions: [synonym("LOCATED_AT", "LOCATED_IN")],
      type_suggestions: [],
    };
    renderQueue();

    fireEvent.click(screen.getByTestId("stub-dismiss"));
    fireEvent.click(screen.getByTestId("normalise-undo-button"));

    expect(h.undismissMutate).toHaveBeenCalledWith({
      surface: "predicate",
      labelA: "LOCATED_AT",
      labelB: "LOCATED_IN",
    });
    expect(screen.getByTestId("normalise-undismiss-error")).toBeInTheDocument();
    expect(screen.getByTestId("normalise-undo")).toBeInTheDocument();
  });
});
