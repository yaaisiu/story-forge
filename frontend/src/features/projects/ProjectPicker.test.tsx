// Tests for the project / story picker (Session 53 — M4 multi-story frontend).
//
// Pins the navigation contract: list projects, select one to load its stories,
// and surface the graph/reader links + the add-a-story affordance (which carries
// the project id back to the upload screen via router state). The fetch stub routes
// by URL so the projects list and the per-project stories list are answered
// independently. Same per-test QueryClient + MemoryRouter harness as the others.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { fireEvent, render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { ProjectPicker } from "./ProjectPicker";

function buildWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/projects"]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  };
}

const PROJECT_ID = "00000000-0000-0000-0000-000000000001";
const STORY_ID = "11111111-1111-1111-1111-111111111111";
const PROJECTS_BODY = [
  {
    id: PROJECT_ID,
    name: "Oakhaven",
    language: "en",
    created_at: "2026-06-01T10:00:00Z",
    story_count: 1,
  },
];
const STORIES_BODY = [{ id: STORY_ID, title: "Chapter one", ingested_at: "2026-06-02T09:00:00Z" }];

function jsonResponse(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

function stubFetch() {
  const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
    const url = String(input);
    if (url.match(/\/projects\/[^/]+\/stories$/)) return jsonResponse(200, STORIES_BODY);
    if (url.endsWith("/projects")) return jsonResponse(200, PROJECTS_BODY);
    throw new Error(`unexpected url ${url}`);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

beforeEach(() => {
  vi.restoreAllMocks();
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("ProjectPicker", () => {
  it("lists projects and shows the placeholder until one is selected", async () => {
    stubFetch();
    render(<ProjectPicker />, { wrapper: buildWrapper() });

    expect(await screen.findByTestId(`project-row-${PROJECT_ID}`)).toHaveTextContent("Oakhaven");
    expect(screen.getByTestId("stories-placeholder")).toBeInTheDocument();
  });

  it("loads the selected project's stories with graph + reader links", async () => {
    stubFetch();
    render(<ProjectPicker />, { wrapper: buildWrapper() });

    fireEvent.click(await screen.findByTestId(`project-row-${PROJECT_ID}`));

    expect(await screen.findByTestId(`story-row-${STORY_ID}`)).toHaveTextContent("Chapter one");
    expect(screen.getByTestId(`story-graph-link-${STORY_ID}`)).toHaveAttribute(
      "href",
      `/stories/${STORY_ID}/graph`,
    );
    expect(screen.getByTestId(`story-reader-link-${STORY_ID}`)).toHaveAttribute(
      "href",
      `/stories/${STORY_ID}/reader`,
    );
  });

  it("offers an add-a-story link back to the upload screen for the selected project", async () => {
    stubFetch();
    render(<ProjectPicker />, { wrapper: buildWrapper() });

    fireEvent.click(await screen.findByTestId(`project-row-${PROJECT_ID}`));

    const addLink = await screen.findByTestId("add-story-link");
    expect(addLink).toHaveAttribute("href", "/");
  });

  it("surfaces an empty state when there are no projects", async () => {
    const fetchMock = vi.fn().mockResolvedValue(jsonResponse(200, []));
    vi.stubGlobal("fetch", fetchMock);

    render(<ProjectPicker />, { wrapper: buildWrapper() });

    expect(await screen.findByTestId("projects-empty")).toBeInTheDocument();
  });
});
