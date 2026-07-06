// Tests for the edge-evidence query hook (Session 76 — Graph-quality S3b, DM-EE-1/2).
//
// Pins: GETs /stories/{id}/relations/{edge_id}/evidence and resolves the typed
// EdgeEvidence; stays disabled (never fetches) until both ids are known; surfaces a
// typed ApiError on 404. Same fetch-stub + per-test QueryClient approach as the other
// hook tests (mirrors useEntityDetail.test.tsx).

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useEdgeEvidence } from "./useEdgeEvidence";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const EDGE_ID = "33333333-3333-3333-3333-333333333333";
const EVIDENCE_BODY = {
  predicate: "TRAVELS_WITH",
  source_provenance: [
    {
      paragraph_id: "44444444-4444-4444-4444-444444444444",
      paragraph_text: "Janek and Katarzyna left the mill together at dawn.",
      evidence_quote: "left the mill together",
    },
  ],
};

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

describe("useEdgeEvidence", () => {
  it("GETs /stories/{id}/relations/{edge_id}/evidence and resolves the typed EdgeEvidence", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, EVIDENCE_BODY));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEdgeEvidence(STORY_ID, EDGE_ID), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(EVIDENCE_BODY);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/relations/${EDGE_ID}/evidence$`));
    expect(init.method).toBe("GET");
  });

  it("resolves an empty provenance list (a manually-added edge) as success, not an error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { predicate: "KNOWS", source_provenance: [] }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEdgeEvidence(STORY_ID, EDGE_ID), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.source_provenance).toEqual([]);
  });

  it("does not fetch while the edgeId is undefined", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEdgeEvidence(STORY_ID, undefined), {
      wrapper: buildWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects with a typed ApiError on 404", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(404, { detail: "Story not found." }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEdgeEvidence(STORY_ID, EDGE_ID), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).status).toBe(404);
  });
});
