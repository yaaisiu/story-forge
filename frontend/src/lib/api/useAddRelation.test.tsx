// Tests for the add-relation mutation hook (Session 38 — M4.S3a-fe).
//
// Pins: a successful add POSTs /stories/{id}/relations with {subject_id, predicate, object_id}
// and invalidates the entity-detail prefix (both endpoints' panels) + the story graph + the
// reader; the `merged_into_existing` flag rides through on the response (the UI warns on it);
// an unknown endpoint entity surfaces as a typed ApiError(404) — the real status the POST route
// raises (EntityNotFound), not a 409.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useAddRelation } from "./useAddRelation";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const SUBJECT_ID = "00000000-0000-0000-0000-0000000000a1";
const OBJECT_ID = "00000000-0000-0000-0000-0000000000b2";

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

describe("useAddRelation", () => {
  it("POSTs the triple and invalidates entity-detail + graph + reader", async () => {
    const edge = {
      edge_id: "00000000-0000-0000-0000-0000000000ed",
      merged_into_existing: true,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, edge));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useAddRelation(STORY_ID), { wrapper });
    hook.current.mutate({ subject_id: SUBJECT_ID, predicate: "loves", object_id: OBJECT_ID });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    // The collision flag rides through so the panel can warn the author.
    expect(hook.current.data?.merged_into_existing).toBe(true);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/relations$`));
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      subject_id: SUBJECT_ID,
      predicate: "loves",
      object_id: OBJECT_ID,
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: entityDetailStoryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
  });

  it("surfaces an unknown endpoint entity as a typed ApiError(404)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(404, { detail: "an endpoint entity not found" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useAddRelation(STORY_ID), { wrapper });
    hook.current.mutate({ subject_id: SUBJECT_ID, predicate: "loves", object_id: OBJECT_ID });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(404);
  });
});
