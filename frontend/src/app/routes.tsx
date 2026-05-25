// Route table — kept as one tiny module so the shell render test can mount the
// routes under <MemoryRouter> while production code mounts the same routes under
// <BrowserRouter>. Add new top-level routes here as features land.
import { Route, Routes } from "react-router-dom";

import { Landing } from "./Landing";

export function AppRoutes() {
  return (
    <Routes>
      <Route path="/" element={<Landing />} />
    </Routes>
  );
}
