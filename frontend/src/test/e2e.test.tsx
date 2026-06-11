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

// The cytoscape mount can't run in jsdom; stub it so the E2E can walk into the
// graph page and prove the data seam (the canvas itself is browser-smoke territory).
vi.mock("../features/graph-viewer/GraphCanvas", () => ({
  GraphCanvas: ({ graph }: { graph: { nodes: { id: string }[] } }) => (
    <div data-testid="graph-canvas-mock">{graph.nodes.length} nodes</div>
  ),
}));

const { AppShell } = await import("../app/AppShell");

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

const EMPTY_GRAPH = { nodes: [], edges: [] };
const POPULATED_GRAPH = {
  nodes: [
    {
      id: "11111111-1111-1111-1111-111111111111",
      type: "Character",
      canonical_name_pl: "Janek",
      canonical_name_en: null,
      aliases: [],
      first_seen_paragraph_id: null,
    },
  ],
  edges: [],
};
const EXTRACT_BODY = {
  story_id: STORY_ID,
  paragraphs_total: 2,
  paragraphs_done: 2,
  entities_written: 1,
  relations_written: 0,
  paused: false,
  pause_reason: null,
};
const STATUS_BEFORE = {
  daily_budget_usd: 5,
  spent_today_usd: 0,
  remaining_usd: 5,
  gpu_seconds_today: 0,
  calls_today: 0,
  by_task_type: [],
  last_call: null,
};
const STATUS_AFTER = {
  ...STATUS_BEFORE,
  calls_today: 1,
  last_call: {
    task_type: "extraction",
    tier: "cloud_free" as const,
    provider: "OllamaProvider",
    model: "gpt-oss:120b-cloud",
    outcome: "success" as const,
    latency_ms: 842,
    cost_estimate: null,
    gpu_seconds: 3.5,
    created_at: "2026-06-11T09:30:00Z",
  },
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

describe("M2 happy path: upload → outline → graph extraction", () => {
  it("walks from / to a rendered entity graph using the typed client end-to-end", async () => {
    let extracted = false;
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/stories/upload")) return jsonResponse(201, UPLOAD_BODY);
      if (url.includes(`/stories/${STORY_ID}/structure`)) {
        return jsonResponse(201, STRUCTURE_BODY);
      }
      if (url.includes(`/stories/${STORY_ID}/extract`) && init?.method === "POST") {
        extracted = true;
        return jsonResponse(200, EXTRACT_BODY);
      }
      if (url.includes(`/stories/${STORY_ID}/graph`)) {
        return jsonResponse(200, extracted ? POPULATED_GRAPH : EMPTY_GRAPH);
      }
      if (url.includes("/llm/status")) {
        return jsonResponse(200, extracted ? STATUS_AFTER : STATUS_BEFORE);
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

    // 6. Continue to the graph page → empty graph + the agent-activity panel.
    await act(async () => {
      fireEvent.click(screen.getByTestId("outline-continue-graph"));
    });
    expect(await screen.findByTestId("graph-empty")).toBeInTheDocument();
    expect(screen.getByTestId("agent-activity-panel")).toBeInTheDocument();
    // Before any call, the panel shows no recent activity.
    expect(screen.getByTestId("activity-no-calls")).toBeInTheDocument();

    // 7. Run extraction → backend returns 200, the graph refetches and renders the
    //    node, and the panel reflects the call that just ran.
    await act(async () => {
      fireEvent.click(screen.getByTestId("run-extraction"));
    });
    expect(await screen.findByTestId("graph-canvas-mock")).toHaveTextContent("1 nodes");
    expect(await screen.findByTestId("activity-task-type")).toHaveTextContent("extraction");

    // The full seam is wired: upload, structure, extract, and two graph reads all fired.
    const urls = fetchMock.mock.calls.map((c) => String(c[0]));
    expect(urls.some((u) => u.endsWith("/stories/upload"))).toBe(true);
    expect(urls.some((u) => u.includes(`/stories/${STORY_ID}/structure`))).toBe(true);
    expect(urls.some((u) => u.includes(`/stories/${STORY_ID}/extract`))).toBe(true);
    expect(
      urls.filter((u) => u.includes(`/stories/${STORY_ID}/graph`)).length,
    ).toBeGreaterThanOrEqual(2);
  });
});
