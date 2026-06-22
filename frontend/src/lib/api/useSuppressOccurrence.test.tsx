// Tests for the suppress / re-assign mutation hook (Session 48 — M4.S3c-fe2).
//
// Pins ADR 0008 §4 — *both* rejections POST /suppressions (never a DELETE): "not an entity"
// sends entity_id null (clear all claimants), "not this entity" sends entity_id set (clear one),
// a re-assign adds retag_to. On success it invalidates reader + graph + entity-detail prefix.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { useSuppressOccurrence } from "./useSuppressOccurrence";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const PARAGRAPH_ID = "00000000-0000-0000-0000-0000000000p1";
const ENTITY_ID = "00000000-0000-0000-0000-0000000000a1";
const RETAG_ID = "00000000-0000-0000-0000-0000000000b2";

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

describe("useSuppressOccurrence", () => {
  it('POSTs "not an entity" (entity_id null) to /suppressions and invalidates the caches', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { suppression_id: "s1" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useSuppressOccurrence(STORY_ID, PARAGRAPH_ID), {
      wrapper,
    });
    hook.current.mutate({ span_start: 0, span_end: 5 });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(
      new RegExp(`/stories/${STORY_ID}/paragraphs/${PARAGRAPH_ID}/suppressions$`),
    );
    expect(init.method).toBe("POST"); // ADR 0008 §4 — a rejection is a suppression, never a DELETE
    expect(JSON.parse(init.body as string)).toEqual({ span_start: 0, span_end: 5 });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: entityDetailStoryKey(STORY_ID) });
  });

  it('POSTs "not this entity" (entity_id set) to /suppressions', async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { suppression_id: "s2" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useSuppressOccurrence(STORY_ID, PARAGRAPH_ID), {
      wrapper,
    });
    hook.current.mutate({ span_start: 0, span_end: 5, entity_id: ENTITY_ID });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      span_start: 0,
      span_end: 5,
      entity_id: ENTITY_ID,
    });
  });

  it("POSTs an atomic re-assign (entity_id + retag_to) and returns the new mention id", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { suppression_id: "s3", mention_id: "m9" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useSuppressOccurrence(STORY_ID, PARAGRAPH_ID), {
      wrapper,
    });
    hook.current.mutate({ span_start: 0, span_end: 5, entity_id: ENTITY_ID, retag_to: RETAG_ID });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.mention_id).toBe("m9");
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      span_start: 0,
      span_end: 5,
      entity_id: ENTITY_ID,
      retag_to: RETAG_ID,
    });
  });
});
