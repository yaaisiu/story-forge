// Tests for the review-queue fetch hook (Session 25 — M3.S4b Stage 4 review UI).
//
// Pins: GETs /stories/{id}/candidates and resolves the pending queue on 200; stays
// disabled (never fetches) until a story id is known; surfaces a 503 (staging store
// down) as a typed ApiError the queue UI can branch on.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useCandidates } from "./useCandidates";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
  };
}

const STORY_ID = "00000000-0000-0000-0000-000000000002";

function candidate(over: Record<string, unknown> = {}) {
  return {
    id: "00000000-0000-0000-0000-0000000000c1",
    paragraph_id: "00000000-0000-0000-0000-0000000000p1",
    candidate_name: "Janek",
    type: "Character",
    context: "Janek entered the mill...",
    proposal: "merge",
    target_entity_id: "00000000-0000-0000-0000-0000000000e1",
    stage_reached: 3,
    confidence: 0.91,
    reasoning: "Same diminutive as the existing Jan.",
    alternatives: [],
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

describe("useCandidates", () => {
  it("GETs /stories/{id}/candidates and resolves the pending queue on 200", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, { candidates: [candidate()] }));
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useCandidates(STORY_ID), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.candidates).toHaveLength(1);
    expect(hook.current.data?.candidates[0]?.candidate_name).toBe("Janek");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/candidates$`));
    expect(init.method).toBe("GET");
  });

  it("stays disabled and never fetches while the story id is undefined", () => {
    const fetchMock = vi.fn();
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useCandidates(undefined), {
      wrapper: buildWrapper(),
    });

    expect(hook.current.fetchStatus).toBe("idle");
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("rejects with a typed ApiError on 503 (staging store unavailable)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(503, { detail: "the staging store is unavailable" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result: hook } = renderHook(() => useCandidates(STORY_ID), {
      wrapper: buildWrapper(),
    });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(503);
  });
});
