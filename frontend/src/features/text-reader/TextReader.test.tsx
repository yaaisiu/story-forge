// Tests for the text-reader page container (Session 33 — M4.S1; extended Session 35 — M4.S2b).
//
// Real `useReader` hook + a stubbed global fetch (the GraphViewer pattern): pins the
// container's state branches (loading / error / empty / success), the legend, the
// rendered highlights, and the graph link. ReaderEntityPanel is mocked to a stub (its own
// test covers its internals + the cytoscape mount is browser-smoke) so this test can pin
// the M4.S2b wiring: click-to-open, neighbour re-target, occurrence drill-flash, close.
// The pure split/colour/occurrence logic is covered by segments/palette/occurrences tests.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Stub the side panel: surface the entity id it was given + buttons that drive its
// callbacks (close / neighbour navigation / occurrence drill-down).
vi.mock("./ReaderEntityPanel", () => ({
  ReaderEntityPanel: ({
    entityId,
    onClose,
    onSelectEntity,
    onNavigateToOccurrence,
  }: {
    entityId: string;
    onClose: () => void;
    onSelectEntity: (id: string) => void;
    onNavigateToOccurrence: (paragraphId: string) => void;
  }) => (
    <aside data-testid="reader-entity-panel-mock">
      <span data-testid="panel-entity-id">{entityId}</span>
      <button data-testid="panel-close" onClick={onClose}>
        close
      </button>
      <button data-testid="panel-neighbour" onClick={() => onSelectEntity("e2")}>
        neighbour
      </button>
      <button data-testid="panel-occurrence" onClick={() => onNavigateToOccurrence("p1")}>
        occurrence
      </button>
    </aside>
  ),
}));

const { TextReader } = await import("./TextReader");

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

  it("opens the entity panel for the clicked highlight", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, READER_BODY)),
    );

    renderReader();

    expect(screen.queryByTestId("reader-entity-panel-mock")).toBeNull();
    fireEvent.click(await screen.findByTestId("highlight"));

    expect(screen.getByTestId("reader-entity-panel-mock")).toBeInTheDocument();
    expect(screen.getByTestId("panel-entity-id")).toHaveTextContent("e1");
  });

  it("re-targets the panel when a neighbour is selected in it", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, READER_BODY)),
    );

    renderReader();

    fireEvent.click(await screen.findByTestId("highlight"));
    fireEvent.click(screen.getByTestId("panel-neighbour"));

    expect(screen.getByTestId("panel-entity-id")).toHaveTextContent("e2");
  });

  it("flashes the target highlight when an occurrence is drilled", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, READER_BODY)),
    );

    renderReader();

    fireEvent.click(await screen.findByTestId("highlight"));
    expect(screen.getByTestId("highlight")).not.toHaveAttribute("data-flash");

    fireEvent.click(screen.getByTestId("panel-occurrence"));
    expect(screen.getByTestId("highlight")).toHaveAttribute("data-flash", "true");
  });

  it("closes the panel", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, READER_BODY)),
    );

    renderReader();

    fireEvent.click(await screen.findByTestId("highlight"));
    expect(screen.getByTestId("reader-entity-panel-mock")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("panel-close"));
    await waitFor(() => expect(screen.queryByTestId("reader-entity-panel-mock")).toBeNull());
  });
});
