// Tests for the text-reader page container (Session 33 — M4.S1).
//
// Real `useReader` hook + a stubbed global fetch (the GraphViewer pattern): pins the
// container's state branches (loading / error / empty / success), the legend, the
// rendered highlights, and the graph link. The pure split/colour logic is covered by
// segments.test / palette.test; ParagraphText + Legend have their own render tests.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { TextReader } from "./TextReader";

const STORY_ID = "00000000-0000-0000-0000-000000000002";

const READER_BODY = {
  paragraphs: [
    {
      id: "p1",
      text: "Janek walked to the mill.",
      highlights: [{ start: 0, end: 5, entity_id: "e1", type: "character" }],
    },
    { id: "p2", text: "It was quiet.", highlights: [] },
  ],
  entities: [{ entity_id: "e1", canonical_name: "Janek", type: "character", aliases: ["Jan"] }],
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderReader() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/stories/${STORY_ID}/reader`]}>
        <Routes>
          <Route path="/stories/:storyId/reader" element={<TextReader />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("TextReader", () => {
  it("renders the story text with an inline highlight, a legend, and a graph link", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, READER_BODY)),
    );

    renderReader();

    const text = await screen.findByTestId("reader-text");
    expect(text).toHaveTextContent("Janek walked to the mill.");
    expect(text).toHaveTextContent("It was quiet.");

    const mark = screen.getByTestId("highlight");
    expect(mark).toHaveTextContent("Janek");
    expect(mark).toHaveAttribute("title", "Janek — character\nAliases: Jan");

    expect(screen.getByTestId("reader-legend")).toHaveTextContent("character");
    expect(screen.getByTestId("graph-link")).toHaveAttribute("href", `/stories/${STORY_ID}/graph`);
  });

  it("shows the empty state for a story with no paragraphs", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, { paragraphs: [], entities: [] })),
    );

    renderReader();

    expect(await screen.findByTestId("reader-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("reader-text")).toBeNull();
  });

  it("shows an error when the reader request fails", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(404, { detail: "story not found" })),
    );

    renderReader();

    expect(await screen.findByTestId("reader-error")).toBeInTheDocument();
  });

  it("shows the loading state while the request is in flight", () => {
    // A never-resolving fetch keeps the query pending so the loading branch renders.
    vi.stubGlobal(
      "fetch",
      vi.fn(() => new Promise<Response>(() => {})),
    );

    renderReader();

    expect(screen.getByTestId("reader-loading")).toBeInTheDocument();
    expect(screen.queryByTestId("reader-text")).toBeNull();
  });
});
