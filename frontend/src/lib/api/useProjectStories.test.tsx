// Tests for the project-stories query hook (Session 53 — M4 multi-story frontend).
//
// Pins: GETs /projects/{id}/stories and resolves the typed StorySummary[]; stays
// disabled (never fetches) until a projectId is known; surfaces a typed ApiError on
// the route's 404 (unknown project). Same fetch-stub + per-test QueryClient approach
// as the other hook tests.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useProjectStories } from "./useProjectStories";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const PROJECT_ID = "00000000-0000-0000-0000-000000000001";
const STORIES_BODY = [
  {
    id: "11111111-1111-1111-1111-111111111111",
    title: "Chapter one",
    ingested_at: "2026-06-01T10:00:00Z",
  },
];

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

describe("useProjectStories", () => {
  it("GETs /projects/{id}/stories and resolves the typed StorySummary[]", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, STORIES_BODY));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useProjectStories(PROJECT_ID), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(STORIES_BODY);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/projects/${PROJECT_ID}/stories$`));
    expect(init.method).toBe("GET");
  });

  it("does not fetch while the projectId is undefined", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useProjectStories(undefined), {
      wrapper: buildWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects with a typed ApiError on 404 (unknown project)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(404, { detail: "project not found" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useProjectStories(PROJECT_ID), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).status).toBe(404);
  });
});
