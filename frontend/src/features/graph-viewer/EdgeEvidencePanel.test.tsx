// Tests for the edge side panel (Session 76 — S3b read; extended Session 83 — S5b-fe edit).
//
// Read: each state — no selection, loading, error, populated (predicate + source quote),
// the zero-provenance "added manually" affordance, close. Edit: the Edit affordance,
// re-predicate → PATCH + onEdited(newId, merged) + onDirtyChange, re-target via the picker,
// delete-confirm → DELETE + onDeleted, and the folded-onto-existing note.
//
// EntityPicker is mocked to a single pick button so the panel's re-target wiring is tested
// without the picker's own search/debounce (it has its own tests) — the TextReader pattern.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { EdgeEvidencePanel } from "./EdgeEvidencePanel";
import type { EdgeEvidence } from "../../lib/api/useEdgeEvidence";
import type { GraphEdge } from "../../lib/api/useStoryGraph";

const PICKED_ID = "99999999-9999-9999-9999-999999999999";

vi.mock("../extraction-review/EntityPicker", () => ({
  EntityPicker: ({
    onPick,
  }: {
    onPick: (r: { entity_id: string; canonical_name: string }) => void;
  }) => (
    <button
      type="button"
      data-testid="entity-picker-pick"
      onClick={() => onPick({ entity_id: PICKED_ID, canonical_name: "Bram" })}
    >
      pick Bram
    </button>
  ),
}));

const STORY_ID = "00000000-0000-0000-0000-000000000002";
const EDGE_ID = "33333333-3333-3333-3333-333333333333";
const NEW_EDGE_ID = "55555555-5555-5555-5555-555555555555";

const EDGE: GraphEdge = {
  id: EDGE_ID,
  type: "TRAVELS_WITH",
  subject_id: "s1",
  object_id: "o1",
  confidence: 1,
};

const EVIDENCE: EdgeEvidence = {
  predicate: "TRAVELS_WITH",
  source_provenance: [
    {
      paragraph_id: "44444444-4444-4444-4444-444444444444",
      paragraph_text: "Janek and Katarzyna left the mill together at dawn.",
      evidence_quote: "left the mill together",
    },
  ],
};

const NAMES: Record<string, string> = { s1: "Janek", o1: "Katarzyna" };
const nameOf = (id: string): string => NAMES[id] ?? id;

/** A method-routed fetch: PATCH → the retarget response, DELETE → 204, else 200 {}. */
function routeFetch(patch: { edge_id: string; merged_into_existing: boolean }) {
  return vi.fn((_url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET";
    if (method === "PATCH") {
      return Promise.resolve(
        new Response(JSON.stringify(patch), {
          status: 200,
          headers: { "Content-Type": "application/json" },
        }),
      );
    }
    if (method === "DELETE") return Promise.resolve(new Response(null, { status: 204 }));
    return Promise.resolve(new Response(JSON.stringify({}), { status: 200 }));
  });
}

