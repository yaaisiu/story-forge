// Tests for the change-boundaries mutation hook (Session 48 — M4.S3c-fe2).
//
// Pins: a boundary change POSTs /boundaries with the old + new span; mention_id null materializes
// an auto search hit (the route also suppresses the old position), mention_id set edits a manual
// span in place. On success it invalidates reader + graph + entity-detail prefix.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useChangeBoundaries } from "./useChangeBoundaries";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const PARAGRAPH_ID = "00000000-0000-0000-0000-0000000000p1";
const ENTITY_ID = "00000000-0000-0000-0000-0000000000a1";
const MENTION_ID = "00000000-0000-0000-0000-0000000000c3";

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

describe("useChangeBoundaries", () => {
  it("POSTs a materialize (mention_id null) with old + new span and invalidates the caches", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { mention_id: "m-new" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useChangeBoundaries(STORY_ID, PARAGRAPH_ID), {
      wrapper,
    });
    hook.current.mutate({
      entity_id: ENTITY_ID,
      old_start: 0,
      old_end: 7,
      new_start: 0,
      new_end: 5,
    });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/paragraphs/${PARAGRAPH_ID}/boundaries$`));
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      entity_id: ENTITY_ID,
      old_start: 0,
      old_end: 7,
      new_start: 0,
      new_end: 5,
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: entityDetailStoryKey(STORY_ID) });
  });

  it("POSTs an in-place edit of a manual span (mention_id set)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { mention_id: MENTION_ID }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useChangeBoundaries(STORY_ID, PARAGRAPH_ID), {
      wrapper,
    });
    hook.current.mutate({
      entity_id: ENTITY_ID,
      mention_id: MENTION_ID,
      old_start: 0,
      old_end: 5,
      new_start: 0,
      new_end: 8,
    });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string).mention_id).toBe(MENTION_ID);
  });
});
