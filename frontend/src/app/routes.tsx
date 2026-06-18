// Route table — kept as one small module separate from AppShell so the routing
// surface has one obvious place to grow as features land in later sessions,
// and so AppShell stays a thin layout wrapper. Both the production composition
// (BrowserRouter in App.tsx) and the shell render test (MemoryRouter in
// AppShell.test.tsx) mount AppShell, which mounts AppRoutes — so this module
// is shared by both code paths.
import { lazy, Suspense } from "react";

import { Route, Routes } from "react-router-dom";

import { OutlineEditor } from "../features/chunking/OutlineEditor";
import { ReviewQueue } from "../features/extraction-review/ReviewQueue";
import { RelationQueue } from "../features/relation-review/RelationQueue";
import { TextReader } from "../features/text-reader/TextReader";
import { UploadScreen } from "../features/upload/UploadScreen";

// Code-split the graph viewer: it pulls in cytoscape (~225 kB gzip), which only
// the graph route needs — lazy-loading keeps it out of the initial bundle so the
// upload/outline flow stays lean. The chunk loads on first navigation to /graph.
const GraphViewer = lazy(() =>
  import("../features/graph-viewer/GraphViewer").then((m) => ({ default: m.GraphViewer })),
);

export function AppRoutes() {
  return (
    <Routes>
      {/* M1 flow: upload a story → build its outline. The router pushes the
          uploaded story's raw_text via location.state into the outline editor,
          so the manual editor opens pre-seeded with the source the user just
          uploaded. */}
      <Route path="/" element={<UploadScreen />} />
      <Route path="/stories/:storyId/structure" element={<OutlineEditor />} />
      {/* M2.S5: once structured, run extraction and view the entity graph. */}
      <Route
        path="/stories/:storyId/graph"
        element={
          <Suspense fallback={<p className="p-6 text-sm text-gray-500">Loading graph viewer…</p>}>
            <GraphViewer />
          </Suspense>
        }
      />
      {/* M3.S4b: review the staged candidates an extraction produced (the human gate
          that commits entities to the graph — spec §3.3 Stage 4 / §8.3). */}
      <Route path="/stories/:storyId/review" element={<ReviewQueue />} />
      {/* M3.S4f: decide on the staged relations between accepted entities (the human
          gate that commits edges to the graph — spec §3.3's 5th human action). */}
      <Route path="/stories/:storyId/relations" element={<RelationQueue />} />
      {/* M4.S1: read the story with accepted entities highlighted inline (spec §3.5).
          Read-only — no editor dep, so it imports directly (no code-split needed). */}
      <Route path="/stories/:storyId/reader" element={<TextReader />} />
    </Routes>
  );
}