function renderPanel(over: Partial<Parameters<typeof EdgeEvidencePanel>[0]> = {}) {
  const onClose = vi.fn();
  const onRetry = vi.fn();
  const onDeleted = vi.fn();
  const onDirtyChange = vi.fn();
  const onEdited = vi.fn();
  const queryClient = new QueryClient({
    defaultOptions: { mutations: { retry: false }, queries: { retry: false } },
  });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  render(
    <EdgeEvidencePanel
      edgeId={EDGE_ID}
      edge={EDGE}
      nameOf={nameOf}
      storyId={STORY_ID}
      evidence={EVIDENCE}
      isPending={false}
      onRetry={onRetry}
      onClose={onClose}
      onDeleted={onDeleted}
      onDirtyChange={onDirtyChange}
      onEdited={onEdited}
      {...over}
    />,
    { wrapper },
  );
  return { onClose, onRetry, onDeleted, onDirtyChange, onEdited };
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("EdgeEvidencePanel — read (S3b)", () => {
  it("prompts to select an edge when none is selected", () => {
    renderPanel({ edgeId: null });
    expect(screen.getByTestId("edge-evidence-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("edge-evidence")).not.toBeInTheDocument();
  });

  it("shows a loading state while the evidence is in flight", () => {
    renderPanel({ isPending: true, evidence: undefined });
    expect(screen.getByTestId("edge-evidence-loading")).toBeInTheDocument();
  });

  it("shows an error state with a working Retry when the read fails with no data", () => {
    const { onRetry } = renderPanel({ evidence: undefined });
    expect(screen.getByTestId("edge-evidence-error")).toBeInTheDocument();
    fireEvent.click(screen.getByTestId("edge-evidence-retry"));
    expect(onRetry).toHaveBeenCalledOnce();
  });

  it("keeps the last-good evidence visible when a background refetch fails (no blanking)", () => {
    renderPanel({ isPending: false, evidence: EVIDENCE });
    expect(screen.getByTestId("edge-evidence")).toBeInTheDocument();
    expect(screen.queryByTestId("edge-evidence-error")).not.toBeInTheDocument();
  });

  it("renders the predicate and each source paragraph with its quote", () => {
    renderPanel();
    expect(screen.getByTestId("edge-evidence-predicate")).toHaveTextContent("TRAVELS_WITH");
    const sources = screen.getAllByTestId("edge-evidence-source");
    expect(sources).toHaveLength(1);
    expect(sources[0]).toHaveTextContent("left the mill together");
  });

  it("says 'added manually' for a zero-provenance edge instead of an empty/broken panel", () => {
    renderPanel({ evidence: { predicate: "KNOWS", source_provenance: [] } });
    expect(screen.getByTestId("edge-evidence-none")).toHaveTextContent(/added manually/i);
  });

  it("tolerates a null predicate", () => {
    renderPanel({ evidence: { predicate: null, source_provenance: [] } });
    expect(screen.getByTestId("edge-evidence-predicate")).toHaveTextContent(/unknown/i);
  });

  it("dispatches onClose from the close button", () => {
    const { onClose } = renderPanel();
    fireEvent.click(screen.getByTestId("edge-evidence-close"));
    expect(onClose).toHaveBeenCalledOnce();
  });

  it("hides the curation affordances until the edge resolves in the payload", () => {
    renderPanel({ edge: undefined });
    expect(screen.queryByTestId("edge-panel-edit")).not.toBeInTheDocument();
    expect(screen.queryByTestId("edge-panel-delete")).not.toBeInTheDocument();
  });
});

describe("EdgeEvidencePanel — edit (S5b-fe)", () => {
  it("offers Edit and Delete on a resolved edge", () => {
    renderPanel();
    expect(screen.getByTestId("edge-panel-edit")).toBeInTheDocument();
    expect(screen.getByTestId("edge-panel-delete")).toBeInTheDocument();
  });

  it("re-predicates the edge: PATCHes the change and re-points via onEdited", async () => {
    const fetchMock = routeFetch({ edge_id: NEW_EDGE_ID, merged_into_existing: false });
    vi.stubGlobal("fetch", fetchMock);
    const { onEdited, onDirtyChange } = renderPanel();

    fireEvent.click(screen.getByTestId("edge-panel-edit"));
    const input = screen.getByTestId("edge-panel-predicate");
    expect(input).toHaveValue("TRAVELS_WITH");
    fireEvent.change(input, { target: { value: "RIDES_WITH" } });

    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(true));
    fireEvent.click(screen.getByTestId("edge-panel-save"));

    await waitFor(() => expect(onEdited).toHaveBeenCalledWith(NEW_EDGE_ID, false));
    const patchCall = fetchMock.mock.calls.find(
      ([, init]) => (init as RequestInit)?.method === "PATCH",
    );
    expect(patchCall).toBeDefined();
    const [url, init] = patchCall as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/relations/${EDGE_ID}$`));
    expect(JSON.parse(init.body as string)).toEqual({ predicate: "RIDES_WITH" });
  });

  it("re-targets an endpoint via the picker and PATCHes the new object_id", async () => {
    const fetchMock = routeFetch({ edge_id: NEW_EDGE_ID, merged_into_existing: false });
    vi.stubGlobal("fetch", fetchMock);
    const { onEdited } = renderPanel();

    fireEvent.click(screen.getByTestId("edge-panel-edit"));
    // Current object endpoint shows its name; "change" opens the (mocked) picker.
    expect(screen.getByTestId("edge-panel-endpoint-object")).toHaveTextContent("Katarzyna");
    fireEvent.click(screen.getByTestId("edge-panel-retarget-object"));
    fireEvent.click(screen.getByTestId("entity-picker-pick"));

    fireEvent.click(screen.getByTestId("edge-panel-save"));

    await waitFor(() => expect(onEdited).toHaveBeenCalledWith(NEW_EDGE_ID, false));
    const [, init] = fetchMock.mock.calls.find(
      ([, i]) => (i as RequestInit)?.method === "PATCH",
    ) as [string, RequestInit];
    expect(JSON.parse(init.body as string)).toEqual({ object_id: PICKED_ID });
  });

  it("disables Save until something changes and when the predicate is blanked", () => {
    renderPanel();
    fireEvent.click(screen.getByTestId("edge-panel-edit"));
    expect(screen.getByTestId("edge-panel-save")).toBeDisabled();

    fireEvent.change(screen.getByTestId("edge-panel-predicate"), {
      target: { value: "RIDES_WITH" },
    });
    expect(screen.getByTestId("edge-panel-save")).toBeEnabled();

    fireEvent.change(screen.getByTestId("edge-panel-predicate"), { target: { value: "   " } });
    expect(screen.getByTestId("edge-panel-save")).toBeDisabled();
  });

  it("Cancel leaves edit mode without a write", () => {
    const fetchMock = routeFetch({ edge_id: NEW_EDGE_ID, merged_into_existing: false });
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();
    fireEvent.click(screen.getByTestId("edge-panel-edit"));
    fireEvent.click(screen.getByTestId("edge-panel-cancel"));
    expect(screen.queryByTestId("edge-panel-edit-form")).not.toBeInTheDocument();
    expect(screen.getByTestId("edge-evidence")).toBeInTheDocument();
    expect(fetchMock).not.toHaveBeenCalled();
  });

  it("deletes the edge on confirm and reports onDeleted", async () => {
    const fetchMock = routeFetch({ edge_id: NEW_EDGE_ID, merged_into_existing: false });
    vi.stubGlobal("fetch", fetchMock);
    const { onDeleted } = renderPanel();

    fireEvent.click(screen.getByTestId("edge-panel-delete"));
    fireEvent.click(screen.getByTestId("edge-panel-delete-confirm-btn"));

    await waitFor(() => expect(onDeleted).toHaveBeenCalledOnce());
    const [url, init] = fetchMock.mock.calls[0] as [string, RequestInit];
    expect(url).toMatch(new RegExp(`/stories/${STORY_ID}/relations/${EDGE_ID}$`));
    expect(init.method).toBe("DELETE");
  });

  it("surfaces a fold from the previous edit as an amber note", () => {
    renderPanel({ justMerged: true });
    expect(screen.getByTestId("edge-panel-merged-warning")).toHaveTextContent(/folded/i);
  });

  it("surfaces a PATCH error inline", async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ detail: "relation not found" }), {
        status: 404,
        headers: { "Content-Type": "application/json" },
      }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderPanel();

    fireEvent.click(screen.getByTestId("edge-panel-edit"));
    fireEvent.change(screen.getByTestId("edge-panel-predicate"), {
      target: { value: "RIDES_WITH" },
    });
    fireEvent.click(screen.getByTestId("edge-panel-save"));

    await waitFor(() =>
      expect(screen.getByTestId("edge-panel-edit-error")).toHaveTextContent("relation not found"),
    );
  });
});
