// Tests for the text-reader page container (Session 33 — M4.S1; extended Session 35 — M4.S2b,
// M4.S3c-fe1).
//
// Real `useReader` hook + a stubbed global fetch (the GraphViewer pattern): pins the
// container's state branches (loading / error / empty / success), the legend, the
// rendered highlights, and the graph link. Two children are mocked to stubs so this test can
// pin the *container's* wiring without their runtimes: ReaderEntityPanel (its own test covers
// its internals; the cytoscape mount is browser-smoke) and ReaderEditor (the ProseMirror/
// Tiptap mount jsdom can't drive — the same boundary as the cytoscape canvases). The pure
// document/decoration/colour/occurrence logic is covered by the
// readerDoc/decorations/palette/occurrences tests; here we pin click-to-open, neighbour
// re-target, occurrence drill-flash, and close.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { ReaderParagraph } from "../../lib/api/useReader";
import type { ContextMenuRequest, ParagraphSpan } from "./correction";
import type { ReaderFlash } from "./ReaderEditor";

// Stub the editor: render each paragraph's text (so the success branch shows the prose) plus
// one clickable `highlight` per highlight that drives `onEntityClick` and reflects `flash` as
// `data-flash` — enough to pin the container wiring. The real decoration rendering (offsets,
// tooltip, colour) is unit-tested in decorations.test.ts and verified in the browser smoke.
//
// For M4.S3c-fe2 it also exposes synthetic correction triggers — buttons that fire
// `onContextMenuRequest` (a search highlight, a manual highlight, a free selection) and
// `onSelectionChange` (the re-selected new span) — so the menu→popover/boundary→mutation flow can
// be driven in jsdom without the real selection runtime (verified in the browser smoke instead).
vi.mock("./ReaderEditor", () => ({
  ReaderEditor: ({
    paragraphs,
    onEntityClick,
    flash,
    onContextMenuRequest,
    onSelectionChange,
  }: {
    paragraphs: readonly ReaderParagraph[];
    onEntityClick: (id: string) => void;
    flash: ReaderFlash | null;
    onContextMenuRequest?: (request: ContextMenuRequest) => void;
    onSelectionChange?: (selection: ParagraphSpan | null) => void;
  }) => (
    <div data-testid="reader-editor-mock">
      {paragraphs.map((paragraph) => (
        <p key={paragraph.id} data-paragraph-id={paragraph.id}>
          <span>{paragraph.text}</span>
          {paragraph.highlights.map((highlight, index) => (
            <button
              key={index}
              data-testid="highlight"
              data-entity-id={highlight.entity_id}
              data-flash={
                flash?.paragraphId === paragraph.id && flash.entityId === highlight.entity_id
                  ? "true"
                  : undefined
              }
              onClick={() => onEntityClick(highlight.entity_id)}
            >
              {paragraph.text.slice(highlight.start, highlight.end)}
            </button>
          ))}
        </p>
      ))}
      <button
        data-testid="ctx-search-highlight"
        onClick={() =>
          onContextMenuRequest?.({
            anchor: { x: 1, y: 2 },
            target: "highlight",
            paragraphId: "p1",
            span_start: 0,
            span_end: 5,
            selectedText: "Janek",
            entityId: "e1",
            source: "search",
            mentionId: null,
          })
        }
      >
        ctx search highlight
      </button>
      <button
        data-testid="ctx-manual-highlight"
        onClick={() =>
          onContextMenuRequest?.({
            anchor: { x: 1, y: 2 },
            target: "highlight",
            paragraphId: "p1",
            span_start: 0,
            span_end: 5,
            selectedText: "Janek",
            entityId: "e1",
            source: "manual",
            mentionId: "mention-1",
          })
        }
      >
        ctx manual highlight
      </button>
      <button
        data-testid="ctx-selection"
        onClick={() =>
          onContextMenuRequest?.({
            anchor: { x: 1, y: 2 },
            target: "selection",
            paragraphId: "p1",
            span_start: 6,
            span_end: 12,
            selectedText: "walked",
          })
        }
      >
        ctx selection
      </button>
      <button
        data-testid="select-new-span"
        onClick={() =>
          onSelectionChange?.({
            paragraphId: "p1",
            span_start: 13,
            span_end: 16,
            selectedText: "the",
          })
        }
      >
        select new span
      </button>
    </div>
  ),
}));

