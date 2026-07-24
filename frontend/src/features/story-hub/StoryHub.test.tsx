// Tests for the story hub (Grzymalin S3 — app navigation).
//
// Pins the navigation contract: the header names the story from GET /stories/{id},
// and every one of the seven per-story screens is reachable by a link carrying the
// id in the URL. The hub stays usable when the title fetch fails (the links only
// need the id). Mounted under a `/stories/:storyId` route so useParams resolves.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { StoryHub } from "./StoryHub";

const STORY_ID = "11111111-1111-1111-1111-111111111111";
const STORY_BODY = {
  id: STORY_ID,
  title: "Grzymalin research",
  ingested_at: "2026-06-01T10:00:00Z",
};

// Every screen the hub must link to, and the path suffix each maps to.
const EXPECTED_SCREENS = [
  ["structure", "structure"],
  ["reader", "reader"],
  ["graph", "graph"],
  ["review", "review"],
  ["relations", "relations"],
  ["duplicates", "duplicates"],
  ["normalise-names", "normalise-names"],
] as const;

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[`/stories/${STORY_ID}`]}>
          <Routes>
            <Route path="/stories/:storyId" element={children} />
          </Routes>
        </MemoryRouter>
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

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("StoryHub", () => {
  it("names the story and links every screen carrying the id in the URL", async () => {
    vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse(200, STORY_BODY)));

    render(<StoryHub />, { wrapper: buildWrapper() });

    expect(await screen.findByTestId("hub-title")).toHaveTextContent("Grzymalin research");
    for (const [key, suffix] of EXPECTED_SCREENS) {
      expect(screen.getByTestId(`hub-link-${key}`)).toHaveAttribute(
        "href",
        `/stories/${STORY_ID}/${suffix}`,
      );
    }
    expect(screen.getByTestId("hub-back-to-projects")).toHaveAttribute("href", "/projects");
  });

  it("shows a loading header until the story resolves", () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );

    render(<StoryHub />, { wrapper: buildWrapper() });

    expect(screen.getByTestId("hub-title-loading")).toBeInTheDocument();
  });

  it("stays navigable when the title fetch fails (links need only the id)", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue(jsonResponse(404, { detail: "story not found" })),
    );

    render(<StoryHub />, { wrapper: buildWrapper() });

    // Fallback header instead of a title, but the screen links still render + resolve.
    expect(await screen.findByTestId("hub-title-error")).toBeInTheDocument();
    expect(screen.getByTestId("hub-link-review")).toHaveAttribute(
      "href",
      `/stories/${STORY_ID}/review`,
    );
  });
});
