// Shared QueryClient factory. We use a factory (not a module-level singleton) so
// tests can build their own client with retry: false; production calls
// createQueryClient() once at startup. Defaults are intentionally conservative:
// no auto-refetch on window focus (single-user local app — no tab-switching
// scenario where that helps), no retries (a failed call against localhost
// almost always means the backend is down — retrying just hides it). Tune
// per-query in the hooks that need different behaviour.
import { QueryClient } from "@tanstack/react-query";

export function createQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
    },
  });
}
