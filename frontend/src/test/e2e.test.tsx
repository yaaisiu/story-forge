// End-to-end happy-path test for Session 6's M1 flow.
//
// Walks the full browser-side flow under a memory router with a stubbed fetch:
//
//   1. Land on "/" → upload screen renders.
//   2. Select a .txt file → filename appears.
//   3. Click Upload → backend returns 201; success block renders the language
//      readout + the "Continue to outline" link with the new story_id.
//   4. Click the link → router navigates to /stories/:id/structure; the editor
//      mounts with the raw_text from upload pre-loaded into the textarea.
//   5. Click "Build outline" (manual mode is the default) → backend returns
//      201; the persisted-counts block renders.
//
// One test, two HTTP round-trips, no real network. The point isn't to
// re-cover the per-screen assertions (the per-feature test files do that), it
// is to prove that the routing + state-passing seam between the two features
// is actually wired so the M1 milestone is "usable in the browser" (the
// success criterion in docs/PLAN_SHORT.md).

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppShell } from "../app/AppShell";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const SAMPLE_RAW = "## Chapter One\n### Dawn\nLine one.\n\nLine two.\n";

const UPLOAD_BODY = {
  project_id: "00000000-0000-0000-0000-000000000001",
  story_id: STORY_ID,
  title: "draft",
  language: "en",
  paragraph_count: 2,
  raw_text: SAMPLE_RAW,
};

const STRUCTURE_BODY = {
  story_id: STORY_ID,
  mode: "manual" as const,
  chapter_count: 1,
  scene_count: 1,
  paragraph_count: 2,
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

describe("M1 happy path: upload → outline persisted", () => {
  it("walks from / to a persisted outline using the typed client end-to-end", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/stories/upload")) return jsonResponse(201, UPLOAD_BODY);
      if (url.includes(`/stories/${STORY_ID}/structure`)) {
        return jsonResponse(201, STRUCTURE_BODY);
      }
      throw new Error(`unexpected fetch url: ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    const queryClient = new QueryClient({
      defaultOptions: {
        mutations: { retry: false },
        queries: { retry: false },
      },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <AppShell />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // 1. Upload screen is mounted at "/".
    const fileInput = screen.getByTestId("upload-file-input") as HTMLInputElement;

    // 2. Pick a .txt file.
    const file = new File([SAMPLE_RAW], "draft.txt", { type: "text/plain" });
    await act(async () => {
      fireEvent.change(fileInput, { target: { files: [file] } });
    });

    // 3. Upload → success state with the language readout and the continue link.
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });
    await screen.findByTestId("upload-success");
    const continueLink = screen.getByTestId("upload-continue-link") as HTMLAnchorElement;
    expect(continueLink.getAttribute("href")).toBe(`/stories/${STORY_ID}/structure`);

    // 4. Click the link → editor mounts with the upload's raw_text pre-loaded.
    await act(async () => {
      fireEvent.click(continueLink);
    });
    const textarea = (await screen.findByTestId("outline-raw-text")) as HTMLTextAreaElement;
    expect(textarea.value).toBe(SAMPLE_RAW);

    // 5. Build outline (manual is the default) → persisted-counts block renders.
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /build outline/i }));
    });
    const success = await screen.findByTestId("outline-success");
    expect(success).toHaveTextContent(/1 chapter/i);
    expect(success).toHaveTextContent(/2 paragraph/i);

    // Two round-trips: one upload, one structure, in that order.
    expect(fetchMock).toHaveBeenCalledTimes(2);
    const uploadCall = fetchMock.mock.calls[0]?.[0];
    const structureCall = fetchMock.mock.calls[1]?.[0];
    expect(String(uploadCall)).toMatch(/\/stories\/upload$/);
    expect(String(structureCall)).toMatch(
      new RegExp(`/stories/${STORY_ID}/structure\\?mode=manual$`),
    );
  });
});
