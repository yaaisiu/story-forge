// Production composition root. The shell render test mounts <AppShell> directly
// under MemoryRouter + QueryClientProvider; here we wrap it in the browser
// equivalents. Keep this file thin — anything more complex than "compose the
// providers" belongs inside src/app/.
import { BrowserRouter } from "react-router-dom";
import { QueryClientProvider } from "@tanstack/react-query";

import { AppShell } from "./app/AppShell";
import { createQueryClient } from "./app/queryClient";

// Single QueryClient instance for the app lifetime. React 19 + StrictMode will
// double-invoke component bodies in dev, so we instantiate at module scope (not
// inside the component) to avoid throwing away the cache on every render.
const queryClient = createQueryClient();

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <AppShell />
      </BrowserRouter>
    </QueryClientProvider>
  );
}

export default App;