// The popover reuses EntityPicker; mock it to a fixed-pick button (the panel test's stub).
const PICKED_ID = "00000000-0000-0000-0000-0000000000c9";
vi.mock("../extraction-review/EntityPicker", () => ({
  EntityPicker: ({ onPick }: { onPick: (r: { entity_id: string }) => void }) => (
    <button data-testid="entity-picker-pick" onClick={() => onPick({ entity_id: PICKED_ID })}>
      pick
    </button>
  ),
}));

// Stub the side panel: surface the entity id it was given + buttons that drive its
// callbacks (close / neighbour navigation / occurrence drill-down).
vi.mock("./ReaderEntityPanel", () => ({
  ReaderEntityPanel: ({
    entityId,
    onClose,
    onDeleted,
    onSelectEntity,
    onNavigateToOccurrence,
  }: {
    entityId: string;
    onClose: () => void;
    onDeleted: () => void;
    onSelectEntity: (id: string) => void;
    onNavigateToOccurrence: (paragraphId: string) => void;
  }) => (
    <aside data-testid="reader-entity-panel-mock">
      <span data-testid="panel-entity-id">{entityId}</span>
      <button data-testid="panel-close" onClick={onClose}>
        close
      </button>
      <button data-testid="panel-deleted" onClick={onDeleted}>
        deleted
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

// Route the reader GET to the fixture and each correction POST to its success body, so a
// mutation's onSuccess invalidation re-fetches the reader cleanly.
function routeFetch() {
  return vi.fn((input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input);
    const method = init?.method ?? "GET";
    if (method === "POST") {
      if (url.includes("/tags"))
        return Promise.resolve(jsonResponse(200, { mention_id: "m9", entity_id: "e1" }));
      if (url.includes("/suppressions"))
        return Promise.resolve(jsonResponse(200, { suppression_id: "s9" }));
      if (url.includes("/boundaries"))
        return Promise.resolve(jsonResponse(200, { mention_id: "m9" }));
    }
    return Promise.resolve(jsonResponse(200, READER_BODY));
  });
}

function lastCall(fetchMock: ReturnType<typeof routeFetch>, fragment: string) {
  const call = [...fetchMock.mock.calls].reverse().find(([url]) => String(url).includes(fragment));
  if (!call) throw new Error(`no fetch call matched ${fragment}`);
  return { url: String(call[0]), init: (call[1] ?? {}) as RequestInit };
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

    // The highlight is rendered by ReaderEditor (mocked here); its tooltip/colour/offset
    // mapping is covered by decorations.test.ts. The container only needs the highlight present.
    expect(screen.getByTestId("highlight")).toHaveTextContent("Janek");

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

  it("renders the story-scoped undo affordance in the header", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, READER_BODY)),
    );

    renderReader();

    expect(await screen.findByTestId("undo-button")).toBeInTheDocument();
  });

  it("closes the panel when the open entity is deleted", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, READER_BODY)),
    );

    renderReader();

    fireEvent.click(await screen.findByTestId("highlight"));
    expect(screen.getByTestId("reader-entity-panel-mock")).toBeInTheDocument();

    fireEvent.click(screen.getByTestId("panel-deleted"));
    await waitFor(() => expect(screen.queryByTestId("reader-entity-panel-mock")).toBeNull());
  });

  // --- Manual correction (M4.S3c-fe2) --------------------------------------------------------

  it('"not an entity" POSTs a suppression with no entity_id (never a DELETE — ADR 0008 §4)', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderReader();

    fireEvent.click(await screen.findByTestId("ctx-search-highlight"));
    fireEvent.click(await screen.findByTestId("context-not-an-entity"));

    await waitFor(() => {
      const { init } = lastCall(fetchMock, "/suppressions");
      expect(init.method).toBe("POST");
    });
    const { url, init } = lastCall(fetchMock, "/suppressions");
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/paragraphs/p1/suppressions$`));
    expect(JSON.parse(init.body as string)).toEqual({ span_start: 0, span_end: 5 });
    // No DELETE was ever issued for the rejection.
    expect(
      fetchMock.mock.calls.some(([, i]) => (i as RequestInit | undefined)?.method === "DELETE"),
    ).toBe(false);
  });

  it('"not this entity" POSTs a suppression carrying the rejected entity_id', async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderReader();

    fireEvent.click(await screen.findByTestId("ctx-search-highlight"));
    fireEvent.click(await screen.findByTestId("context-not-this"));

    await waitFor(() => expect(lastCall(fetchMock, "/suppressions").init.method).toBe("POST"));
    expect(JSON.parse(lastCall(fetchMock, "/suppressions").init.body as string)).toEqual({
      span_start: 0,
      span_end: 5,
      entity_id: "e1",
    });
  });

  it("re-assign suppresses the wrong entity and re-tags to the picked one (atomic)", async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderReader();

    fireEvent.click(await screen.findByTestId("ctx-search-highlight"));
    fireEvent.click(await screen.findByTestId("context-reassign"));
    fireEvent.click(await screen.findByTestId("entity-picker-pick"));

    await waitFor(() => expect(lastCall(fetchMock, "/suppressions").init.method).toBe("POST"));
    expect(JSON.parse(lastCall(fetchMock, "/suppressions").init.body as string)).toEqual({
      span_start: 0,
      span_end: 5,
      entity_id: "e1",
      retag_to: PICKED_ID,
    });
  });

  it("tags a free selection as an existing entity", async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderReader();

    fireEvent.click(await screen.findByTestId("ctx-selection"));
    // A selection offers only "tag as entity".
    fireEvent.click(await screen.findByTestId("context-tag"));
    fireEvent.click(await screen.findByTestId("entity-picker-pick"));

    await waitFor(() => expect(lastCall(fetchMock, "/tags").init.method).toBe("POST"));
    expect(JSON.parse(lastCall(fetchMock, "/tags").init.body as string)).toEqual({
      span_start: 6,
      span_end: 12,
      entity_id: PICKED_ID,
    });
  });

  it("tags a free selection as a new entity (name pre-filled, open-world type)", async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderReader();

    fireEvent.click(await screen.findByTestId("ctx-selection"));
    fireEvent.click(await screen.findByTestId("context-tag"));
    fireEvent.click(await screen.findByTestId("tag-mode-new"));
    fireEvent.change(screen.getByTestId("new-entity-type"), { target: { value: "place" } });
    fireEvent.click(screen.getByTestId("new-entity-submit"));

    await waitFor(() => expect(lastCall(fetchMock, "/tags").init.method).toBe("POST"));
    expect(JSON.parse(lastCall(fetchMock, "/tags").init.body as string)).toEqual({
      span_start: 6,
      span_end: 12,
      new_entity: { name: "walked", type: "place" },
    });
  });

  it("changes boundaries on a search hit: confirm POSTs old+new span, materialize (no mention_id)", async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderReader();

    fireEvent.click(await screen.findByTestId("ctx-search-highlight"));
    fireEvent.click(await screen.findByTestId("context-change-boundaries"));

    // The banner's Confirm is disabled until a new span is re-selected.
    expect((screen.getByTestId("boundary-confirm") as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByTestId("select-new-span"));
    expect((screen.getByTestId("boundary-confirm") as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByTestId("boundary-confirm"));

    await waitFor(() => expect(lastCall(fetchMock, "/boundaries").init.method).toBe("POST"));
    const body = JSON.parse(lastCall(fetchMock, "/boundaries").init.body as string);
    expect(body).toMatchObject({
      entity_id: "e1",
      old_start: 0,
      old_end: 5,
      new_start: 13,
      new_end: 16,
    });
    // A search hit materializes — no mention_id in the request.
    expect(body.mention_id ?? null).toBeNull();
  });

  it("changes boundaries on a manual span: confirm carries the mention_id (edit in place)", async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderReader();

    fireEvent.click(await screen.findByTestId("ctx-manual-highlight"));
    fireEvent.click(await screen.findByTestId("context-change-boundaries"));
    fireEvent.click(screen.getByTestId("select-new-span"));
    fireEvent.click(screen.getByTestId("boundary-confirm"));

    await waitFor(() => expect(lastCall(fetchMock, "/boundaries").init.method).toBe("POST"));
    expect(JSON.parse(lastCall(fetchMock, "/boundaries").init.body as string).mention_id).toBe(
      "mention-1",
    );
  });

  it("dismisses the context menu without a mutation", async () => {
    const fetchMock = routeFetch();
    vi.stubGlobal("fetch", fetchMock);
    renderReader();

    fireEvent.click(await screen.findByTestId("ctx-search-highlight"));
    expect(screen.getByTestId("reader-context-menu")).toBeInTheDocument();
    fireEvent.keyDown(document, { key: "Escape" });
    await waitFor(() => expect(screen.queryByTestId("reader-context-menu")).toBeNull());
    expect(
      fetchMock.mock.calls.some(([url]) => /suppressions|tags|boundaries/.test(String(url))),
    ).toBe(false);
  });
});
