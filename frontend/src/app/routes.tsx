// Route table — kept as one small module separate from AppShell so the routing
// surface has one obvious place to grow as features land in later sessions,
// and so AppShell stays a thin layout wrapper. Both the production composition
// (BrowserRouter in App.tsx) and the shell render test (MemoryRouter in
// AppShell.test.tsx) mount AppShell, which mounts AppRoutes — so this module
// is shared by both code paths.
import { Route, Routes } from "react-router-dom";

import { Landing } from "./Landing";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
    </Routes>
  );
}
