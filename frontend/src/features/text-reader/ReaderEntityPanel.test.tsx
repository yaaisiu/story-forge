// Tests for the reader entity side panel (Session 35 — M4.S2b).
//
// EgoGraphCanvas (the cytoscape mount) is mocked to a stub that renders a button per
// neighbour — jsdom can't drive a canvas, so the real canvas is covered by the browser
// smoke walk, while this test pins the panel's behaviour: the detail fetch states, the
// properties/aliases rendering, the occurrence timeline derived from the reader's
// paragraphs (DM-SP-3), occurrence drill-down, neighbour navigation, and close.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
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

// Stub the entity picker (its own tests cover the search box): render a button that picks a
// fixed entity, so the relation-add flow is drivable without a live search.
const PICKED_ID = "22222222-2222-2222-2222-222222222222";
vi.mock("../extraction-review/EntityPicker", () => ({
  EntityPicker: ({
    onPick,
  }: {
    onPick: (r: { entity_id: string; canonical_name: string }) => void;
  }) => (
    <button
      data-testid="entity-picker-mock-pick"
      onClick={() => onPick({ entity_id: PICKED_ID, canonical_name: "Marek" })}
    >
      pick
    </button>
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
  language: "en",
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
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const props = {
    storyId: STORY_ID,
    entityId: ENTITY_ID,
    paragraphs: PARAGRAPHS,
    onClose: vi.fn(),
    onDeleted: vi.fn(),
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

// Route a fetch mock by HTTP method so the GET (detail) and the write (PATCH/POST/DELETE)
// can return different bodies and be asserted independently.
function routeFetch(write: (url: string, init: RequestInit) => Response) {
  return vi.fn((url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method === "GET") return Promise.resolve(jsonResponse(200, DETAIL_BODY));
    return Promise.resolve(write(url, init ?? {}));
  });
}

describe("ReaderEntityPanel — entity editing (M4.S3a-fe)", () => {
  it("PATCHes the edited name (project-language slot) and type, then leaves edit mode", async () => {
    const fetchMock = routeFetch(() =>
      jsonResponse(200, { ...DETAIL_BODY, canonical_name: "Elaria", type: "deity" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    fireEvent.click(await screen.findByTestId("reader-entity-edit"));

    fireEvent.change(screen.getByTestId("reader-entity-name-input"), {
      target: { value: "Elaria" },
    });
    fireEvent.change(screen.getByTestId("reader-entity-type-input"), {
      target: { value: "deity" },
    });
    fireEvent.click(screen.getByTestId("reader-entity-save"));

    await waitFor(() => expect(screen.queryByTestId("reader-entity-edit-form")).toBeNull());

    const patchCall = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "PATCH",
    ) as [string, RequestInit];
    expect(patchCall[0]).toMatch(new RegExp(`/stories/${STORY_ID}/entities/${ENTITY_ID}$`));
    const body = JSON.parse(patchCall[1].body as string);
    // language === "en" → the single name field writes the EN slot, not PL.
    expect(body.canonical_name_en).toBe("Elaria");
    expect(body.canonical_name_pl).toBeUndefined();
    expect(body.type).toBe("deity");
    expect(body.aliases).toEqual(["the seer"]);
  });

  it("disables Save when the name is blanked", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );

    renderPanel();
    fireEvent.click(await screen.findByTestId("reader-entity-edit"));
    fireEvent.change(screen.getByTestId("reader-entity-name-input"), { target: { value: "  " } });

    expect(screen.getByTestId("reader-entity-save")).toBeDisabled();
  });

  it("sends a typed property and keeps numbers as numbers", async () => {
    const fetchMock = routeFetch(() => jsonResponse(200, DETAIL_BODY));
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    fireEvent.click(await screen.findByTestId("reader-entity-edit"));

    fireEvent.click(screen.getByTestId("reader-entity-prop-add"));
    const keys = screen.getAllByTestId("reader-entity-prop-key");
    const kinds = screen.getAllByTestId("reader-entity-prop-kind");
    const values = screen.getAllByTestId("reader-entity-prop-value");
    const last = keys.length - 1;
    fireEvent.change(keys[last]!, { target: { value: "age_years" } });
    fireEvent.change(kinds[last]!, { target: { value: "number" } });
    fireEvent.change(values[last]!, { target: { value: "41" } });
    fireEvent.click(screen.getByTestId("reader-entity-save"));

    await waitFor(() => expect(screen.queryByTestId("reader-entity-edit-form")).toBeNull());
    const patchCall = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "PATCH",
    ) as [string, RequestInit];
    const body = JSON.parse(patchCall[1].body as string);
    expect(body.properties.age_years).toBe(41);
  });

  it("surfaces a 400 edit rejection inline and stays in edit mode", async () => {
    const fetchMock = routeFetch(() =>
      jsonResponse(400, { detail: "an entity must keep at least one canonical name" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    fireEvent.click(await screen.findByTestId("reader-entity-edit"));
    fireEvent.click(screen.getByTestId("reader-entity-save"));

    expect(await screen.findByTestId("reader-entity-edit-error")).toHaveTextContent(
      "canonical name",
    );
    expect(screen.getByTestId("reader-entity-edit-form")).toBeInTheDocument();
  });
});

describe("ReaderEntityPanel — delete (M4.S3b-fe)", () => {
  it("deletes the entity after a confirm and calls onDeleted", async () => {
    const fetchMock = routeFetch(() => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    const props = renderPanel();
    await screen.findByTestId("reader-entity-type");

    // First click reveals the confirm; the destructive call only fires on the second.
    fireEvent.click(screen.getByTestId("reader-entity-delete"));
    fireEvent.click(screen.getByTestId("reader-entity-delete-confirm-btn"));

    await waitFor(() => expect(props.onDeleted).toHaveBeenCalled());
    const del = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "DELETE",
    ) as [string, RequestInit];
    expect(del[0]).toMatch(new RegExp(`/stories/${STORY_ID}/entities/${ENTITY_ID}$`));
  });

  it("does not delete when the confirm is cancelled", async () => {
    const fetchMock = routeFetch(() => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    await screen.findByTestId("reader-entity-type");

    fireEvent.click(screen.getByTestId("reader-entity-delete"));
    fireEvent.click(screen.getByTestId("reader-entity-delete-cancel"));

    expect(screen.queryByTestId("reader-entity-delete-confirm")).toBeNull();
    expect(
      fetchMock.mock.calls.some((c) => (c[1] as RequestInit | undefined)?.method === "DELETE"),
    ).toBe(false);
  });
});

describe("ReaderEntityPanel — relation editing (M4.S3a-fe)", () => {
  it("lists relations and removes one via DELETE", async () => {
    const fetchMock = routeFetch(() => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    await screen.findByTestId("reader-entity-type");

    expect(screen.getAllByTestId("reader-relation")).toHaveLength(1);
    fireEvent.click(screen.getByTestId("reader-relation-remove"));

    await waitFor(() => {
      const del = fetchMock.mock.calls.find(
        (c) => (c[1] as RequestInit | undefined)?.method === "DELETE",
      );
      expect(del).toBeDefined();
      expect((del as [string, RequestInit])[0]).toMatch(
        new RegExp(`/stories/${STORY_ID}/relations/e1$`),
      );
    });
  });

  it("adds a relation (this → other) and warns on a merge collision", async () => {
    const fetchMock = routeFetch(() =>
      jsonResponse(200, {
        edge_id: "00000000-0000-0000-0000-0000000000ed",
        merged_into_existing: true,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    await screen.findByTestId("reader-entity-type");

    fireEvent.click(screen.getByTestId("entity-picker-mock-pick"));
    fireEvent.change(screen.getByTestId("reader-relation-predicate"), {
      target: { value: "mentors" },
    });
    fireEvent.click(screen.getByTestId("reader-relation-add"));

    expect(await screen.findByTestId("reader-relation-merged-warning")).toBeInTheDocument();
    const postCall = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "POST",
    ) as [string, RequestInit];
    const body = JSON.parse(postCall[1].body as string);
    expect(body).toEqual({ subject_id: ENTITY_ID, predicate: "mentors", object_id: PICKED_ID });
  });

  it("flips orientation so the focal entity is the object", async () => {
    const fetchMock = routeFetch(() =>
      jsonResponse(200, {
        edge_id: "00000000-0000-0000-0000-0000000000ee",
        merged_into_existing: false,
      }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderPanel();
    await screen.findByTestId("reader-entity-type");

    // The toggle keeps "this"/"other" in place and flips only the arrow direction.
    const orientation = screen.getByTestId("reader-relation-orientation");
    expect(orientation).toHaveTextContent("this → other");
    fireEvent.click(orientation);
    expect(orientation).toHaveTextContent("this ← other");
    fireEvent.click(screen.getByTestId("entity-picker-mock-pick"));
    fireEvent.change(screen.getByTestId("reader-relation-predicate"), {
      target: { value: "employs" },
    });
    fireEvent.click(screen.getByTestId("reader-relation-add"));

    await waitFor(() => {
      const post = fetchMock.mock.calls.find(
        (c) => (c[1] as RequestInit | undefined)?.method === "POST",
      );
      expect(post).toBeDefined();
    });
    const postCall = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "POST",
    ) as [string, RequestInit];
    const body = JSON.parse(postCall[1].body as string);
    expect(body).toEqual({ subject_id: PICKED_ID, predicate: "employs", object_id: ENTITY_ID });
  });
});
