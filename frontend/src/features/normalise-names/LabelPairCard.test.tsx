// Tests for the label-pair card (Session 96 — Graph-quality S6b).
//
// The card is render-and-dispatch over the useRenameLabel hook, which is mocked here to isolate the
// card's own wiring: honest scores + counts, the arm-then-confirm rename that sends from_label
// verbatim, the reported summary, and the dismiss dispatch. The pair logic (scoreLabels/armRename/
// hints) is covered in normaliseNames.test.

import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import { LabelPairCard } from "./LabelPairCard";
import type { LabelPairItem } from "./normaliseNames";

const h = vi.hoisted(() => ({
  renameMutate: vi.fn(),
  renameReset: vi.fn(),
  renameError: { value: null as { detail: string } | null },
  renamePending: { value: false },
}));

vi.mock("../../lib/api/useRenameLabel", () => ({
  useRenameLabel: () => ({
    mutate: h.renameMutate,
    reset: h.renameReset,
    isPending: h.renamePending.value,
    isError: h.renameError.value !== null,
    error: h.renameError.value,
  }),
}));

function item(overrides: Partial<LabelPairItem["pair"]> = {}): LabelPairItem {
  return {
    surface: "predicate",
    pair: {
      label_lo: "  LOCATED_AT ",
      label_hi: "LOCATED_IN",
      count_lo: 3,
      count_hi: 12,
      name_score: 91,
      cosine_score: 0.88,
      combined_score: 0.9,
      ...overrides,
    },
  };
}

function renderCard(over: Partial<Parameters<typeof LabelPairCard>[0]> = {}) {
  const onRenamed = vi.fn();
  const onDismiss = vi.fn();
  const onSelect = vi.fn();
  render(
    <LabelPairCard
      storyId="s-1"
      item={item()}
      isSelected={false}
      onSelect={onSelect}
      onRenamed={onRenamed}
      onDismiss={onDismiss}
      {...over}
    />,
  );
  return { onRenamed, onDismiss, onSelect };
}

afterEach(() => {
  vi.clearAllMocks();
  h.renameError.value = null;
  h.renamePending.value = false;
});

describe("LabelPairCard", () => {
  it("renders both labels with counts, the surface, and honest scores", () => {
    renderCard();
    expect(screen.getByText("LOCATED_IN")).toBeInTheDocument();
    expect(screen.getByTestId("label-surface")).toHaveTextContent("predicate");
    expect(screen.getByTestId("label-scores")).toHaveTextContent("name match 91 · embedding 0.88");
  });

  it("arms a direction on pick, showing the fold hint and highlighting the kept side", () => {
    renderCard();
    // Keep LOCATED_IN → fold the 3 LOCATED_AT edges into it. (toHaveTextContent collapses runs of
    // whitespace, so we assert the stable parts; the verbatim from_label is pinned on the mutate arg
    // in the commit test below.)
    fireEvent.click(screen.getByText("LOCATED_IN"));
    expect(screen.getByTestId("rename-hint")).toHaveTextContent(
      /Rename 3 edges from “ ?LOCATED_AT ” to “LOCATED_IN”\. Nothing happens until you press Rename\./,
    );
    const kept = screen.getByText("LOCATED_IN").closest("[data-testid='label-keep']");
    expect(kept).toHaveAttribute("data-active", "true");
  });

  it("Rename is disabled until a direction is armed", () => {
    renderCard();
    expect(screen.getByTestId("rename-confirm")).toBeDisabled();
    fireEvent.click(screen.getByText("LOCATED_IN"));
    expect(screen.getByTestId("rename-confirm")).toBeEnabled();
  });

  it("commits the rename sending from_label VERBATIM (the untrimmed stored label)", () => {
    renderCard();
    fireEvent.click(screen.getByText("LOCATED_IN"));
    fireEvent.click(screen.getByTestId("rename-confirm"));
    expect(h.renameMutate).toHaveBeenCalledTimes(1);
    expect(h.renameMutate.mock.calls[0]?.[0]).toEqual({
      surface: "predicate",
      fromLabel: "  LOCATED_AT ",
      toLabel: "LOCATED_IN",
    });
  });

  it("reports the rename summary up to the queue on success", () => {
    const summary = { surface: "predicate", renamed_count: 3, folded_count: 1 };
    h.renameMutate.mockImplementation((_vars, opts) => opts?.onSuccess?.(summary));
    const { onRenamed } = renderCard();
    fireEvent.click(screen.getByText("LOCATED_IN"));
    fireEvent.click(screen.getByTestId("rename-confirm"));
    expect(onRenamed).toHaveBeenCalledWith({
      summary,
      fromLabel: "  LOCATED_AT ",
      toLabel: "LOCATED_IN",
    });
  });

  it("dispatches dismiss and surfaces a rename error", () => {
    h.renameError.value = { detail: "a data store is unavailable" };
    const { onDismiss } = renderCard();
    fireEvent.click(screen.getByTestId("label-dismiss"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
    expect(screen.getByTestId("rename-error")).toHaveTextContent("a data store is unavailable");
  });
});
