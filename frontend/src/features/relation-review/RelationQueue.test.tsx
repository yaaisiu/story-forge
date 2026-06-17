// Tests for the relation-review queue page container (Session 30 — M3.S4f).
//
// Pins the container's behaviour against a real-fetch stub (the house pattern, cf.
// ReviewQueue.test): loading/empty/error states, a card per committable relation, the
// keyboard scheme driving the decision endpoint, mouse dispatch, and the 409
// already-decided surface. The card + keyboard logic are unit-tested separately.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { RelationQueue } from "./RelationQueue";

const STORY_ID = "00000000-0000-0000-0000-000000000002";

function relation(id: string, over: Record<string, unknown> = {}) {
  return {
    id,
    paragraph_id: "p1",
    subject: `subject-${id}`,
    predicate: "works_at",
    object: `object-${id}`,
    confidence: 0.9,
    subject_entity_id: "e1",
    object_entity_id: "e2",
    ...over,
  };
}

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderQueue() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[`/stories/${STORY_ID}/relations`]}>
        <Routes>
          <Route path="/stories/:storyId/relations" element={<RelationQueue />} />
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

describe("RelationQueue", () => {
  it("renders a card per committable relation, first one selected", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { relations: [relation("r1"), relation("r2")] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();

    const cards = await screen.findAllByTestId("relation-card");
    expect(cards).toHaveLength(2);
    expect(cards[0]).toHaveAttribute("data-selected", "true");
    expect(cards[1]).toHaveAttribute("data-selected", "false");
  });

  it("shows the empty state when nothing is committable", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { relations: [] }));
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();

    expect(await screen.findByTestId("relations-empty")).toBeInTheDocument();
  });

  it("shows an error state when the relations fetch fails", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(503, { detail: "the relation store is unavailable" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();

    expect(await screen.findByTestId("relations-error")).toBeInTheDocument();
  });

  it("J moves the selection to the next card", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { relations: [relation("r1"), relation("r2")] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("relation-card");

    fireEvent.keyDown(screen.getByTestId("relation-queue"), { key: "j" });

    const cards = screen.getAllByTestId("relation-card");
    expect(cards[0]).toHaveAttribute("data-selected", "false");
    expect(cards[1]).toHaveAttribute("data-selected", "true");
  });

  it("A commits the selected relation's edge", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/decide") && init?.method === "POST") {
        return jsonResponse(200, {
          relation_id: "r1",
          status: "written",
          edge_id: "edge-1",
          already_decided: false,
        });
      }
      return jsonResponse(200, { relations: [relation("r1"), relation("r2")] });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("relation-card");

    await act(async () => {
      fireEvent.keyDown(screen.getByTestId("relation-queue"), { key: "a" });
    });

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/r1/decide"));
      expect(call).toBeTruthy();
      const body = JSON.parse((call?.[1] as RequestInit).body as string);
      expect(body).toEqual({ action: "commit" });
    });
  });

  it("clicking a card's Reject posts a reject for that relation", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/decide") && init?.method === "POST") {
        return jsonResponse(200, {
          relation_id: "r2",
          status: "rejected",
          edge_id: null,
          already_decided: false,
        });
      }
      return jsonResponse(200, { relations: [relation("r1"), relation("r2")] });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("relation-card");

    await act(async () => {
      fireEvent.click(screen.getAllByTestId("reject-relation")[1]!);
    });

    await waitFor(() => {
      const call = fetchMock.mock.calls.find(([u]) => String(u).includes("/r2/decide"));
      expect(call).toBeTruthy();
      const body = JSON.parse((call?.[1] as RequestInit).body as string);
      expect(body).toEqual({ action: "reject" });
    });
  });

  // A commit can 409 when an endpoint went stale after the queue loaded (the backend's
  // RelationEndpointsUnresolved — an entity was rejected/merged away). NB: already-decided
  // is NOT a 409; the backend returns 200 + already_decided:true. The card must surface the
  // stale-endpoint meaning, not "already decided".
  it("surfaces a 409 stale-endpoint as an error with the right message", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/decide") && init?.method === "POST") {
        return jsonResponse(409, { detail: "a relation endpoint no longer resolves (stale/held)" });
      }
      return jsonResponse(200, { relations: [relation("r1")] });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("relation-card");

    await act(async () => {
      fireEvent.keyDown(screen.getByTestId("relation-queue"), { key: "a" });
    });

    const banner = await screen.findByTestId("decide-error");
    expect(banner).toHaveTextContent(/no longer available/i);
    expect(banner).not.toHaveTextContent(/already decided/i);
  });

  it("disables only the in-flight relation's actions, not the rest of the queue", async () => {
    let resolveDecide!: (r: Response) => void;
    const decideInFlight = new Promise<Response>((resolve) => {
      resolveDecide = resolve;
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/decide") && init?.method === "POST") return decideInFlight;
      return jsonResponse(200, { relations: [relation("r1"), relation("r2")] });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("relation-card");

    // Commit the selected (first) relation; its request hangs in flight.
    fireEvent.keyDown(screen.getByTestId("relation-queue"), { key: "a" });

    await waitFor(() => expect(screen.getAllByTestId("commit-relation")[0]).toBeDisabled());
    // The other relation stays actionable — the author can keep working.
    expect(screen.getAllByTestId("commit-relation")[1]).not.toBeDisabled();

    await act(async () => {
      resolveDecide(
        jsonResponse(200, {
          relation_id: "r1",
          status: "written",
          edge_id: "edge-1",
          already_decided: false,
        }),
      );
    });
  });

  it("links to the graph viewer", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { relations: [relation("r1")] }));
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("relation-card");

    expect(screen.getByTestId("graph-link")).toHaveAttribute("href", `/stories/${STORY_ID}/graph`);
  });

  it("ignores the keyboard scheme while a text input is the event target", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { relations: [relation("r1"), relation("r2")] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("relation-card");

    const input = document.createElement("input");
    document.body.appendChild(input);
    fireEvent.keyDown(input, { key: "j" });

    const cards = screen.getAllByTestId("relation-card");
    expect(cards[0]).toHaveAttribute("data-selected", "true");
    expect(cards[1]).toHaveAttribute("data-selected", "false");

    document.body.removeChild(input);
  });
});
