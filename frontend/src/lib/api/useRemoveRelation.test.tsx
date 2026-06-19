// Tests for the remove-relation mutation hook (Session 38 — M4.S3a-fe).
//
// Pins: a successful remove DELETEs /stories/{id}/relations/{edgeId}, tolerates the 204
// No-Content (empty body, no parse error), and invalidates the entity-detail prefix + the
// story graph + the reader; a stale double-remove surfaces as a typed ApiError(404) — the
// real status the DELETE route raises (RelationEdgeNotFound).

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useRemoveRelation } from "./useRemoveRelation";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const EDGE_ID = "00000000-0000-0000-0000-0000000000ed";

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

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useRemoveRelation", () => {
  it("DELETEs the edge (204 no body) and invalidates entity-detail + graph + reader", async () => {
    // 204 No Content — an empty body the hook must not try to JSON-parse.
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useRemoveRelation(STORY_ID), { wrapper });
    hook.current.mutate(EDGE_ID);

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/relations/${EDGE_ID}$`));
    expect(init.method).toBe("DELETE");

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["entity-detail", STORY_ID] });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
  });

  it("surfaces a stale double-remove as a typed ApiError(404)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "relation not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useRemoveRelation(STORY_ID), { wrapper });
    hook.current.mutate(EDGE_ID);

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(404);
  });
});
