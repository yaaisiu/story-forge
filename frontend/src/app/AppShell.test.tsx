// App shell render test (Session 5 — Frontend foundation).
//
// What this test pins down:
//   1. The app shell can be mounted under React Router + TanStack Query without
//      throwing, and the QueryClientProvider in the test tree is *load-bearing*:
//      the QuerySentinel below calls `useQueryClient()`, which throws when no
//      provider is in scope, so removing the provider wrapper would fail the
//      test rather than silently passing. This catches the "we thought the
//      provider chain was wired" class of regression.
//   2. The root route "/" renders a recognisable landing placeholder. Session 6
//      will replace the landing content with the real upload screen; until then
//      we just need *something* deterministic to assert on.
//
// We mount <AppShell> with our own <MemoryRouter> + <QueryClientProvider> instead
// of the production <App> so the test controls the router entry and doesn't share
// a QueryClient across tests. The production <App> in App.tsx composes the same
// pieces with a BrowserRouter — covered transitively by `tsc --noEmit` + a smoke
// render in dev. See frontend/src/CLAUDE.md for the "no useEffect(fetch)" rule
// that motivated removing the M0 /health page this shell replaces.

import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";

import { AppShell } from "./AppShell";

// Tiny in-test component that asserts a QueryClientProvider is in scope by
// calling useQueryClient(). The hook throws when no provider is mounted, which
// makes the wrapper in the render tree load-bearing: a regression that drops
// the provider would crash this child and fail the test, rather than passing
// because nothing in <AppShell> happens to use TanStack Query yet (Session 5
// hasn't shipped any hooks — the first one lands in Session 6).
function QuerySentinel() {
  useQueryClient();
  return null;
}

describe("AppShell", () => {
  it("renders the landing placeholder at / under both providers", () => {
    // Fresh QueryClient per test — no cross-test cache bleed. retry: false keeps
    // failing queries from looping in tests.
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <QuerySentinel />
          <AppShell />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // The landing placeholder identifies itself by a stable test id so we can
    // change its visible copy in Session 6 without touching this shell test.
    expect(screen.getByTestId("landing-placeholder")).toBeInTheDocument();
  });
});
