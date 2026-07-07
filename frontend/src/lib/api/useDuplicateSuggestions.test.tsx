// Tests for the duplicate-suggestions query hook (Session 79 — Graph-quality S4b).
//
// Pins: it GETs /stories/{id}/duplicate-suggestions and resolves the ranked list; it stays
// disabled (no fetch) until a storyId is known; a failure bubbles as a typed ApiError.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError } from "./client";
import { useDuplicateSuggestions } from "./useDuplicateSuggestions";

const STORY_ID = "00000000-0000-0000-0000-000000000002";

function wrapperWith() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
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

describe("useDuplicateSuggestions", () => {
  it("GETs the duplicate-suggestions route and resolves the ranked list", async () => {
    const payload = {
      suggestions: [
        {
          entity_a: {
            entity_id: "a",
            canonical_name: "Elara",
            type: "Person",
            aliases: [],
            context_quote: "Elara stepped forward.",
          },
          entity_b: {
            entity_id: "b",
            canonical_name: "Elira",
            type: "Person",
            aliases: ["El"],
            context_quote: null,
          },
          name_score: 88,
          cosine_score: 0.91,
          combined_score: 0.9,
        },
      ],
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, payload));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDuplicateSuggestions(STORY_ID), {
      wrapper: wrapperWith(),
    });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(fetchMock).toHaveBeenCalledWith(
      `http://localhost:8000/stories/${STORY_ID}/duplicate-suggestions`,
      { method: "GET" },
    );
    expect(result.current.data?.suggestions).toHaveLength(1);
    expect(result.current.data?.suggestions[0]?.name_score).toBe(88);
  });

  it("does not fire while the storyId is undefined", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    renderHook(() => useDuplicateSuggestions(undefined), { wrapper: wrapperWith() });

    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("surfaces a failure as a typed ApiError", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(503, { detail: "store unavailable" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useDuplicateSuggestions(STORY_ID), {
      wrapper: wrapperWith(),
    });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect(result.current.error?.status).toBe(503);
  });
});
