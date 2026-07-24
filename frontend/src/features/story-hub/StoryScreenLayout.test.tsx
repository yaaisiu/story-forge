// Tests for the story-screen layout wiring (Grzymalin S3 — app navigation).
//
// Pins the navigation loop through the *real* AppRoutes: a per-story subscreen renders
// the "← Story hub" back-link (so it's never a one-way door), while the exact hub path
// does NOT (the hub has its own "← All projects" instead). This guards the subtle route
// ranking — two routes share the /stories/:storyId prefix, the leaf hub completing only
// the exact path and the layout completing the deeper ones. Fetch is stubbed pending so
// every screen just shows its loading state; the layout link is synchronous.

import type { ReactNode } from "react";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { AppRoutes } from "../../app/routes";

const STORY_ID = "11111111-1111-1111-1111-111111111111";

function renderAt(path: string): void {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={[path]}>{children}</MemoryRouter>
      </QueryClientProvider>
    );
  }
  render(<AppRoutes />, { wrapper: Wrapper });
}

beforeEach(() => {
  // Never-resolving fetch: screens stay in their loading state, so the assertions
  // are about the synchronous layout chrome, not a screen's data.
  vi.stubGlobal(
    "fetch",
    vi.fn(() => new Promise<Response>(() => {})),
  );
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("StoryScreenLayout wiring", () => {
  it("shows the ← Story hub back-link on a per-story subscreen", () => {
    renderAt(`/stories/${STORY_ID}/review`);

    expect(screen.getByTestId("back-to-hub")).toHaveAttribute("href", `/stories/${STORY_ID}`);
  });

  it("does not show the back-link on the hub itself (it has ← All projects instead)", () => {
    renderAt(`/stories/${STORY_ID}`);

    expect(screen.queryByTestId("back-to-hub")).not.toBeInTheDocument();
    expect(screen.getByTestId("hub-back-to-projects")).toBeInTheDocument();
  });
});
