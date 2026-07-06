// Tests for the review-queue page container (Session 25 — M3.S4b Stage 4).
//
// Pins the container's behaviour against a real-fetch stub (the house pattern, cf.
// GraphViewer.test): loading/empty/error states, a card per staged candidate, the
// §8.3 keyboard scheme driving the decision endpoints, mouse dispatch, and the 409
// stale-merge-target surface. The cards + keyboard logic are unit-tested separately.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ReviewQueue } from "./ReviewQueue";

const STORY_ID = "00000000-0000-0000-0000-000000000002";

function candidate(id: string, over: Record<string, unknown> = {}) {
  return {
    id,
    paragraph_id: "p1",
    candidate_name: `Name-${id}`,
    type: "Character",
    context: `context for ${id}`,
    proposal: "merge",
    target_entity_id: "e1",
    target_canonical_name: "Jan",
    stage_reached: 3,
    confidence: 0.9,
    reasoning: "because",
    alternatives: [
      {
        entity_id: "e1",
        canonical_name: "Jan",
        score: 91,
        type: "Character",
        aliases: [],
        context_quote: null,
      },
      {
        entity_id: "e2",
        canonical_name: "Janusz",
        score: 70,
        type: "Character",
        aliases: [],
        context_quote: null,
      },
    ],
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
      <MemoryRouter initialEntries={[`/stories/${STORY_ID}/review`]}>
        <Routes>
          <Route path="/stories/:storyId/review" element={<ReviewQueue />} />
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

describe("ReviewQueue", () => {
  it("renders a card per staged candidate, first one selected", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { candidates: [candidate("c1"), candidate("c2")] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();

    const cards = await screen.findAllByTestId("candidate-card");
    expect(cards).toHaveLength(2);
    expect(cards[0]).toHaveAttribute("data-selected", "true");
    expect(cards[1]).toHaveAttribute("data-selected", "false");
  });

  it("shows the empty state when nothing is pending", async () => {
    const fetchMock = vi.fn(async () => jsonResponse(200, { candidates: [] }));
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();

    expect(await screen.findByTestId("queue-empty")).toBeInTheDocument();
  });

  it("shows an error state when the queue fetch fails", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(503, { detail: "the staging store is unavailable" }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();

    expect(await screen.findByTestId("queue-error")).toBeInTheDocument();
  });

  it("J moves the selection to the next card", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { candidates: [candidate("c1"), candidate("c2")] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("candidate-card");

    fireEvent.keyDown(screen.getByTestId("review-queue"), { key: "j" });

    const cards = screen.getAllByTestId("candidate-card");
    expect(cards[0]).toHaveAttribute("data-selected", "false");
    expect(cards[1]).toHaveAttribute("data-selected", "true");
  });

  it("A accepts the selected candidate's cascade proposal", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/accept") && init?.method === "POST") {
        return jsonResponse(200, {
          candidate_id: "c1",
          status: "merged",
          entity_id: "e1",
          already_decided: false,
        });
      }
      return jsonResponse(200, { candidates: [candidate("c1"), candidate("c2")] });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("candidate-card");

    await act(async () => {
      fireEvent.keyDown(screen.getByTestId("review-queue"), { key: "a" });
    });

    await waitFor(() => {
      const acceptCall = fetchMock.mock.calls.find(([u]) => String(u).includes("/c1/accept"));
      expect(acceptCall).toBeTruthy();
    });
  });

  it("clicking a card's Reject posts a reject for that candidate", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/reject") && init?.method === "POST") {
        return jsonResponse(200, {
          candidate_id: "c2",
          status: "rejected",
          entity_id: null,
          already_decided: false,
        });
      }
      return jsonResponse(200, { candidates: [candidate("c1"), candidate("c2")] });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("candidate-card");

    await act(async () => {
      fireEvent.click(screen.getAllByTestId("reject")[1]!);
    });

    await waitFor(() => {
      const rejectCall = fetchMock.mock.calls.find(([u]) => String(u).includes("/c2/reject"));
      expect(rejectCall).toBeTruthy();
    });
  });

  it("M then Enter accepts-as-merge to the picked alternative", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/accept") && init?.method === "POST") {
        return jsonResponse(200, {
          candidate_id: "c1",
          status: "merged",
          entity_id: "e1",
          already_decided: false,
        });
      }
      return jsonResponse(200, { candidates: [candidate("c1")] });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("candidate-card");
    const queue = screen.getByTestId("review-queue");

    fireEvent.keyDown(queue, { key: "m" }); // pick first alternative (e1)
    await act(async () => {
      fireEvent.keyDown(queue, { key: "Enter" });
    });

    await waitFor(() => {
      const acceptCall = fetchMock.mock.calls.find(([u]) => String(u).includes("/c1/accept"));
      expect(acceptCall).toBeTruthy();
      const body = JSON.parse((acceptCall?.[1] as RequestInit).body as string);
      expect(body).toEqual({ action: "merge", target_entity_id: "e1" });
    });
  });

  it("surfaces a 409 stale-merge-target as an error", async () => {
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/accept") && init?.method === "POST") {
        return jsonResponse(409, { detail: "merge target no longer exists" });
      }
      return jsonResponse(200, { candidates: [candidate("c1")] });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("candidate-card");

    await act(async () => {
      fireEvent.keyDown(screen.getByTestId("review-queue"), { key: "a" });
    });

    expect(await screen.findByTestId("review-error")).toBeInTheDocument();
  });

  it("disables only the in-flight candidate's actions, not the rest of the queue", async () => {
    let resolveAccept!: (r: Response) => void;
    const acceptInFlight = new Promise<Response>((resolve) => {
      resolveAccept = resolve;
    });
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = String(input);
      if (url.includes("/accept") && init?.method === "POST") return acceptInFlight;
      return jsonResponse(200, { candidates: [candidate("c1"), candidate("c2")] });
    });
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("candidate-card");

    // Accept the selected (first) candidate; its request hangs in flight.
    fireEvent.keyDown(screen.getByTestId("review-queue"), { key: "a" });

    await waitFor(() => expect(screen.getAllByTestId("accept-proposal")[0]).toBeDisabled());
    // The other candidate stays actionable — the reviewer can keep working.
    expect(screen.getAllByTestId("accept-proposal")[1]).not.toBeDisabled();

    await act(async () => {
      resolveAccept(
        jsonResponse(200, {
          candidate_id: "c1",
          status: "merged",
          entity_id: "e1",
          already_decided: false,
        }),
      );
    });
  });

  it("ignores the keyboard scheme while a text input is the event target", async () => {
    const fetchMock = vi.fn(async () =>
      jsonResponse(200, { candidates: [candidate("c1"), candidate("c2")] }),
    );
    vi.stubGlobal("fetch", fetchMock);

    renderQueue();
    await screen.findAllByTestId("candidate-card");

    // Simulate a future text input on the page (the deferred arbitrary-search picker):
    // keystrokes typed into it must not drive the queue's J/K/A/N/M/R scheme.
    const input = document.createElement("input");
    document.body.appendChild(input);
    fireEvent.keyDown(input, { key: "j" });

    const cards = screen.getAllByTestId("candidate-card");
    expect(cards[0]).toHaveAttribute("data-selected", "true");
    expect(cards[1]).toHaveAttribute("data-selected", "false");

    document.body.removeChild(input);
  });
});
