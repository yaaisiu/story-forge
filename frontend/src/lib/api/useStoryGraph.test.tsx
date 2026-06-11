// Tests for the story-graph query hook (Session 17 — M2.S5).
//
// Pins: GETs /stories/{id}/graph and resolves the typed GraphResponse; stays
// disabled (never fetches) without a storyId; surfaces a typed ApiError on 404.
// Same fetch-stub + per-test QueryClient approach as the other hook tests.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useStoryGraph } from "./useStoryGraph";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const GRAPH_BODY = {
  nodes: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      type: "Character",
      canonical_name_pl: "Janek",
      canonical_name_en: null,
      aliases: ["Janek z młyna"],
      first_seen_paragraph_id: "22222222-2222-2222-2222-222222222222",
    },
  ],
  edges: [],
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

describe("useStoryGraph", () => {
  it("GETs /stories/{id}/graph and resolves the typed GraphResponse", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, GRAPH_BODY));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStoryGraph(STORY_ID), { wrapper: buildWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(GRAPH_BODY);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/graph$`));
    expect(init.method).toBe("GET");
  });

  it("does not fetch while the storyId is undefined", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStoryGraph(undefined), { wrapper: buildWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects with a typed ApiError on 404", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(404, { detail: "story not found" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStoryGraph(STORY_ID), { wrapper: buildWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).status).toBe(404);
  });
});
