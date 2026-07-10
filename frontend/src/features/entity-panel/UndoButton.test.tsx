// Tests for the reader's undo affordance (Session 43 — M4.S3b-fe, DM-S3b-1 see-what-I-undo).
//
// Pins: clicking previews (POST ?preview=true) and shows the description before reversing; Confirm
// applies (POST, no preview) and shows the undone description; Cancel drops the preview without
// applying; nothing-to-undo (404) is a quiet message; drift on apply (409) is a reload-and-retry
// error. Fetch is routed by the `?preview=true` query so preview and apply return different bodies.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { UndoButton } from "./UndoButton";

const STORY_ID = "00000000-0000-0000-0000-000000000002";

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function renderButton() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  render(
    <QueryClientProvider client={queryClient}>
      <UndoButton storyId={STORY_ID} />
    </QueryClientProvider>,
  );
}

// Route by whether the URL carries ?preview=true.
function routeFetch(previewResp: () => Response, applyResp: () => Response) {
  return vi.fn((url: string) =>
    Promise.resolve(url.includes("preview=true") ? previewResp() : applyResp()),
  );
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("UndoButton", () => {
  it("previews the description, then applies on confirm", async () => {
    const fetchMock = routeFetch(
      () =>
        jsonResponse(200, {
          description: "merged Broniek into Bronisław",
          op_kind: "merge",
          applied: false,
        }),
      () =>
        jsonResponse(200, {
          description: "merged Broniek into Bronisław",
          op_kind: "merge",
          applied: true,
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderButton();

    fireEvent.click(screen.getByTestId("undo-button"));
    expect(await screen.findByTestId("undo-preview")).toHaveTextContent(
      "merged Broniek into Bronisław",
    );

    // The preview must not have applied anything.
    const previewCall = fetchMock.mock.calls[0] as [string];
    expect(previewCall[0]).toContain("preview=true");

    fireEvent.click(screen.getByTestId("undo-confirm"));
    expect(await screen.findByTestId("undo-applied")).toHaveTextContent(
      "merged Broniek into Bronisław",
    );

    const applyCall = fetchMock.mock.calls.find((c) => !c[0].includes("preview=true")) as [string];
    expect(applyCall[0]).toMatch(new RegExp(`/stories/${STORY_ID}/graph-edits/undo$`));
  });

  it("cancels a preview without applying", async () => {
    const fetchMock = routeFetch(
      () =>
        jsonResponse(200, {
          description: "deleted Oakhaven",
          op_kind: "delete_entity",
          applied: false,
        }),
      () =>
        jsonResponse(200, {
          description: "deleted Oakhaven",
          op_kind: "delete_entity",
          applied: true,
        }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderButton();

    fireEvent.click(screen.getByTestId("undo-button"));
    await screen.findByTestId("undo-preview");
    fireEvent.click(screen.getByTestId("undo-cancel"));

    await waitFor(() => expect(screen.queryByTestId("undo-preview")).toBeNull());
    expect(screen.getByTestId("undo-button")).toBeInTheDocument();
    // Only the preview fired; nothing was applied.
    expect(fetchMock.mock.calls.every((c) => (c[0] as string).includes("preview=true"))).toBe(true);
  });

  it("shows a quiet message when there is nothing to undo (404)", async () => {
    const fetchMock = routeFetch(
      () => jsonResponse(404, { detail: "nothing to undo" }),
      () => jsonResponse(404, { detail: "nothing to undo" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderButton();

    fireEvent.click(screen.getByTestId("undo-button"));
    expect(await screen.findByTestId("undo-empty")).toBeInTheDocument();
    expect(screen.queryByTestId("undo-preview")).toBeNull();
  });

  it("shows a reload-and-retry error when the graph drifted on apply (409)", async () => {
    const fetchMock = routeFetch(
      () =>
        jsonResponse(200, {
          description: "deleted Oakhaven",
          op_kind: "delete_entity",
          applied: false,
        }),
      () => jsonResponse(409, { detail: "the graph drifted since" }),
    );
    vi.stubGlobal("fetch", fetchMock);
    renderButton();

    fireEvent.click(screen.getByTestId("undo-button"));
    await screen.findByTestId("undo-preview");
    fireEvent.click(screen.getByTestId("undo-confirm"));

    await waitFor(() => expect(screen.getByTestId("undo-error")).toHaveTextContent("reload"));
  });
});
