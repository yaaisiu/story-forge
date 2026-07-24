// Tests for the single-story query hook (Grzymalin S3 — story hub).
//
// Pins: GETs /stories/{id} and resolves the typed StorySummary; stays disabled
// (never fetches) until a storyId is known; surfaces a typed ApiError on the
// route's 404 (unknown story). Same fetch-stub + per-test QueryClient approach
// as the other hook tests.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useStory } from "./useStory";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const STORY_ID = "11111111-1111-1111-1111-111111111111";
const STORY_BODY = {
  id: STORY_ID,
  title: "Grzymalin research",
  ingested_at: "2026-06-01T10:00:00Z",
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

describe("useStory", () => {
  it("GETs /stories/{id} and resolves the typed StorySummary", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, STORY_BODY));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStory(STORY_ID), { wrapper: buildWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(STORY_BODY);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}$`));
    expect(init.method).toBe("GET");
  });

  it("does not fetch while the storyId is undefined", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStory(undefined), { wrapper: buildWrapper() });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects with a typed ApiError on 404 (unknown story)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(404, { detail: "story not found" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStory(STORY_ID), { wrapper: buildWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).status).toBe(404);
  });
});
