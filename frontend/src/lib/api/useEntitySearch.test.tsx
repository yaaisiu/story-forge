// Tests for the manual-handpick entity-search hook (M3.S4d).
//
// Pins: GETs /stories/{id}/entities?q=<query> and resolves ranked hits on 200; stays
// disabled (never fetches) while the story id OR the query is empty/blank — so it never
// fires with `undefined` in the path nor searches on an empty box; url-encodes the query;
// surfaces a 404 (unknown story) as a typed ApiError.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useEntitySearch } from "./useEntitySearch";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const STORY_ID = "00000000-0000-0000-0000-000000000002";

function hit(over: Record<string, unknown> = {}) {
  return {
    entity_id: "00000000-0000-0000-0000-0000000000e1",
    canonical_name: "Jan",
    type: "Character",
    score: 90,
    aliases: ["Janek"],
    ...over,
  };
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

describe("useEntitySearch", () => {
  it("GETs /stories/{id}/entities?q=<query> and resolves ranked hits on 200", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { entities: [hit()] }));
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useEntitySearch(STORY_ID, "Jan"), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.entities).toHaveLength(1);
    expect(hook.current.data?.entities[0]?.canonical_name).toBe("Jan");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/entities\\?q=Jan$`));
    expect(init.method).toBe("GET");
  });

  it("url-encodes the query", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { entities: [] }));
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useEntitySearch(STORY_ID, "Jan Kowalski"), { wrapper: buildWrapper() });

    await waitFor(() => expect(fetchMock).toHaveBeenCalled());
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toMatch(/\?q=Jan%20Kowalski$/);
  });

  it("stays disabled and never fetches while the query is blank", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useEntitySearch(STORY_ID, "   "), {
      wrapper: buildWrapper(),
    });

    expect(hook.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("stays disabled and never fetches while the story id is undefined", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useEntitySearch(undefined, "Jan"), {
      wrapper: buildWrapper(),
    });

    expect(hook.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects with a typed ApiError on 404 (unknown story)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(404, { detail: "story not found" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useEntitySearch(STORY_ID, "Jan"), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(404);
  });
});
