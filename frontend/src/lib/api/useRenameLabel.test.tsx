// Tests for the label-rename mutation hook (Session 96 — Graph-quality S6b).
//
// Pins: it POSTs { surface, from_label, to_label } to /label-vocabulary/rename, sending from_label
// VERBATIM (S95 strip-bug guard); it resolves the renamed/folded summary; it invalidates the
// vocabulary list; a failure bubbles as a typed ApiError (404/503).

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./client";
import { entityDetailStoryKey } from "./useEntityDetail";
import { labelVocabularyQueryKey } from "./useLabelVocabulary";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";
import { useRenameLabel } from "./useRenameLabel";

const STORY_ID = "00000000-0000-0000-0000-000000000002";

function buildHarness() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
  return { wrapper, invalidateSpy };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useRenameLabel", () => {
  it("POSTs the rename (from_label verbatim), resolves the summary, and invalidates the list", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(200, { surface: "predicate", renamed_count: 3, folded_count: 1 }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result } = renderHook(() => useRenameLabel(STORY_ID), { wrapper });
    // A from-label with surrounding whitespace must reach the wire untrimmed.
    result.current.mutate({
      surface: "predicate",
      fromLabel: "  LOCATED_AT ",
      toLabel: "LOCATED_IN",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/stories/${STORY_ID}/label-vocabulary/rename`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          surface: "predicate",
          from_label: "  LOCATED_AT ",
          to_label: "LOCATED_IN",
        }),
      },
    );
    expect(result.current.data).toEqual({
      surface: "predicate",
      renamed_count: 3,
      folded_count: 1,
    });
    // The rename wrote the graph, so it invalidates its own list AND the graph-write caches
    // (mirroring useMergeEntities) so the graph/reader/detail views don't serve stale data.
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: labelVocabularyQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: entityDetailStoryKey(STORY_ID) });
  });

  it("surfaces a failure as a typed ApiError", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(503, { detail: "a data store is unavailable" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result } = renderHook(() => useRenameLabel(STORY_ID), { wrapper });
    result.current.mutate({ surface: "type", fromLabel: "Place", toLabel: "Location" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect(result.current.error?.status).toBe(503);
  });
});
