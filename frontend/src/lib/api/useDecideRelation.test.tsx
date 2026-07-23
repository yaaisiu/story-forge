// Tests for the relation-decision mutation hook (Session 30 — M3.S4f).
//
// Pins (mirroring useReviewCandidate.test.tsx): a commit POSTs
// /relations/{id}/decide with {action:"commit"} and invalidates BOTH the queue (so the
// decided relation drops off), the story graph (so the new edge appears in the §3.4
// viewer) and the reader (whose §3.5 tooltip summary is derived from the project's edges);
// a reject POSTs {action:"reject"} and invalidates ONLY the queue, never the graph or the
// reader (a reject writes no edge); a 409 stale-endpoint surfaces as a typed ApiError.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useDecideRelation } from "./useDecideRelation";
import { readerQueryKey } from "./useReader";
import { relationsQueryKey } from "./useRelations";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const RELATION_ID = "00000000-0000-0000-0000-0000000000a1";

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

describe("useDecideRelation", () => {
  it("commit POSTs {action:commit} and invalidates queue + graph + reader", async () => {
    const decision = {
      relation_id: RELATION_ID,
      status: "written",
      edge_id: "00000000-0000-0000-0000-0000000000ed",
      already_decided: false,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, decision));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useDecideRelation(STORY_ID), { wrapper });
    hook.current.mutate({ relationId: RELATION_ID, action: "commit" });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.status).toBe("written");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/relations/${RELATION_ID}/decide$`));
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({ action: "commit" });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: relationsQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    // The reader's tooltip summary reads the project's edges (S7), so a commit dirties it too.
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
  });

  it("reject POSTs {action:reject} and refreshes only the queue, not the graph or reader", async () => {
    const decision = {
      relation_id: RELATION_ID,
      status: "rejected",
      edge_id: null,
      already_decided: false,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, decision));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useDecideRelation(STORY_ID), { wrapper });
    hook.current.mutate({ relationId: RELATION_ID, action: "reject" });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.status).toBe("rejected");

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ action: "reject" });

    // A reject writes no edge — only the queue needs refreshing.
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: relationsQueryKey(STORY_ID) });
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
  });

  it("rejects with a typed ApiError on 409 (stale endpoint)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(409, { detail: "a relation endpoint no longer resolves (stale/held)" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useDecideRelation(STORY_ID), { wrapper });
    hook.current.mutate({ relationId: RELATION_ID, action: "commit" });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(409);
  });
});
