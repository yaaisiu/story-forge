// Route table — kept as one small module separate from AppShell so the routing
// surface has one obvious place to grow as features land in later sessions,
// and so AppShell stays a thin layout wrapper. Both the production composition
// (BrowserRouter in App.tsx) and the shell render test (MemoryRouter in
// AppShell.test.tsx) mount AppShell, which mounts AppRoutes — so this module
// is shared by both code paths.
import { Route, Routes } from "react-router-dom";

import { OutlineEditor } from "../features/chunking/OutlineEditor";
import { UploadScreen } from "../features/upload/UploadScreen";

export function AppRoutes() {
  return (
    <Routes>
      {/* M1 flow: upload a story → build its outline. The router pushes the
          uploaded story's raw_text via location.state into the outline editor,
          so the manual editor opens pre-seeded with the source the user just
          uploaded. */}
      <Route path="/" element={<UploadScreen />} />
      <Route path="/stories/:storyId/structure" element={<OutlineEditor />} />
    </Routes>
  );
}
