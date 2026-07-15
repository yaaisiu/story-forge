// Tests for the label-vocabulary query hook (Session 96 — Graph-quality S6b).
//
// Pins: it GETs /stories/{id}/label-vocabulary and resolves both ranked vocabularies; it stays
// disabled (no fetch) until a storyId is known; a failure bubbles as a typed ApiError (404/503).

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./client";
import { useLabelVocabulary } from "./useLabelVocabulary";

const STORY_ID = "00000000-0000-0000-0000-000000000002";

function wrapperWith() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
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

describe("useLabelVocabulary", () => {
  it("GETs the label-vocabulary route and resolves both vocabularies", async () => {
    const payload = {
      predicate_suggestions: [
        {
          label_lo: "LOCATED_AT",
          label_hi: "LOCATED_IN",
          count_lo: 3,
          count_hi: 12,
          name_score: 91,
          cosine_score: 0.88,
          combined_score: 0.9,
        },
      ],
      type_suggestions: [
        {
          label_lo: "Place",
          label_hi: "Location",
          count_lo: 4,
          count_hi: 9,
          name_score: 80,
          cosine_score: null,
          combined_score: 0.8,
        },
      ],
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, payload));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useLabelVocabulary(STORY_ID), { wrapper: wrapperWith() });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/stories/${STORY_ID}/label-vocabulary`,
      { method: "GET" },
    );
    expect(result.current.data?.predicate_suggestions).toHaveLength(1);
    expect(result.current.data?.type_suggestions[0]?.cosine_score).toBeNull();
  });

  it("does not fire while the storyId is undefined", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useLabelVocabulary(undefined), { wrapper: wrapperWith() });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces a failure as a typed ApiError", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(503, { detail: "a data store is unavailable" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useLabelVocabulary(STORY_ID), { wrapper: wrapperWith() });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect(result.current.error?.status).toBe(503);
  });
});
