// Tests for the reader entity side panel (Session 35 — M4.S2b).
//
// EgoGraphCanvas (the cytoscape mount) is mocked to a stub that renders a button per
// neighbour — jsdom can't drive a canvas, so the real canvas is covered by the browser
// smoke walk, while this test pins the panel's behaviour: the detail fetch states, the
// properties/aliases rendering, the occurrence timeline derived from the reader's
// paragraphs (DM-SP-3), occurrence drill-down, neighbour navigation, and close.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Stub the cytoscape mount: render a tappable button per neighbour so navigation is drivable.
vi.mock("./EgoGraphCanvas", () => ({
  EgoGraphCanvas: ({
    detail,
    onSelectNeighbour,
  }: {
    detail: { ego_graph: { neighbours?: { entity_id: string }[] } };
    onSelectNeighbour: (id: string) => void;
  }) => (
    <div data-testid="ego-graph-canvas-mock">
      {(detail.ego_graph.neighbours ?? []).map((n) => (
        <button
          key={n.entity_id}
          data-testid={`ego-node-${n.entity_id}`}
          onClick={() => onSelectNeighbour(n.entity_id)}
        >
          {n.entity_id}
        </button>
      ))}
    </div>
  ),
}));

const { ReaderEntityPanel } = await import("./ReaderEntityPanel");

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const ENTITY_ID = "11111111-1111-1111-1111-111111111111";

const PARAGRAPHS = [
  {
    id: "p1",
    text: "Elara walked to the mill.",
    highlights: [{ start: 0, end: 5, entity_id: ENTITY_ID, type: "character" }],
  },
  { id: "p2", text: "It was quiet.", highlights: [] },
  {
    id: "p3",
    text: "Marek met Elara there.",
    highlights: [{ start: 10, end: 15, entity_id: ENTITY_ID, type: "character" }],
  },
];

const DETAIL_BODY = {
  entity_id: ENTITY_ID,
  canonical_name: "Elara",
  type: "character",
  aliases: ["the seer"],
  properties: { age: "30", role: "protagonist" },
  ego_graph: {
    neighbours: [{ entity_id: "n1", type: "character", canonical_name_pl: "Marek" }],
    edges: [{ id: "e1", type: "knows", direction: "out", neighbour_id: "n1", confidence: 0.9 }],
  },
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderPanel(overrides: Partial<Parameters<typeof ReaderEntityPanel>[0]> = {}) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const props = {
    storyId: STORY_ID,
    entityId: ENTITY_ID,
    paragraphs: PARAGRAPHS,
    onClose: vi.fn(),
    onSelectEntity: vi.fn(),
    onNavigateToOccurrence: vi.fn(),
    ...overrides,
  };
  render(
    <QueryClientProvider client={queryClient}>
      <ReaderEntityPanel {...props} />
    </QueryClientProvider>,
  );
  return props;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ReaderEntityPanel", () => {
  it("renders the entity's name, type, aliases, and properties", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );

    renderPanel();

    expect(await screen.findByTestId("reader-entity-type")).toHaveTextContent("character");
    expect(screen.getByTestId("reader-entity-name")).toHaveTextContent("Elara");
    expect(screen.getByTestId("reader-entity-aliases")).toHaveTextContent("the seer");
    const props = screen.getByTestId("reader-entity-properties");
    expect(props).toHaveTextContent("age");
    expect(props).toHaveTextContent("30");
    expect(props).toHaveTextContent("role");
    expect(props).toHaveTextContent("protagonist");
  });

  it("shows 'none' when there are no properties", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, { ...DETAIL_BODY, properties: {} })),
    );

    renderPanel();

    await screen.findByTestId("reader-entity-type");
    expect(screen.getByTestId("reader-entity-properties")).toHaveTextContent("none");
  });

  it("lists occurrences derived from the reader's highlights, in document order", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );

    renderPanel();

    await screen.findByTestId("reader-entity-type");
    const occurrences = screen.getAllByTestId("occurrence");
    expect(occurrences).toHaveLength(2);
    expect(occurrences[0]).toHaveAttribute("data-paragraph-id", "p1");
    expect(occurrences[1]).toHaveAttribute("data-paragraph-id", "p3");
  });

  it("drills an occurrence back to its paragraph", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );

    const props = renderPanel();

    await screen.findByTestId("reader-entity-type");
    fireEvent.click(screen.getAllByTestId("occurrence")[1]!);
    expect(props.onNavigateToOccurrence).toHaveBeenCalledWith("p3");
  });

  it("navigates to a neighbour tapped in the mini-graph", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );

    const props = renderPanel();

    await screen.findByTestId("reader-entity-type");
    fireEvent.click(screen.getByTestId("ego-node-n1"));
    expect(props.onSelectEntity).toHaveBeenCalledWith("n1");
  });

  it("shows the empty occurrences state for an entity not highlighted in this story", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );

    // A neighbour entity whose id never appears in PARAGRAPHS' highlights.
    renderPanel({ entityId: "n1" });

    await screen.findByTestId("reader-entity-type");
    expect(screen.getByTestId("reader-entity-occurrences-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("occurrence")).toBeNull();
  });

  it("surfaces a load error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(404, { detail: "entity not found" })),
    );

    renderPanel();

    expect(await screen.findByTestId("reader-entity-error")).toBeInTheDocument();
  });

  it("closes when the close button is clicked", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );

    const props = renderPanel();

    fireEvent.click(screen.getByTestId("reader-entity-close"));
    expect(props.onClose).toHaveBeenCalled();
  });
});
