// Tests for the review-decision mutation hook (Session 25 — M3.S4b Stage 4 review UI).
//
// Pins: an accept POSTs /candidates/{cid}/accept with the AcceptRequest body and
// resolves the ReviewResponse; a reject POSTs /candidates/{cid}/reject with no body;
// a successful decision invalidates BOTH the queue (so the decided item drops off)
// and the story graph (so it fills as the author commits — the handoff's re-fetch
// requirement); a 409 stale-merge-target surfaces as a typed ApiError.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { candidatesQueryKey } from "./useCandidates";
import { ApiError, useReviewCandidate } from "./useReviewCandidate";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const CANDIDATE_ID = "00000000-0000-0000-0000-0000000000c1";

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

describe("useReviewCandidate", () => {
  it("accept POSTs the accept route with the body and invalidates queue + graph", async () => {
    const review = {
      candidate_id: CANDIDATE_ID,
      status: "merged",
      entity_id: "00000000-0000-0000-0000-0000000000e1",
      already_decided: false,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, review));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useReviewCandidate(STORY_ID), { wrapper });
    hook.current.mutate({
      candidateId: CANDIDATE_ID,
      decision: "accept",
      accept: { action: "merge", target_entity_id: "00000000-0000-0000-0000-0000000000e1" },
    });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.status).toBe("merged");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/candidates/${CANDIDATE_ID}/accept$`));
    expect(init.method).toBe("POST");
    expect(JSON.parse(init.body as string)).toMatchObject({ action: "merge" });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: candidatesQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
  });

  it("reject POSTs the reject route with no body and refreshes only the queue, not the graph", async () => {
    const review = {
      candidate_id: CANDIDATE_ID,
      status: "rejected",
      entity_id: null,
      already_decided: false,
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, review));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useReviewCandidate(STORY_ID), { wrapper });
    hook.current.mutate({ candidateId: CANDIDATE_ID, decision: "reject" });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.status).toBe("rejected");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/candidates/${CANDIDATE_ID}/reject$`));
    expect(init.method).toBe("POST");
    expect(init.body).toBe("null");

    // A reject writes nothing to the graph — only the queue needs refreshing.
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: candidatesQueryKey(STORY_ID) });
    expect(invalidateSpy).not.toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
  });

  it("rejects with a typed ApiError on 409 (stale merge target)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(409, { detail: "merge target no longer exists" }));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useReviewCandidate(STORY_ID), { wrapper });
    hook.current.mutate({
      candidateId: CANDIDATE_ID,
      decision: "accept",
      accept: { action: "merge", target_entity_id: "00000000-0000-0000-0000-0000000000ff" },
    });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(409);
  });
});
