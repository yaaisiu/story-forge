// AppShell — the router-only portion of the app. It assumes a router and a
// QueryClientProvider are already mounted above it, which keeps it trivial to
// test (the shell render test wraps it in MemoryRouter + QueryClientProvider)
// and trivial to compose in production (App.tsx wraps it in BrowserRouter +
// QueryClientProvider). Conventions: frontend/src/CLAUDE.md.
//
// The shell deliberately doesn't impose a width / page-chrome container — each
// feature owns its own <main> + max-width so different screens (a narrow form,
// a wide editor) can size themselves honestly. Cross-cutting chrome (a nav, a
// footer) lands here when an actual one is needed.
import { AppRoutes } from "./routes";

export function AppShell() {
  return <AppRoutes />;
}
