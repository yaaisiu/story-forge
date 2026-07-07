// Tests for the duplicate dismiss / un-dismiss mutation hooks (Session 79 — Graph-quality S4b).
//
// Pins: dismiss POSTs the pair to /duplicate-suggestions/dismiss; un-dismiss DELETEs the same
// route WITH a JSON body (the DM-CD-3 reversal); both invalidate the suggestions list so the
// row drops / reappears. Both routes reply 204 (no body).

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { duplicateSuggestionsQueryKey } from "./useDuplicateSuggestions";
import { useDismissDuplicate, useUndismissDuplicate } from "./useDismissDuplicate";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const PAIR = { entityIdA: "a-id", entityIdB: "b-id" };

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

describe("useDismissDuplicate", () => {
  it("POSTs the pair to the dismiss route and invalidates the suggestions list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(emptyResponse(204));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result } = renderHook(() => useDismissDuplicate(STORY_ID), { wrapper });
    result.current.mutate(PAIR);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/stories/${STORY_ID}/duplicate-suggestions/dismiss`,
      {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entity_id_a: "a-id", entity_id_b: "b-id" }),
      },
    );
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: duplicateSuggestionsQueryKey(STORY_ID),
    });
  });
});

describe("useUndismissDuplicate", () => {
  it("DELETEs the pair (with a JSON body) and invalidates the suggestions list", async () => {
    const fetchMock = vi.fn().mockResolvedValue(emptyResponse(204));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result } = renderHook(() => useUndismissDuplicate(STORY_ID), { wrapper });
    result.current.mutate(PAIR);

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/stories/${STORY_ID}/duplicate-suggestions/dismiss`,
      {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ entity_id_a: "a-id", entity_id_b: "b-id" }),
      },
    );
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: duplicateSuggestionsQueryKey(STORY_ID),
    });
  });
});
