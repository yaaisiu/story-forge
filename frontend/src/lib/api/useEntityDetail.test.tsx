// Tests for the entity-detail query hook (Session 35 — M4.S2b, spec §3.4/§3.5).
//
// Pins: GETs /stories/{id}/entities/{eid} and resolves the typed EntityDetailResponse;
// stays disabled (never fetches) until both ids are known; surfaces a typed ApiError on
// 404. Same fetch-stub + per-test QueryClient approach as the other hook tests.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useEntityDetail } from "./useEntityDetail";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const ENTITY_ID = "11111111-1111-1111-1111-111111111111";
const DETAIL_BODY = {
  entity_id: ENTITY_ID,
  canonical_name: "Elara",
  type: "character",
  aliases: ["the seer"],
  properties: { age: "30" },
  ego_graph: { neighbours: [], edges: [] },
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

describe("useEntityDetail", () => {
  it("GETs /stories/{id}/entities/{eid} and resolves the typed EntityDetailResponse", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, DETAIL_BODY));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntityDetail(STORY_ID, ENTITY_ID), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(DETAIL_BODY);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/entities/${ENTITY_ID}$`));
    expect(init.method).toBe("GET");
  });

  it("does not fetch while the entityId is undefined", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntityDetail(STORY_ID, undefined), {
      wrapper: buildWrapper(),
    });

    expect(result.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects with a typed ApiError on 404", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(404, { detail: "entity not found" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useEntityDetail(STORY_ID, ENTITY_ID), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).status).toBe(404);
  });
});
