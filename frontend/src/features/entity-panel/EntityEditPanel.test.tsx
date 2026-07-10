// Tests for the shared entity edit/inspect panel (Graph-quality S5a). The reader's own
// contract is pinned by ReaderEntityPanel.test.tsx (unchanged, via testIdPrefix="reader-entity");
// this file pins the shared core's behaviour directly with the canvas prefix "node-panel":
// the fetch states, the edit→save PATCH, delete-confirm→onDeleted, the DM-S5-6 guard callbacks
// (onDirtyChange/onEdited), and renderReadExtras.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import type { EntityDetailResponse } from "../../lib/api/useEntityDetail";
import { EntityEditPanel } from "./EntityEditPanel";

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const ENTITY_ID = "11111111-1111-1111-1111-111111111111";

const DETAIL_BODY: EntityDetailResponse = {
  entity_id: ENTITY_ID,
  canonical_name: "Elara",
  language: "en",
  type: "character",
  aliases: ["the seer"],
  properties: { age: 30 },
  ego_graph: { neighbours: [], edges: [] },
};

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

// GET → detail, other methods → the write body.
function routeFetch(write: () => Response) {
  return vi.fn((_url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method === "GET") return Promise.resolve(jsonResponse(200, DETAIL_BODY));
    return Promise.resolve(write());
  });
}

function renderPanel(overrides: Partial<Parameters<typeof EntityEditPanel>[0]> = {}) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const props = {
    storyId: STORY_ID,
    entityId: ENTITY_ID,
    testIdPrefix: "node-panel",
    onClose: vi.fn(),
    onDeleted: vi.fn(),
    onDirtyChange: vi.fn(),
    onEdited: vi.fn(),
    ...overrides,
  };
  render(
    <QueryClientProvider client={queryClient}>
      <EntityEditPanel {...props} />
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

describe("EntityEditPanel", () => {
  it("renders details under the given testId prefix", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );
    renderPanel();

    expect(await screen.findByTestId("node-panel-type")).toHaveTextContent("character");
    expect(screen.getByTestId("node-panel-name")).toHaveTextContent("Elara");
    expect(screen.getByTestId("node-panel-aliases")).toHaveTextContent("the seer");
  });

  it("surfaces a load error", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(404, { detail: "entity not found" })),
    );
    renderPanel();
    expect(await screen.findByTestId("node-panel-error")).toBeInTheDocument();
  });

  it("closes when the close button is clicked", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );
    const props = renderPanel();
    fireEvent.click(await screen.findByTestId("node-panel-close"));
    expect(props.onClose).toHaveBeenCalled();
  });

  it("edits, PATCHes, fires onEdited, and reports dirty transitions to the guard", async () => {
    const fetchMock = routeFetch(() => jsonResponse(200, { ...DETAIL_BODY, type: "deity" }));
    vi.stubGlobal("fetch", fetchMock);
    const props = renderPanel();

    fireEvent.click(await screen.findByTestId("node-panel-edit"));
    // Not dirty yet on entering edit mode.
    expect(props.onDirtyChange).toHaveBeenLastCalledWith(false);

    fireEvent.change(screen.getByTestId("node-panel-type-input"), { target: { value: "deity" } });
    await waitFor(() => expect(props.onDirtyChange).toHaveBeenLastCalledWith(true));

    fireEvent.click(screen.getByTestId("node-panel-save"));
    await waitFor(() => expect(screen.queryByTestId("node-panel-edit-form")).toBeNull());
    expect(props.onEdited).toHaveBeenCalled();

    const patchCall = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "PATCH",
    ) as [string, RequestInit];
    expect(patchCall[0]).toMatch(new RegExp(`/stories/${STORY_ID}/entities/${ENTITY_ID}$`));
    expect(JSON.parse(patchCall[1].body as string).type).toBe("deity");
  });

  it("deletes after a confirm and calls onDeleted", async () => {
    const fetchMock = routeFetch(() => new Response(null, { status: 204 }));
    vi.stubGlobal("fetch", fetchMock);
    const props = renderPanel();

    await screen.findByTestId("node-panel-type");
    fireEvent.click(screen.getByTestId("node-panel-delete"));
    fireEvent.click(screen.getByTestId("node-panel-delete-confirm-btn"));

    await waitFor(() => expect(props.onDeleted).toHaveBeenCalled());
    const del = fetchMock.mock.calls.find(
      (c) => (c[1] as RequestInit | undefined)?.method === "DELETE",
    ) as [string, RequestInit];
    expect(del[0]).toMatch(new RegExp(`/stories/${STORY_ID}/entities/${ENTITY_ID}$`));
  });

  it("renders renderReadExtras in read mode and hides it while editing", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn(async () => jsonResponse(200, DETAIL_BODY)),
    );
    renderPanel({
      renderReadExtras: (d) => <div data-testid="read-extra">extra for {d.canonical_name}</div>,
    });

    expect(await screen.findByTestId("read-extra")).toHaveTextContent("extra for Elara");
    fireEvent.click(screen.getByTestId("node-panel-edit"));
    expect(screen.queryByTestId("read-extra")).toBeNull();
  });
});
