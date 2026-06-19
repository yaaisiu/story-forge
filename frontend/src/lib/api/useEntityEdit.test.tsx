// Tests for the entity-edit mutation hook (Session 38 — M4.S3a-fe).
//
// Pins (mirroring useDecideRelation.test.tsx): a successful edit PATCHes
// /stories/{id}/entities/{eid} with the patch body and invalidates the reader, the story
// graph, AND the entity-detail bundle (so a corrected name re-highlights, a new type
// recolours, and the panel refetches — DM-S3a-4). A blank name/type surfaces as a typed
// ApiError(400) — the real status the PATCH route raises (EntityEditInvalid), not a 409.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useEntityEdit } from "./useEntityEdit";
import { entityDetailQueryKey } from "./useEntityDetail";
import { readerQueryKey } from "./useReader";
import { storyGraphQueryKey } from "./useStoryGraph";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const ENTITY_ID = "00000000-0000-0000-0000-0000000000e1";

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

describe("useEntityEdit", () => {
  it("PATCHes the patch body and invalidates reader + graph + entity-detail", async () => {
    const updated = {
      entity_id: ENTITY_ID,
      canonical_name: "Warden",
      type: "character",
      aliases: ["the Warden"],
      properties: { age: 40 },
    };
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, updated));
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper, invalidateSpy } = buildHarness();

    const { result: hook } = renderHook(() => useEntityEdit(STORY_ID, ENTITY_ID), { wrapper });
    hook.current.mutate({ canonical_name_en: "Warden", type: "character" });

    await waitFor(() => expect(hook.current.isSuccess).toBe(true));
    expect(hook.current.data?.canonical_name).toBe("Warden");

    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/entities/${ENTITY_ID}$`));
    expect(init.method).toBe("PATCH");
    expect(JSON.parse(init.body as string)).toEqual({
      canonical_name_en: "Warden",
      type: "character",
    });

    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: readerQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: storyGraphQueryKey(STORY_ID) });
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: entityDetailQueryKey(STORY_ID, ENTITY_ID),
    });
  });

  it("surfaces a blank-name/type rejection as a typed ApiError(400)", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(
        jsonResponse(400, { detail: "an entity must keep at least one canonical name" }),
      );
    vi.stubGlobal("fetch", fetchMock);
    const { wrapper } = buildHarness();

    const { result: hook } = renderHook(() => useEntityEdit(STORY_ID, ENTITY_ID), { wrapper });
    hook.current.mutate({ canonical_name_en: "" });

    await waitFor(() => expect(hook.current.isError).toBe(true));
    expect(hook.current.error).toBeInstanceOf(ApiError);
    expect((hook.current.error as ApiError).status).toBe(400);
  });
});
