// Tests for the graph-viewer page container (Session 17 — M2.S5; Session 73 — S2
// navigation filters + search).
//
// GraphCanvas (the cytoscape mount) is mocked to a stub that renders a button per
// *node element* and echoes the focus-ids — jsdom can't drive a canvas, so the real
// canvas (fcose layout, highlight, pan-to) is covered by the browser smoke walk,
// while this test pins the container's behaviour: empty state, extraction refetch,
// node selection, and the client-side type/degree/search navigation (§3.4, DM-GN-4).
// The agent-activity panel polls /llm/status, which the fetch stub answers.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

// Mock the cytoscape mount: render a tappable button per node element (an element is
// a node unless it carries a `source`) and expose the focus-ids so search is drivable.
vi.mock("./GraphCanvas", () => ({
  GraphCanvas: ({
    elements,
    focusNodeIds,
    onSelectNode,
  }: {
    elements: { data: { id: string; source?: string } }[];
    focusNodeIds: string[];
    onSelectNode: (id: string) => void;
  }) => (
    <div data-testid="graph-canvas-mock">
      <span data-testid="focus-ids">{focusNodeIds.join(",")}</span>
      {elements
        .filter((el) => !("source" in el.data))
        .map((el) => (
          <button
            key={el.data.id}
            data-testid={`cy-node-${el.data.id}`}
            onClick={() => onSelectNode(el.data.id)}
          >
            {el.data.id}
          </button>
        ))}
    </div>
  ),
}));

const { GraphViewer } = await import("./GraphViewer");

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const NODE_ID = "11111111-1111-1111-1111-111111111111";

// A single-node graph (kept for the selection / extraction / scope tests).
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

