// Tests for the extraction mutation hook (Session 17 — M2.S5).
//
// Pins: POSTs /stories/{id}/extract; a 200 resolves to the finished result; a 202
// also resolves (budget/quota pause is success-with-paused, not an error — OQ-2);
// a 502 rejects with a typed ApiError.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useExtractStory } from "./useExtractStory";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const STORY_ID = "00000000-0000-0000-0000-000000000002";

function result(over: Record<string, unknown> = {}) {
  return {
    story_id: STORY_ID,
    paragraphs_total: 3,
    paragraphs_done: 3,
    entities_written: 5,
    relations_written: 2,
    paused: false,
    pause_reason: null,
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

describe("useExtractStory", () => {
  it("POSTs /stories/{id}/extract and resolves the finished result on 200", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, result()));
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useExtractStory(), { wrapper: buildWrapper() });
    hook.current.mutate({ storyId: STORY_ID });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.paused).toBe(false);
    expect(hook.current.data?.entities_written).toBe(5);

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/extract$`));
    expect(init.method).toBe("POST");
  });

  it("treats a 202 pause as success carrying paused + partial progress", async () => {
    const body = result({ paragraphs_done: 1, paused: true, pause_reason: "daily budget reached" });
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(202, body));
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useExtractStory(), { wrapper: buildWrapper() });
    hook.current.mutate({ storyId: STORY_ID });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.paused).toBe(true);
    expect(hook.current.data?.pause_reason).toBe("daily budget reached");
  });

  it("rejects with a typed ApiError on 502", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(502, { detail: "gave up after retries" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useExtractStory(), { wrapper: buildWrapper() });
    hook.current.mutate({ storyId: STORY_ID });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(502);
  });
});
