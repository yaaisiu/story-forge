// Tests for the manual-tag mutation hook (Session 48 — M4.S3c-fe2).
//
// Pins: a tag POSTs /stories/{id}/paragraphs/{pid}/tags and invalidates reader + graph +
// entity-detail prefix; the two tag shapes ride through verbatim (existing entity carries
// `entity_id`, new entity carries `new_entity` {name, type}); a bad span surfaces as a typed
// ApiError(400) — the real status the route raises (SpanInvalid).

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useTagOccurrence } from "./useTagOccurrence";
import { entityDetailStoryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const PARAGRAPH_ID = "00000000-0000-0000-0000-0000000000p1";
const ENTITY_ID = "00000000-0000-0000-0000-0000000000a1";

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

describe("useTagOccurrence", () => {
  it("POSTs a tag for an existing entity and invalidates reader + graph + entity-detail", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { mention_id: "m1", entity_id: ENTITY_ID }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useTagOccurrence(STORY_ID, PARAGRAPH_ID), {
      wrapper,
    });
    hook.current.mutate({ span_start: 0, span_end: 5, entity_id: ENTITY_ID });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/paragraphs/${PARAGRAPH_ID}/tags$`));
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toEqual({
      span_start: 0,
      span_end: 5,
      entity_id: ENTITY_ID,
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: entityDetailStoryKey(STORY_ID) });
  });

  it("POSTs a tag that creates a new entity (name + open-world type)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(200, { mention_id: "m2", entity_id: "e-new" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useTagOccurrence(STORY_ID, PARAGRAPH_ID), {
      wrapper,
    });
    hook.current.mutate({
      span_start: 4,
      span_end: 9,
      new_entity: { name: "Janek", type: "ghost" },
    });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));

    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({
      span_start: 4,
      span_end: 9,
      new_entity: { name: "Janek", type: "ghost" },
    });
  });

  it("surfaces a bad span as a typed ApiError(400)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(400, { detail: "span [0, 0) is empty or reversed" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useTagOccurrence(STORY_ID, PARAGRAPH_ID), {
      wrapper,
    });
    hook.current.mutate({ span_start: 0, span_end: 0, entity_id: ENTITY_ID });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(400);
  });
});
