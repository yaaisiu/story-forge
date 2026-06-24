// First hand-written TanStack Query hook test (Session 6 — Frontend upload UI).
//
// What this test pins down (the spec, encoded as assertions before any
// production code exists):
//
//   1. The hook posts `multipart/form-data` to `POST /stories/upload` with the
//      File under the form field name `file` (matches the FastAPI parameter
//      name in `backend/src/story_forge/api/stories.py`).
//   2. A 201 JSON body resolves to a typed `StoryUploadResponse` (project_id,
//      story_id, title, language, paragraph_count).
//   3. 400 / 413 / 415 reject with a typed `ApiError` carrying `status` and the
//      `detail` from the backend's `ErrorResponse`. This is the discriminator
//      the upload UI needs to render "empty file" vs "too big" vs "wrong type"
//      distinctly — without parsing the message string.
//
// We stub `globalThis.fetch` via `vi.stubGlobal` rather than adding MSW: two
// routes don't justify the dep. Each test gets its own QueryClient with
// `retry: false` so a rejected mutation surfaces immediately instead of
// looping.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ApiError, useUploadStory } from "./useUploadStory";

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

const SAMPLE_RESPONSE = {
  project_id: "00000000-0000-0000-0000-000000000001",
  story_id: "00000000-0000-0000-0000-000000000002",
  title: "draft",
  language: "en",
  paragraph_count: 3,
  raw_text: "hello world",
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

describe("useUploadStory", () => {
  it("posts multipart/form-data to /stories/upload and resolves the typed response on 201", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, SAMPLE_RESPONSE));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useUploadStory(), { wrapper: buildWrapper() });

    const file = new File(["hello world"], "draft.txt", { type: "text/plain" });
    result.current.mutate({ file });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data).toEqual(SAMPLE_RESPONSE);

    // One call to the right URL/method, with the file under "file" in FormData.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(/\/stories\/upload$/);
    expect(init.method).toBe("POST");
    expect(init.body).toBeInstanceOf(FormData);
    const sentFile = (init.body as FormData).get("file");
    expect(sentFile).toBeInstanceOf(File);
    expect((sentFile as File).name).toBe("draft.txt");
    // No projectId given → no project_id query param (the backend creates a new project).
    expect(url).not.toContain("project_id");
  });

  it("targets an existing project via the project_id query param when projectId is given", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, SAMPLE_RESPONSE));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useUploadStory(), { wrapper: buildWrapper() });

    const projectId = "00000000-0000-0000-0000-000000000001";
    const file = new File(["hello world"], "draft.txt", { type: "text/plain" });
    result.current.mutate({ file, projectId });

    await waitFor(() => expect(result.current.isSuccess).toBe(true));

    const [url] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/upload\\?project_id=${projectId}$`));
  });

  it("surfaces the route's 404 (target project does not exist) as a typed ApiError", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(404, { detail: "project not found" }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useUploadStory(), { wrapper: buildWrapper() });

    const file = new File(["x"], "draft.txt", { type: "text/plain" });
    result.current.mutate({ file, projectId: "00000000-0000-0000-0000-0000000000ff" });

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(result.current.error).toBeInstanceOf(ApiError);
    expect((result.current.error as ApiError).status).toBe(404);
  });

  it.each([
    [400, "uploaded file is empty"],
    [413, "file exceeds the maximum upload size"],
    [415, "unsupported file type: '.bin'"],
  ])("rejects with a typed ApiError on %i", async (status, detail) => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(status, { detail }));
    vi.stubGlobal("fetch", fetchMock);

    const { result } = renderHook(() => useUploadStory(), { wrapper: buildWrapper() });

    const file = new File(["x"], "draft.bin", { type: "application/octet-stream" });
    result.current.mutate({ file });

    await waitFor(() => expect(result.current.isError).toBe(true));
    const error = result.current.error;
    expect(error).toBeInstanceOf(ApiError);
    expect((error as ApiError).status).toBe(status);
    expect((error as ApiError).detail).toBe(detail);
  });
});
