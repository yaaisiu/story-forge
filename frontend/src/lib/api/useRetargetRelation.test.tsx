// Tests for the retarget-relation mutation hook (Graph-quality S5b-fe).
//
// Pins: a successful retarget PATCHes /stories/{id}/relations/{edgeId} with the changed-
// fields body, returns the new edge id + fold flag, and invalidates the entity-detail prefix
// + the story graph + the reader; a stale edge surfaces as a typed ApiError(404) — the real
// status the PATCH route raises (RelationEdgeNotFound). A fold is a 200 (merged_into_existing),
// not an error.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useRetargetRelation } from "./useRetargetRelation";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const EDGE_ID = "00000000-0000-0000-0000-0000000000ed";
const NEW_EDGE_ID = "00000000-0000-0000-0000-0000000000fe";

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

describe("useRetargetRelation", () => {
  it("PATCHes the changed fields and invalidates entity-detail + graph + reader", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ edge_id: NEW_EDGE_ID, merged_into_existing: false }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useRetargetRelation(STORY_ID, EDGE_ID), { wrapper });
    hook.current.mutate({ predicate: "adores" });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/relations/${EDGE_ID}$`));
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({ predicate: "adores" });

    expect(hook.current.data).toEqual({ edge_id: NEW_EDGE_ID, merged_into_existing: false });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: entityDetailStoryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
  });

  it("surfaces a fold as a 200 with merged_into_existing (not an error)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ edge_id: NEW_EDGE_ID, merged_into_existing: true }), {
        status: 200,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useRetargetRelation(STORY_ID, EDGE_ID), { wrapper });
    hook.current.mutate({ object_id: "00000000-0000-0000-0000-0000000000aa" });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.merged_into_existing).toBe(true);
  });

  it("surfaces a stale/gone edge as a typed ApiError(404)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "relation not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useRetargetRelation(STORY_ID, EDGE_ID), { wrapper });
    hook.current.mutate({ predicate: "adores" });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(404);
  });
});
