// Tests the outline editor screen (Session 6).
//
// Encodes the user-facing contract before the component exists:
//
//   1. Renders the mode picker (auto / manual / hybrid). Manual is the default
//      because Session 6's primary UX is the deterministic source editor.
//   2. In manual mode, renders an editable textarea seeded with the raw text
//      passed via router state (from UploadScreen's success → navigate flow),
//      plus a live preview block that updates the chapter/scene/paragraph
//      counts as the user edits.
//   3. Submitting in manual mode POSTs to /stories/{id}/structure?mode=manual
//      with the edited raw_text in the body; on 201, the persisted counts
//      block renders.
//   4. Switching to auto mode hides the textarea and sends `raw_text: null` so
//      the backend uses the stored copy.
//   5. A 409 ("already structured") renders the re-structure-specific copy.
//   6. With an empty editor in manual/hybrid (e.g. deep-link refresh, no
//      router state), Build outline is disabled and an inline hint explains
//      why — closes the silent-clear-stored-raw_text footgun.
//   7. After a successful build, the submit button is disabled and relabeled
//      so a second click can't trigger a 409.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, within } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { OutlineEditor } from "./OutlineEditor";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const INITIAL_RAW = "## Chapter One\n### A\nFoo.\n\nBar.\n";

function renderEditor(rawText: string = INITIAL_RAW) {
  const queryClient = new QueryClient({
    defaultOptions: {
      mutations: { retry: false },
      queries: { retry: false },
    },
  });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter
          initialEntries={[{ pathname: `/stories/${STORY_ID}/structure`, state: { rawText } }]}
        >
          <Routes>
            <Route path="/stories/:storyId/structure" element={children} />
          </Routes>
        </MemoryRouter>
      </QueryClientProvider>
    );
  }
  return render(<OutlineEditor />, { wrapper: Wrapper });
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const SUCCESS_BODY = {
  story_id: STORY_ID,
  mode: "manual" as const,
  chapter_count: 1,
  scene_count: 1,
  paragraph_count: 2,
};

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("OutlineEditor", () => {
  it("renders the mode picker, the editor seeded with router-state raw text, and a live preview", () => {
    renderEditor();

    expect(screen.getByTestId("outline-mode-manual")).toBeInTheDocument();
    expect(screen.getByTestId("outline-mode-auto")).toBeInTheDocument();
    expect(screen.getByTestId("outline-mode-hybrid")).toBeInTheDocument();

    const textarea = screen.getByTestId("outline-raw-text") as HTMLTextAreaElement;
    expect(textarea.value).toBe(INITIAL_RAW);

    // Live preview: 1 chapter, 1 scene, 2 paragraphs (matches the initial text).
    const preview = screen.getByTestId("outline-preview");
    expect(preview).toHaveTextContent(/1 chapter/i);
    expect(preview).toHaveTextContent(/1 scene/i);
    expect(preview).toHaveTextContent(/2 paragraphs/i);
  });

  it("live preview updates as the user edits the textarea", () => {
    renderEditor("## A\n### B\nOne.\n");
    const textarea = screen.getByTestId("outline-raw-text") as HTMLTextAreaElement;
    expect(screen.getByTestId("outline-preview")).toHaveTextContent(/1 paragraph/i);

    fireEvent.change(textarea, {
      target: { value: "## A\n### B\nOne.\n\nTwo.\n\nThree.\n" },
    });
    expect(screen.getByTestId("outline-preview")).toHaveTextContent(/3 paragraphs/i);
  });

  it("submits manual mode with the edited raw_text, renders persisted counts on 201", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(201, SUCCESS_BODY));
    vi.stubGlobal("fetch", fetchMock);

    renderEditor();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /build outline/i }));
    });

    const success = await screen.findByTestId("outline-success");
    expect(within(success).getByText(/1 chapter/i)).toBeInTheDocument();
    expect(within(success).getByText(/2 paragraph/i)).toBeInTheDocument();

    expect(fetchMock).toHaveBeenCalledTimes(1);
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/structure\\?mode=manual$`));
    expect(JSON.parse(init.body as string)).toEqual({ raw_text: INITIAL_RAW });

    // After success the submit button is disabled and relabeled so a second
    // click can't trigger the backend's 409 re-structure refusal.
    const submit = screen.getByTestId("outline-submit");
    expect(submit).toBeDisabled();
    expect(submit).toHaveTextContent(/built/i);
  });

  it("switching to auto mode hides the editor and sends raw_text: null", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(201, { ...SUCCESS_BODY, mode: "auto" }));
    vi.stubGlobal("fetch", fetchMock);

    renderEditor();
    await act(async () => {
      fireEvent.click(screen.getByTestId("outline-mode-auto"));
    });

    // Editor textarea is gone in auto mode (the LLM decides; nothing to edit).
    expect(screen.queryByTestId("outline-raw-text")).not.toBeInTheDocument();

    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /build outline/i }));
    });

    await screen.findByTestId("outline-success");
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/structure\\?mode=auto$`));
    expect(JSON.parse(init.body as string)).toEqual({ raw_text: null });
  });

  it("disables submit + shows the empty hint when manual/hybrid editor is empty", () => {
    // Simulates a deep link / refresh where router state didn't carry raw_text.
    // Without the guard the user could click Build outline and the backend
    // would silently overwrite stored raw_text with "" — see the override-and-
    // persist path in backend/src/story_forge/api/stories.py.
    renderEditor("");
    expect(screen.getByTestId("outline-submit")).toBeDisabled();
    expect(screen.getByTestId("outline-empty-hint")).toBeInTheDocument();

    // Auto mode bypasses the editor entirely → submit re-enables (the LLM
    // will work off the stored raw_text on the backend).
    fireEvent.click(screen.getByTestId("outline-mode-auto"));
    expect(screen.getByTestId("outline-submit")).not.toBeDisabled();
    expect(screen.queryByTestId("outline-empty-hint")).not.toBeInTheDocument();
  });

  it("on a 409, surfaces the already-structured message", async () => {
    const fetchMock = vi
      .fn()
      .mockResolvedValue(jsonResponse(409, { detail: "story already has a structure" }));
    vi.stubGlobal("fetch", fetchMock);

    renderEditor();
    await act(async () => {
      fireEvent.click(screen.getByRole("button", { name: /build outline/i }));
    });

    const error = await screen.findByTestId("outline-error");
    expect(error).toHaveTextContent(/already (has a )?structure|already structured|409/i);
  });
});