// A multi-type, multi-degree graph for the navigation tests.
// Degrees over its edges: A=2, B=1, C=1.
const CHAR_A = "aaaaaaaa-0000-0000-0000-000000000001";
const LOC_B = "bbbbbbbb-0000-0000-0000-000000000002";
const CHAR_C = "cccccccc-0000-0000-0000-000000000003";
function graphNode(over: Record<string, unknown>) {
  return {
    type: "Character",
    canonical_name_pl: null,
    canonical_name_en: null,
    aliases: [],
    first_seen_paragraph_id: null,
    ...over,
  };
}
const MULTI_GRAPH = {
  nodes: [
    graphNode({ id: CHAR_A, type: "Character", canonical_name_pl: "Janek" }),
    graphNode({ id: LOC_B, type: "Location", canonical_name_pl: "Młyn" }),
    graphNode({ id: CHAR_C, type: "Character", canonical_name_pl: "Zosia" }),
  ],
  edges: [
    { id: "e1", type: "KNOWS", subject_id: CHAR_A, object_id: LOC_B, confidence: 0.9 },
    { id: "e2", type: "KNOWS", subject_id: CHAR_A, object_id: CHAR_C, confidence: 0.9 },
  ],
};
// A Location-only graph — the post-refetch payload for the filter-staleness test.
const LOCATION_ONLY_GRAPH = {
  nodes: [graphNode({ id: LOC_B, type: "Location", canonical_name_pl: "Młyn" })],
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

/** A fetch stub that always answers /llm/status and returns `graphBody` for /graph. */
function stubFetch(graphBody: unknown) {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.includes("/graph")) return jsonResponse(200, graphBody);
    if (url.includes("/llm/status")) return jsonResponse(200, STATUS_BODY);
    throw new Error(`unexpected url ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
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
    stubFetch(EMPTY_GRAPH);
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
    stubFetch(EMPTY_GRAPH);
    renderViewer();

    const link = await screen.findByTestId("review-queue-link");
    expect(link).toHaveAttribute("href", `/stories/${STORY_ID}/review`);
  });

  it("links to the story's relation-review queue (the §3.3 decide-relations gate)", async () => {
    stubFetch(EMPTY_GRAPH);
    renderViewer();

    const link = await screen.findByTestId("relations-link");
    expect(link).toHaveAttribute("href", `/stories/${STORY_ID}/relations`);
  });

  it("links to the story's text reader (the §3.5 inline-highlights view)", async () => {
    stubFetch(EMPTY_GRAPH);
    renderViewer();

    const link = await screen.findByTestId("reader-link");
    expect(link).toHaveAttribute("href", `/stories/${STORY_ID}/reader`);
  });

  it("defaults to the story scope and refetches scope=project when toggled", async () => {
    const graphUrls: string[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = String(input);
      if (url.includes("/graph")) {
        graphUrls.push(url);
        return jsonResponse(200, POPULATED_GRAPH);
      }
      if (url.includes("/llm/status")) return jsonResponse(200, STATUS_BODY);
      throw new Error(`unexpected url ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderViewer();

    // First load uses the default story scope.
    await waitFor(() => expect(graphUrls.length).toBeGreaterThan(0));
    expect(graphUrls[0]).toContain("scope=story");
    expect(screen.getByTestId("scope-story")).toHaveAttribute("aria-pressed", "true");

    // Toggling to the whole project refetches at scope=project.
    fireEvent.click(screen.getByTestId("scope-project"));

    await waitFor(() => expect(graphUrls.some((u) => u.includes("scope=project"))).toBe(true));
    expect(screen.getByTestId("scope-project")).toHaveAttribute("aria-pressed", "true");
  });

  it("clears the open node-details panel when the scope is toggled", async () => {
    stubFetch(POPULATED_GRAPH);
    renderViewer();

    fireEvent.click(await screen.findByTestId(`cy-node-${NODE_ID}`));
    expect(await screen.findByTestId("node-details")).toBeInTheDocument();

    // A node picked in one scope may not exist in the other — toggling resets the
    // selection rather than leaving a stale, blank panel.
    fireEvent.click(screen.getByTestId("scope-project"));

    await waitFor(() => expect(screen.queryByTestId("node-details")).not.toBeInTheDocument());
  });

  it("opens the node-details panel when a node is tapped", async () => {
    stubFetch(POPULATED_GRAPH);
    renderViewer();

    const nodeButton = await screen.findByTestId(`cy-node-${NODE_ID}`);
    fireEvent.click(nodeButton);

    expect(await screen.findByTestId("node-details")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Janek" })).toBeInTheDocument();
  });

  // ── §3.4 client-side navigation (Session 73, S2) ──────────────────────────────

  it("derives the type-filter options from the data present (INV-4)", async () => {
    stubFetch(MULTI_GRAPH);
    renderViewer();

    expect(await screen.findByTestId("type-filter-Character")).toBeInTheDocument();
    expect(screen.getByTestId("type-filter-Location")).toBeInTheDocument();
    // Both node-types render initially (no filter active = all shown).
    expect(screen.getByTestId(`cy-node-${CHAR_A}`)).toBeInTheDocument();
    expect(screen.getByTestId(`cy-node-${LOC_B}`)).toBeInTheDocument();
  });

  it("AND-combines an active type filter — only that type's nodes remain", async () => {
    stubFetch(MULTI_GRAPH);
    renderViewer();

    fireEvent.click(await screen.findByTestId("type-filter-Location"));

    await waitFor(() => expect(screen.queryByTestId(`cy-node-${CHAR_A}`)).not.toBeInTheDocument());
    expect(screen.queryByTestId(`cy-node-${CHAR_C}`)).not.toBeInTheDocument();
    expect(screen.getByTestId(`cy-node-${LOC_B}`)).toBeInTheDocument();
  });

  it("drops nodes below the minimum-connections threshold", async () => {
    stubFetch(MULTI_GRAPH);
    renderViewer();

    // Degrees: A=2, B=1, C=1 → minDegree 2 keeps only A.
    fireEvent.change(await screen.findByTestId("degree-filter"), { target: { value: "2" } });

    await waitFor(() => expect(screen.queryByTestId(`cy-node-${LOC_B}`)).not.toBeInTheDocument());
    expect(screen.queryByTestId(`cy-node-${CHAR_C}`)).not.toBeInTheDocument();
    expect(screen.getByTestId(`cy-node-${CHAR_A}`)).toBeInTheDocument();
  });

  it("shows the match count and a clear-filters affordance when a filter empties the graph", async () => {
    stubFetch(MULTI_GRAPH);
    renderViewer();

    // Location AND degree>=2 → nothing (B is Location but degree 1).
    fireEvent.click(await screen.findByTestId("type-filter-Location"));
    fireEvent.change(screen.getByTestId("degree-filter"), { target: { value: "2" } });

    expect(await screen.findByTestId("graph-no-match")).toBeInTheDocument();
    expect(screen.queryByTestId("graph-canvas-mock")).not.toBeInTheDocument();

    // Clearing restores the full graph.
    fireEvent.click(screen.getByTestId("clear-filters"));
    await waitFor(() => expect(screen.getByTestId("graph-canvas-mock")).toBeInTheDocument());
    expect(screen.getByTestId("graph-match-count")).toHaveTextContent("3 of 3 entities");
  });

  it("clears the selection when a filter hides the selected node", async () => {
    stubFetch(MULTI_GRAPH);
    renderViewer();

    fireEvent.click(await screen.findByTestId(`cy-node-${CHAR_A}`));
    expect(await screen.findByTestId("node-details")).toBeInTheDocument();

    // Filtering to Location hides the selected Character A → the panel closes.
    fireEvent.click(screen.getByTestId("type-filter-Location"));

    await waitFor(() => expect(screen.queryByTestId("node-details")).not.toBeInTheDocument());
  });

  it("focuses a search match (past the debounce)", async () => {
    stubFetch(MULTI_GRAPH);
    renderViewer();

    fireEvent.change(await screen.findByTestId("node-search"), { target: { value: "zosia" } });

    // The debounced term reaches matchNodes → the mock echoes the matched id.
    await waitFor(() => expect(screen.getByTestId("focus-ids")).toHaveTextContent(CHAR_C));
  });

  it("reports a search match hidden by an active filter", async () => {
    stubFetch(MULTI_GRAPH);
    renderViewer();

    // Hide the Characters, then search for one — the match exists but is filtered out.
    fireEvent.click(await screen.findByTestId("type-filter-Location"));
    fireEvent.change(screen.getByTestId("node-search"), { target: { value: "zosia" } });

    expect(await screen.findByTestId("graph-search-hidden")).toBeInTheDocument();
    expect(screen.getByTestId("focus-ids")).toHaveTextContent("");
  });

  it("prunes a selected type that a refetch removed (no blank graph)", async () => {
    let graphCalls = 0;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/llm/status")) return jsonResponse(200, STATUS_BODY);
      if (url.includes("/extract") && init?.method === "POST") {
        return jsonResponse(200, EXTRACT_RESULT);
      }
      if (url.includes("/graph")) {
        graphCalls += 1;
        // Character+Location first; Location-only after the extraction refetch.
        return jsonResponse(200, graphCalls === 1 ? MULTI_GRAPH : LOCATION_ONLY_GRAPH);
      }
      throw new Error(`unexpected url ${url}`);
    });
    vi.stubGlobal("fetch", fetchMock);

    renderViewer();

    // Select Character, then refetch a payload that no longer has that type.
    fireEvent.click(await screen.findByTestId("type-filter-Character"));
    await waitFor(() => expect(screen.queryByTestId(`cy-node-${LOC_B}`)).not.toBeInTheDocument());

    await act(async () => {
      fireEvent.click(screen.getByTestId("run-extraction"));
    });

    // The now-absent Character option is gone and the graph is NOT blank — the
    // Location node shows (the pruned filter no longer constrains it to nothing).
    await waitFor(() =>
      expect(screen.queryByTestId("type-filter-Character")).not.toBeInTheDocument(),
    );
    expect(screen.getByTestId(`cy-node-${LOC_B}`)).toBeInTheDocument();
    expect(screen.queryByTestId("graph-no-match")).not.toBeInTheDocument();
  });
});
