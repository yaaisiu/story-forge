// Tests for the entity-merge mutation hook (Session 43 — M4.S3b-fe).
//
// Pins (mirroring useEntityEdit.test.tsx): a successful merge POSTs
// /stories/{id}/entities/{absorbedId}/merge with {target_entity_id, resolved_properties} and
// invalidates the reader, the story graph, AND every entity-detail bundle for the story (both
// endpoints' panels via the prefix key). An unresolved property conflict surfaces as a typed
// ApiError(400) — the real status the merge route raises (EntityMergeInvalid → 400).

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useMergeEntities } from "./useMergeEntities";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const SURVIVOR_ID = "00000000-0000-0000-0000-0000000000a1";
const ABSORBED_ID = "00000000-0000-0000-0000-0000000000b2";

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

describe("useMergeEntities", () => {
  it("POSTs the merge to the absorbed entity's URL and invalidates reader + graph + detail", async () => {
    const summary = {
      survivor_entity_id: SURVIVOR_ID,
      repointed_count: 3,
      folded_count: 1,
      self_loops_dropped: 0,
      mentions_repointed: 4,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, summary));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useMergeEntities(STORY_ID), { wrapper });
    hook.current.mutate({
      absorbedId: ABSORBED_ID,
      targetEntityId: SURVIVOR_ID,
      resolvedProperties: { age: 40 },
    });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.repointed_count).toBe(3);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/entities/${ABSORBED_ID}/merge$`));
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      target_entity_id: SURVIVOR_ID,
      resolved_properties: { age: 40 },
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: entityDetailStoryKey(STORY_ID) });
  });

  it("surfaces an unresolved property conflict as a typed ApiError(400)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(400, { detail: "unresolved property conflicts: ['age']" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useMergeEntities(STORY_ID), { wrapper });
    hook.current.mutate({
      absorbedId: ABSORBED_ID,
      targetEntityId: SURVIVOR_ID,
      resolvedProperties: {},
    });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(400);
  });
});
