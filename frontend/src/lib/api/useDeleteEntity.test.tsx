// Tests for the entity-delete mutation hook (Session 43 — M4.S3b-fe).
//
// Pins (mirroring useRemoveRelation.test.tsx): a successful delete DELETEs
// /stories/{id}/entities/{eid} (→ 204) and invalidates the reader, the story graph, and every
// entity-detail bundle for the story. A stale double-delete (entity already gone, or not in this
// project) surfaces as a typed ApiError(404) — the real status the delete route raises.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useDeleteEntity } from "./useDeleteEntity";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const ENTITY_ID = "00000000-0000-0000-0000-0000000000e1";

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
  return new Response(body === null ? null : JSON.stringify(body), {
    status,
    headers: body === null ? undefined : { "Content-Type": "application/json" },
  });
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("useDeleteEntity", () => {
  it("DELETEs the entity and invalidates reader + graph + detail", async () => {
    const fetchMock = vi.fn().mockResolvedValue(new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useDeleteEntity(STORY_ID), { wrapper });
    hook.current.mutate(ENTITY_ID);

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/entities/${ENTITY_ID}$`));
    expect(init.method).toBe("DELETE");

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: entityDetailStoryKey(STORY_ID) });
  });

  it("surfaces a stale delete as a typed ApiError(404)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(404, { detail: "entity not found" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useDeleteEntity(STORY_ID), { wrapper });
    hook.current.mutate(ENTITY_ID);

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(404);
  });
});
