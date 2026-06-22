// Tests for the undo mutation hook (Session 43 — M4.S3b-fe, DM-S3b-1 see-what-I-undo).
//
// Undo is story-scoped: POST /stories/{id}/graph-edits/undo reverses the LAST graph edit anywhere
// in the story. With `?preview=true` the backend reports what *would* be reversed without touching
// the graph (applied=false) — so a preview must NOT invalidate any query. A real undo (applied=true)
// invalidates the reader, the story graph, and every entity-detail bundle. Nothing left to undo
// 404s; the graph drifted since 409s — each a typed ApiError, statuses read off api/stories.py.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useUndo } from "./useUndo";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";

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

describe("useUndo", () => {
  it("previews with ?preview=true and does NOT invalidate", async () => {
    const preview = {
      description: "merged Broniek into Bronisław",
      op_kind: "merge",
      applied: false,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, preview));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useUndo(STORY_ID), { wrapper });
    hook.current.mutate(true);

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.applied).toBe(false);
    expect(hook.current.data?.description).toBe("merged Broniek into Bronisław");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/graph-edits/undo\\?preview=true$`));
    expect(init.method).toBe("POST");
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it("applies (no preview param) and invalidates reader + graph + detail", async () => {
    const applied = { description: "deleted Oakhaven", op_kind: "delete_entity", applied: true };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, applied));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useUndo(STORY_ID), { wrapper });
    hook.current.mutate(false);

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/graph-edits/undo$`));

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: entityDetailStoryKey(STORY_ID) });
  });

  it("surfaces nothing-to-undo as a typed ApiError(404)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(404, { detail: "nothing to undo" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useUndo(STORY_ID), { wrapper });
    hook.current.mutate(false);

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect((hook.current.error as ApiError).status).toBe(404);
  });

  it("surfaces drift as a typed ApiError(409)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(409, { detail: "the graph drifted" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useUndo(STORY_ID), { wrapper });
    hook.current.mutate(false);

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect((hook.current.error as ApiError).status).toBe(409);
  });
});
