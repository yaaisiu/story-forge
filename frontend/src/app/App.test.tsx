// App shell render test (Session 5 — Frontend foundation).
//
// What this test pins down:
//   1. The app shell can be mounted under React Router + TanStack Query without
//      throwing. This is the smallest assertion that proves both providers are
//      wired correctly in src/app/.
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
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";

import { AppShell } from "./AppShell";

describe("AppShell", () => {
  it("renders the landing placeholder at /", () => {
    // Fresh QueryClient per test — no cross-test cache bleed. retry: false keeps
    // failing queries from looping in tests.
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false } },
    });

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter initialEntries={["/"]}>
          <AppShell />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    // The landing placeholder identifies itself by a stable test id so we can
    // change its visible copy in Session 6 without touching this shell test.
    expect(screen.getByTestId("landing-placeholder")).toBeInTheDocument();
  });
});
