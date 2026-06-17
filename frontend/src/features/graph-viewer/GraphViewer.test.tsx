// Tests for the graph-viewer page container (Session 17 — M2.S5).
//
// GraphCanvas (the cytoscape mount) is mocked to a stub that renders a button per
// node — jsdom can't drive a canvas, so the real canvas is covered by the browser
// smoke walk, while this test pins the container's behaviour: empty state, the
// extraction trigger refetching the graph, and node selection opening the details
// panel. The agent-activity panel polls /llm/status, which the fetch stub answers.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the cytoscape mount: render a tappable button per node so selection is drivable.
vi.mock("./GraphCanvas", () => ({
  GraphCanvas: ({
    graph,
    onSelectNode,
  }: {
    graph: { nodes: { id: string }[] };
    onSelectNode: (id: string) => void;
  }) => (
    <div data-testid="graph-canvas-mock">
      {graph.nodes.map((n) => (
        <button key={n.id} data-testid={`cy-node-${n.id}`} onClick={() => onSelectNode(n.id)}>
          {n.id}
        </button>
      ))}
    </div>
  ),
}));

const { GraphViewer } = await import("./GraphViewer");

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const NODE_ID = "11111111-1111-1111-1111-111111111111";

const EMPTY_GRAPH = { nodes: [], edges: [] };
const POPULATED_GRAPH = {
  nodes: [
    {
      id: NODE_ID,
      type: "Character",
      canonical_name_pl: "Janek",
      canonical_name_en: null,
      aliases: ["młynarz"],
      first_seen_paragraph_id: "22222222-2222-2222-2222-222222222222",
    },
  ],
  edges: [],
};
const EXTRACT_RESULT = {
  story_id: STORY_ID,
  paragraphs_total: 2,
  paragraphs_done: 2,
  candidates_staged: 1,
  paused: false,
  pause_reason: null,
};
const STATUS_BODY = {
  daily_budget_usd: 5,
  spent_today_usd: 0,
  remaining_usd: 5,
  gpu_seconds_today: 0,
  calls_today: 0,
  by_task_type: [],
  last_call: null,
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderViewer() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/stories/${STORY_ID}/graph`]}>
        <Routes>
          <Route path="/stories/:storyId/graph" element={<GraphViewer />} />
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

describe("GraphViewer", () => {
  it("shows the empty state for a story with no extracted graph", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/graph")) return jsonResponse(200, EMPTY_GRAPH);
      if (url.includes("/llm/status")) return jsonResponse(200, STATUS_BODY);
      throw new Error(`unexpected url ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderViewer();

    expect(await screen.findByTestId("graph-empty")).toBeInTheDocument();
    expect(screen.getByTestId("run-extraction")).toBeInTheDocument();
  });

  it("runs extraction, refetches, and renders the resulting graph", async () => {
    let graphCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/llm/status")) return jsonResponse(200, STATUS_BODY);
      if (url.includes("/extract") && init?.method === "POST") {
        return jsonResponse(200, EXTRACT_RESULT);
      }
      if (url.includes("/graph")) {
        graphCalls += 1;
        // Empty until extraction has run; populated on the post-extraction refetch.
        return jsonResponse(200, graphCalls === 1 ? EMPTY_GRAPH : POPULATED_GRAPH);
      }
      throw new Error(`unexpected url ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderViewer();
    await screen.findByTestId("graph-empty");

    await act(async () => {
      fireEvent.click(screen.getByTestId("run-extraction"));
    });

    // The graph refetched and the canvas mock rendered the new node.
    await waitFor(() => expect(screen.getByTestId("graph-canvas-mock")).toBeInTheDocument());
    expect(screen.getByTestId(`cy-node-${NODE_ID}`)).toBeInTheDocument();
  });

  it("links to the story's review queue (the Stage-4 human gate)", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/graph")) return jsonResponse(200, EMPTY_GRAPH);
      if (url.includes("/llm/status")) return jsonResponse(200, STATUS_BODY);
      throw new Error(`unexpected url ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderViewer();

    const link = await screen.findByTestId("review-queue-link");
    expect(link).toHaveAttribute("href", `/stories/${STORY_ID}/review`);
  });

  it("links to the story's relation-review queue (the §3.3 decide-relations gate)", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/graph")) return jsonResponse(200, EMPTY_GRAPH);
      if (url.includes("/llm/status")) return jsonResponse(200, STATUS_BODY);
      throw new Error(`unexpected url ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderViewer();

    const link = await screen.findByTestId("relations-link");
    expect(link).toHaveAttribute("href", `/stories/${STORY_ID}/relations`);
  });

  it("opens the node-details panel when a node is tapped", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/graph")) return jsonResponse(200, POPULATED_GRAPH);
      if (url.includes("/llm/status")) return jsonResponse(200, STATUS_BODY);
      throw new Error(`unexpected url ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderViewer();

    const nodeButton = await screen.findByTestId(`cy-node-${NODE_ID}`);
    fireEvent.click(nodeButton);

    expect(await screen.findByTestId("node-details")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Janek" })).toBeInTheDocument();
  });
});
