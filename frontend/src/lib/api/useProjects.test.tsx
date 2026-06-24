// Tests for the projects-listing query hook (Session 53 — M4 multi-story frontend).
//
// Pins: GETs /projects and resolves the typed ProjectSummary[] (the picker's project
// list); surfaces a typed ApiError on failure. Same fetch-stub + per-test QueryClient
// approach as the other hook tests.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useProjects } from "./useProjects";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const PROJECTS_BODY = [
  {
    id: "00000000-0000-0000-0000-000000000001",
    name: "Oakhaven",
    language: "en",
    created_at: "2026-06-01T10:00:00Z",
    story_count: 2,
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

describe("useProjects", () => {
  it("GETs /projects and resolves the typed ProjectSummary[]", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, PROJECTS_BODY));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useProjects(), { wrapper: buildWrapper() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(PROJECTS_BODY);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/projects$/);
    expect(init.method).toBe("GET");
  });

  it("rejects with a typed ApiError on failure", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(503, { detail: "store unavailable" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useProjects(), { wrapper: buildWrapper() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).status).toBe(503);
  });
});
