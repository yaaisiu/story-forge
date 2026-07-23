// Tests for the label dismiss / un-dismiss mutation hooks (Session 96 — Graph-quality S6b).
//
// Pins: dismiss POSTs the surface + pair to /label-vocabulary/dismiss; un-dismiss DELETEs the same
// route WITH a JSON body (the DM-NN-3 reversal); both invalidate the vocabulary list. Both reply 204.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { labelVocabularyQueryKey } from "./useLabelVocabulary";
import { useDismissLabel, useUndismissLabel } from "./useDismissLabel";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const PAIR = { surface: "predicate" as const, labelA: "LOCATED_AT", labelB: "LOCATED_IN" };

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

function emptyResponse(status: number): Response {
  return new Response(null, { status });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useDismissLabel", () => {
  it("POSTs the surface + pair and invalidates the vocabulary list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(emptyResponse(204));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result } = renderHook(() => useDismissLabel(STORY_ID), { wrapper });
    result.current.mutate(PAIR);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/stories/${STORY_ID}/label-vocabulary/dismiss`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          surface: "predicate",
          label_a: "LOCATED_AT",
          label_b: "LOCATED_IN",
        }),
      },
    );
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: labelVocabularyQueryKey(STORY_ID) });
  });
});

describe("useUndismissLabel", () => {
  it("DELETEs the surface + pair (with a JSON body) and invalidates the vocabulary list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(emptyResponse(204));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result } = renderHook(() => useUndismissLabel(STORY_ID), { wrapper });
    result.current.mutate(PAIR);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/stories/${STORY_ID}/label-vocabulary/dismiss`,
      {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          surface: "predicate",
          label_a: "LOCATED_AT",
          label_b: "LOCATED_IN",
        }),
      },
    );
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: labelVocabularyQueryKey(STORY_ID) });
  });
});
