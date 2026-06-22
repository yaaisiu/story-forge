// Tests for the reader panel's merge affordance (Session 43 — M4.S3b-fe).
//
// EntityPicker is stubbed (its own tests cover the search box) to two buttons: pick the absorbed
// entity, or pick the survivor itself (to exercise the self-merge guard). The conflict resolver is
// driven by the absorbed entity's GET detail vs the survivor's props passed in. Pins: a property
// conflict surfaces with both values, the chosen side flows into resolved_properties, a clean merge
// sends {} resolved, the self-merge is blocked client-side, and a backend rejection shows inline.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const SURVIVOR_ID = "11111111-1111-1111-1111-111111111111";
const ABSORBED_ID = "22222222-2222-2222-2222-222222222222";

vi.mock("../extraction-review/EntityPicker", () => ({
  EntityPicker: ({
    onPick,
  }: {
    onPick: (r: { entity_id: string; canonical_name: string }) => void;
  }) => (
    <div>
      <button
        data-testid="pick-absorbed"
        onClick={() => onPick({ entity_id: ABSORBED_ID, canonical_name: "Broniek" })}
      >
        pick absorbed
      </button>
      <button
        data-testid="pick-self"
        onClick={() => onPick({ entity_id: SURVIVOR_ID, canonical_name: "Bronisław" })}
      >
        pick self
      </button>
    </div>
  ),
}));

const { MergeControls } = await import("./MergeControls");

function absorbedDetail(properties: Record<string, unknown>) {
  return {
    entity_id: ABSORBED_ID,
    canonical_name: "Broniek",
    language: "pl",
    type: "character",
    aliases: [],
    properties,
    ego_graph: { neighbours: [], edges: [] },
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

const SUMMARY = {
  survivor_entity_id: SURVIVOR_ID,
  repointed_count: 2,
  folded_count: 1,
  self_loops_dropped: 0,
  mentions_repointed: 3,
};

// Route by method: GET → the absorbed entity's detail; POST → the merge write.
function routeFetch(absorbedProps: Record<string, unknown>, write: () => Response) {
  return vi.fn((_url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method === "GET") return Promise.resolve(jsonResponse(200, absorbedDetail(absorbedProps)));
    return Promise.resolve(write());
  });
}

function renderControls(survivorProperties: Record<string, unknown> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <MergeControls
        storyId={STORY_ID}
        survivorId={SURVIVOR_ID}
        survivorName="Bronisław"
        survivorProperties={survivorProperties}
      />
    </QueryClientProvider>,
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("MergeControls", () => {
  it("opens the merge UI from the collapsed button", () => {
    vi.stubGlobal(
      "fetch",
      routeFetch({}, () => jsonResponse(200, SUMMARY)),
    );
    renderControls();
    expect(screen.queryByTestId("merge-controls")).toBeNull();
    fireEvent.click(screen.getByTestId("reader-entity-merge"));
    expect(screen.getByTestId("merge-controls")).toBeInTheDocument();
  });

  it("surfaces a property conflict with both values and merges keeping the survivor's by default", async () => {
    const fetchMock = routeFetch({ age: 41 }, () => jsonResponse(200, SUMMARY));
    vi.stubGlobal("fetch", fetchMock);
    renderControls({ age: 40 });

    fireEvent.click(screen.getByTestId("reader-entity-merge"));
    fireEvent.click(screen.getByTestId("pick-absorbed"));

    // The conflict row appears once the absorbed detail loads.
    const conflict = await screen.findByTestId("merge-conflict");
    expect(conflict).toHaveTextContent("age");
    expect(conflict).toHaveTextContent("40");
    expect(conflict).toHaveTextContent("41");

    fireEvent.click(screen.getByTestId("merge-confirm"));

    expect(await screen.findByTestId("merge-summary")).toHaveTextContent("re-pointed");
    const post = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "POST",
    ) as [string, RequestInit];
    expect(post[0]).toMatch(new RegExp(`/stories/${STORY_ID}/entities/${ABSORBED_ID}/merge$`));
    const body = JSON.parse(post[1].body as string);
    expect(body).toEqual({ target_entity_id: SURVIVOR_ID, resolved_properties: { age: 40 } });
  });

  it("sends the absorbed value when the author picks it", async () => {
    const fetchMock = routeFetch({ age: 41 }, () => jsonResponse(200, SUMMARY));
    vi.stubGlobal("fetch", fetchMock);
    renderControls({ age: 40 });

    fireEvent.click(screen.getByTestId("reader-entity-merge"));
    fireEvent.click(screen.getByTestId("pick-absorbed"));
    await screen.findByTestId("merge-conflict");
    fireEvent.click(screen.getByTestId("merge-keep-absorbed"));
    fireEvent.click(screen.getByTestId("merge-confirm"));

    await screen.findByTestId("merge-summary");
    const post = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "POST",
    ) as [string, RequestInit];
    expect(JSON.parse(post[1].body as string).resolved_properties).toEqual({ age: 41 });
  });

  it("merges with empty resolved_properties when there is no conflict", async () => {
    const fetchMock = routeFetch({ home: "Oakhaven" }, () => jsonResponse(200, SUMMARY));
    vi.stubGlobal("fetch", fetchMock);
    renderControls({ age: 40 });

    fireEvent.click(screen.getByTestId("reader-entity-merge"));
    fireEvent.click(screen.getByTestId("pick-absorbed"));
    // Wait for the absorbed detail to load (the absorbed-name confirms the pick resolved).
    await waitFor(() => expect(screen.getByTestId("merge-confirm")).toBeEnabled());
    expect(screen.queryByTestId("merge-conflict")).toBeNull();
    fireEvent.click(screen.getByTestId("merge-confirm"));

    await screen.findByTestId("merge-summary");
    const post = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "POST",
    ) as [string, RequestInit];
    expect(JSON.parse(post[1].body as string).resolved_properties).toEqual({});
  });

  it("blocks a self-merge client-side", async () => {
    const fetchMock = routeFetch({}, () => jsonResponse(200, SUMMARY));
    vi.stubGlobal("fetch", fetchMock);
    renderControls();

    fireEvent.click(screen.getByTestId("reader-entity-merge"));
    fireEvent.click(screen.getByTestId("pick-self"));

    expect(await screen.findByTestId("merge-self-warning")).toBeInTheDocument();
    expect(screen.getByTestId("merge-confirm")).toBeDisabled();
  });

  it("surfaces a backend rejection inline", async () => {
    const fetchMock = routeFetch({}, () =>
      jsonResponse(409, { detail: "cannot merge an entity into itself" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderControls();

    fireEvent.click(screen.getByTestId("reader-entity-merge"));
    fireEvent.click(screen.getByTestId("pick-absorbed"));
    await waitFor(() => expect(screen.getByTestId("merge-confirm")).toBeEnabled());
    fireEvent.click(screen.getByTestId("merge-confirm"));

    expect(await screen.findByTestId("merge-error")).toHaveTextContent("cannot merge");
  });
});
