// Tests for the duplicate-pair card (Session 79 — Graph-quality S4b).
//
// The card is render-and-dispatch over two already-unit-tested network hooks (useEntityDetail,
// useMergeEntities), so those are mocked here to isolate the card's own wiring: honest context +
// scores, the explicit survivor pick that arms the merge, the by-hand conflict resolver, and the
// dismiss dispatch. The pair logic (scoreLabels/mergeVarsFor) is covered in duplicateReview.test.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";

import type { DuplicateSuggestionView } from "../../lib/api/useDuplicateSuggestions";
import { DuplicatePairCard } from "./DuplicatePairCard";

const h = vi.hoisted(() => ({
  mergeMutate: vi.fn(),
  mergeReset: vi.fn(),
  mergeSuccess: { value: false },
  detailMode: { value: "success" as "success" | "loading" | "error" },
  props: {} as Record<string, Record<string, unknown>>,
}));

vi.mock("../../lib/api/useEntityDetail", () => ({
  useEntityDetail: (_storyId?: string, entityId?: string) => {
    if (!entityId) return { data: undefined, isPending: false, isError: false, isSuccess: false };
    if (h.detailMode.value === "loading")
      return { data: undefined, isPending: true, isError: false, isSuccess: false };
    if (h.detailMode.value === "error")
      return { data: undefined, isPending: false, isError: true, isSuccess: false };
    return {
      data: { properties: h.props[entityId] ?? {} },
      isPending: false,
      isError: false,
      isSuccess: true,
    };
  },
}));

vi.mock("../../lib/api/useMergeEntities", () => ({
  useMergeEntities: () => ({
    mutate: h.mergeMutate,
    reset: h.mergeReset,
    isPending: false,
    isError: false,
    isSuccess: h.mergeSuccess.value,
    error: null,
  }),
}));

function suggestion(overrides: Partial<DuplicateSuggestionView> = {}): DuplicateSuggestionView {
  return {
    entity_a: {
      entity_id: "a-id",
      canonical_name: "Elara",
      type: "Person",
      aliases: ["El"],
      context_quote: "Elara stepped forward.",
    },
    entity_b: {
      entity_id: "b-id",
      canonical_name: "Elira",
      type: "Person",
      aliases: [],
      context_quote: null,
    },
    name_score: 88,
    cosine_score: 0.912,
    combined_score: 0.9,
    ...overrides,
  };
}

function renderCard(props: Partial<Parameters<typeof DuplicatePairCard>[0]> = {}) {
  const queryClient = new QueryClient();
  const onSelect = vi.fn();
  const onDismiss = vi.fn();
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  render(
    <DuplicatePairCard
      storyId="s1"
      suggestion={suggestion()}
      isSelected={false}
      onSelect={onSelect}
      onDismiss={onDismiss}
      {...props}
    />,
    { wrapper },
  );
  return { onSelect, onDismiss };
}

afterEach(() => {
  vi.clearAllMocks();
  h.detailMode.value = "success";
  h.mergeSuccess.value = false;
  h.props = {};
});

describe("DuplicatePairCard", () => {
  it("renders both sides' identity, quote, and the honest pair scores", () => {
    renderCard();
    const names = screen.getAllByTestId("duplicate-side-name").map((n) => n.textContent);
    expect(names).toEqual(["Elara", "Elira"]);
    const identities = screen.getAllByTestId("duplicate-side-identity").map((n) => n.textContent);
    expect(identities[0]).toContain("aka El");
    expect(screen.getByText("Elara stepped forward.", { exact: false })).toBeInTheDocument();
    // Only side A has a quote (side B's is null).
    expect(screen.getAllByTestId("duplicate-side-quote")).toHaveLength(1);
    expect(screen.getByTestId("duplicate-scores").textContent).toBe(
      "name match 88 · embedding 0.91",
    );
  });

  it("labels a name-only pair when the cosine score is null", () => {
    renderCard({ suggestion: suggestion({ cosine_score: null }) });
    expect(screen.getByTestId("duplicate-scores").textContent).toBe("name match 88 · name-only");
  });

  it("gates the merge behind an explicit survivor pick", () => {
    renderCard();
    expect(screen.getByTestId("duplicate-merge-confirm")).toBeDisabled();

    fireEvent.click(screen.getByTestId("duplicate-keep-a"));
    // Picking a survivor highlights that side and enables the merge (details resolve in the mock).
    expect(screen.getAllByTestId("duplicate-side")[0]).toHaveAttribute("data-active", "true");
    expect(screen.getByTestId("duplicate-merge-confirm")).toBeEnabled();
  });

  it("merges keeping the picked survivor, defaulting an unresolved conflict to the survivor", () => {
    h.props = { "a-id": { age: 40 }, "b-id": { age: 42 } };
    renderCard();
    fireEvent.click(screen.getByTestId("duplicate-keep-a"));

    // The age conflict surfaces; the author leaves it at the survivor's value.
    expect(screen.getByTestId("merge-conflicts")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("duplicate-merge-confirm"));

    expect(h.mergeMutate).toHaveBeenCalledWith(
      { targetEntityId: "a-id", absorbedId: "b-id", resolvedProperties: { age: 40 } },
      expect.anything(),
    );
  });

  it("carries a resolved conflict choice into the merge", () => {
    h.props = { "a-id": { age: 40 }, "b-id": { age: 42 } };
    renderCard();
    fireEvent.click(screen.getByTestId("duplicate-keep-a"));
    fireEvent.click(screen.getByTestId("merge-keep-absorbed"));
    fireEvent.click(screen.getByTestId("duplicate-merge-confirm"));

    expect(h.mergeMutate).toHaveBeenCalledWith(
      expect.objectContaining({ resolvedProperties: { age: 42 } }),
      expect.anything(),
    );
  });

  it("shows a details-loading and a details-error state under the survivor pick", () => {
    h.detailMode.value = "loading";
    const { onDismiss } = renderCard();
    fireEvent.click(screen.getByTestId("duplicate-keep-b"));
    expect(screen.getByTestId("duplicate-details-loading")).toBeInTheDocument();
    expect(screen.getByTestId("duplicate-merge-confirm")).toBeDisabled();

    // Dismiss stays available regardless of the merge sub-form.
    fireEvent.click(screen.getByTestId("duplicate-dismiss"));
    expect(onDismiss).toHaveBeenCalledTimes(1);
  });

  it("surfaces a details-error when a detail read fails and the merge has not succeeded", () => {
    h.detailMode.value = "error";
    renderCard();
    fireEvent.click(screen.getByTestId("duplicate-keep-a"));
    expect(screen.getByTestId("duplicate-details-error")).toBeInTheDocument();
  });

  it("suppresses the details-error once the merge has succeeded (no happy-path flash)", () => {
    // After merge success useMergeEntities invalidates entity-detail, so the deleted absorbed
    // entity refetches and 404s in the gap before the card unmounts — that must not flash an error.
    h.detailMode.value = "error";
    h.mergeSuccess.value = true;
    renderCard();
    fireEvent.click(screen.getByTestId("duplicate-keep-a"));
    expect(screen.queryByTestId("duplicate-details-error")).not.toBeInTheDocument();
  });
});
