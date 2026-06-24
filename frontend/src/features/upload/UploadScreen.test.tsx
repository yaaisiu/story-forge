// Tests the upload screen (Session 6 — Frontend upload UI).
//
// Encodes the user-facing contract of the screen as failing assertions before
// the component exists:
//
//   1. The screen renders both a file <input type="file"> and a drag-drop zone,
//      so a user can either pick or drag a story file.
//   2. After choosing a file, the filename is shown to confirm the selection;
//      the Upload button enables.
//   3. Clicking Upload posts to /stories/upload (via the useUploadStory hook),
//      and on a 201 the success state shows the detected language and the
//      paragraph count from the typed StoryUploadResponse.
//   4. On a 413 the screen surfaces a status-specific message — using the
//      ApiError.status discriminator, not a string match on the backend's
//      detail text.
//
// We stub global `fetch` instead of pulling in MSW (same call as the
// useUploadStory test). The screen mounts under a fresh QueryClient + a
// MemoryRouter so navigation calls in later sessions don't break the test.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UploadScreen } from "./UploadScreen";

function buildWrapper(initialEntry: string | { pathname: string; state: unknown } = "/upload") {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[initialEntry]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const SUCCESS_BODY = {
  project_id: "00000000-0000-0000-0000-000000000001",
  story_id: "00000000-0000-0000-0000-000000000002",
  title: "draft",
  language: "en",
  paragraph_count: 3,
  raw_text: "hello world",
};

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("UploadScreen", () => {
  it("renders the picker and the drag-drop zone", () => {
    render(<UploadScreen />, { wrapper: buildWrapper() });

    expect(screen.getByTestId("upload-file-input")).toBeInTheDocument();
    expect(screen.getByTestId("upload-dropzone")).toBeInTheDocument();
    // No file yet → upload button is disabled.
    expect(screen.getByRole("button", { name: /upload/i })).toBeDisabled();
  });

  it("on a successful upload, shows the detected language and paragraph count", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, SUCCESS_BODY));
    vi.stubGlobal("fetch", fetchMock);

    render(<UploadScreen />, { wrapper: buildWrapper() });

    const file = new File(["hello"], "draft.txt", { type: "text/plain" });
    const input = screen.getByTestId("upload-file-input") as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });

    // Selected-file readout confirms the pick.
    expect(screen.getByTestId("upload-selected-file")).toHaveTextContent("draft.txt");

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    // Success block names the language and the paragraph count straight from
    // StoryUploadResponse — no extra fetch / no derived state.
    const success = await screen.findByTestId("upload-success");
    expect(success).toHaveTextContent(/en/i);
    expect(success).toHaveTextContent(/3/);

    // The mutation went out exactly once, to the right route.
    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toMatch(/\/stories\/upload$/);
  });

  it("links to the project picker when not adding to a project", () => {
    render(<UploadScreen />, { wrapper: buildWrapper() });

    const link = screen.getByTestId("browse-projects-link");
    expect(link).toHaveAttribute("href", "/projects");
    expect(screen.queryByTestId("upload-target-project")).not.toBeInTheDocument();
  });

  it("uploads into the target project when navigated with a projectId in router state", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, SUCCESS_BODY));
    vi.stubGlobal("fetch", fetchMock);

    const projectId = "00000000-0000-0000-0000-000000000001";
    render(<UploadScreen />, {
      wrapper: buildWrapper({
        pathname: "/upload",
        state: { projectId, projectName: "Oakhaven" },
      }),
    });

    // The add-to-project context is shown instead of the browse link.
    expect(screen.getByTestId("upload-target-project")).toHaveTextContent("Oakhaven");
    expect(screen.queryByTestId("browse-projects-link")).not.toBeInTheDocument();

    const file = new File(["hello"], "draft.txt", { type: "text/plain" });
    const input = screen.getByTestId("upload-file-input") as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    await screen.findByTestId("upload-success");
    const [url] = fetchMock.mock.calls[0] as [string];
    expect(url).toMatch(new RegExp(`/stories/upload\\?project_id=${projectId}$`));
  });

  it("on a 413 response, shows the status-specific error", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(413, { detail: "file exceeds the maximum upload size" }));
    vi.stubGlobal("fetch", fetchMock);

    render(<UploadScreen />, { wrapper: buildWrapper() });

    const file = new File(["x".repeat(64)], "huge.txt", { type: "text/plain" });
    const input = screen.getByTestId("upload-file-input") as HTMLInputElement;
    await act(async () => {
      fireEvent.change(input, { target: { files: [file] } });
    });
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /upload/i }));
    });

    const error = await screen.findByTestId("upload-error");
    // The screen discriminates by status: a 413 must render the "too large"
    // message — proves we branch on err.status, not on a translated detail.
    expect(error).toHaveTextContent(/too large|413/i);
  });
});
