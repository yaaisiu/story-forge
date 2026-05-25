// AppShell — the router-only portion of the app. It assumes a router and a
// QueryClientProvider are already mounted above it, which keeps it trivial to
// test (the shell render test wraps it in MemoryRouter + QueryClientProvider)
// and trivial to compose in production (App.tsx wraps it in BrowserRouter +
// QueryClientProvider). Conventions: frontend/src/CLAUDE.md.
import { AppRoutes } from "./routes";

export function AppShell() {
  return (
    <main className="mx-auto max-w-2xl p-8 font-sans">
      <AppRoutes />
    </main>
  );
}
