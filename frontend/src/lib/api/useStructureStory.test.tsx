// Tests the structure mutation hook (Session 6).
//
// Encodes the contract before the hook exists:
//
//   1. POSTs to `/stories/{id}/structure?mode=...` with a JSON body
//      `{raw_text}` (the manual editor's edited source; null/undefined for
//      auto/hybrid). Resolves with the typed StructureResponse on 201.
//   2. 404 / 409 / 502 reject with a typed ApiError carrying the status; the
//      OutlineScreen branches on status to render the right copy.
//   3. The 422 overload — FastAPI's auto-attached HTTPValidationError vs the
//      domain ChunkingTooLongError, both returning 422 with different bodies —
//      is discriminated by reading `err.body`. We assert ApiError.body holds
//      the raw parsed JSON so callers can inspect its shape.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useStructureStory } from "./useStructureStory";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const STORY_ID = "00000000-0000-0000-0000-000000000002";

const SAMPLE_RESPONSE = {
  story_id: STORY_ID,
  mode: "manual" as const,
  chapter_count: 1,
  scene_count: 2,
  paragraph_count: 3,
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

describe("useStructureStory", () => {
  it("posts the chosen mode + raw_text and resolves the typed response on 201", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, SAMPLE_RESPONSE));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStructureStory(), { wrapper: buildWrapper() });

    result.current.mutate({
      storyId: STORY_ID,
      mode: "manual",
      rawText: "## Chapter\n### Scene\nLine.\n",
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(SAMPLE_RESPONSE);

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/structure\\?mode=manual$`));
    expect(init.method).toBe("POST");
    expect((init.headers as Record<string, string>)["Content-Type"]).toBe("application/json");
    expect(JSON.parse(init.body as string)).toEqual({
      raw_text: "## Chapter\n### Scene\nLine.\n",
    });
  });

  it("sends null raw_text when none provided (auto/hybrid path)", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, SAMPLE_RESPONSE));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStructureStory(), { wrapper: buildWrapper() });

    result.current.mutate({ storyId: STORY_ID, mode: "auto" });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ raw_text: null });
  });

  it.each([
    ["empty string", ""],
    ["whitespace only", "   \n  \t  "],
  ])(
    "drops the override when rawText is %s (defense-in-depth, prevents destructive overwrite)",
    async (_label, value) => {
      // The OutlineEditor UI already disables submit when its textarea is
      // empty (see OutlineEditor.tsx:73), but a programmatic caller — or a
      // future regression that re-enables the button — could still slip an
      // empty string through. The hook treats empty/whitespace the same as
      // "no override" so the backend keeps the stored raw_text instead of
      // overwriting it.
      const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, SAMPLE_RESPONSE));
      vi.stubGlobal("fetch", fetchMock);

      const { result } = renderHook(() => useStructureStory(), { wrapper: buildWrapper() });
      result.current.mutate({ storyId: STORY_ID, mode: "manual", rawText: value });

      await waitFor(() => expect(result.current.isSuccess).toBe(true));
      const [, init] = fetchMock.mock.calls[0] as [string, RequestInit];
      expect(JSON.parse(init.body as string)).toEqual({ raw_text: null });
    },
  );

  it.each([
    [404, "story not found"],
    [409, "story already has a structure"],
    [502, "chunking agent failed"],
  ])("rejects with a typed ApiError on %i", async (status, detail) => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(status, { detail }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStructureStory(), { wrapper: buildWrapper() });

    result.current.mutate({ storyId: STORY_ID, mode: "manual" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    const error = result.current.error;
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(status);
    expect((error as ApiError).detail).toBe(detail);
  });

  it("exposes the raw body on 422 so callers can discriminate validation vs domain error", async () => {
    // FastAPI's HTTPValidationError shape — a 422 with detail: ValidationError[].
    // Callers need the structured body to tell this apart from the domain-level
    // 422 (ChunkingTooLongError) which uses {detail: str}. The hook itself
    // doesn't branch — it just exposes both via ApiError.body.
    const validation = {
      detail: [
        {
          loc: ["query", "mode"],
          msg: "Input should be 'auto', 'manual' or 'hybrid'",
          type: "literal_error",
        },
      ],
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(422, validation));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useStructureStory(), { wrapper: buildWrapper() });

    result.current.mutate({ storyId: STORY_ID, mode: "manual" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    const error = result.current.error as ApiError;
    expect(error.status).toBe(422);
    expect(error.body).toEqual(validation);
  });
});
