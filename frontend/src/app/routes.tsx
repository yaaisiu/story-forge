// Route table — kept as one small module separate from AppShell so the routing
// surface has one obvious place to grow as features land in later sessions,
// and so AppShell stays a thin layout wrapper. Both the production composition
// (BrowserRouter in App.tsx) and the shell render test (MemoryRouter in
// AppShell.test.tsx) mount AppShell, which mounts AppRoutes — so this module
// is shared by both code paths.
import { lazy, Suspense } from "react";

import { Route, Routes } from "react-router-dom";

import { OutlineEditor } from "../features/chunking/OutlineEditor";
import { DuplicatesQueue } from "../features/duplicate-review/DuplicatesQueue";
import { ReviewQueue } from "../features/extraction-review/ReviewQueue";
import { ProjectPicker } from "../features/projects/ProjectPicker";
import { NormaliseNamesQueue } from "../features/normalise-names/NormaliseNamesQueue";
import { RelationQueue } from "../features/relation-review/RelationQueue";
import { StoryHub } from "../features/story-hub/StoryHub";
import { StoryScreenLayout } from "../features/story-hub/StoryScreenLayout";
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
      {/* M4 multi-story: browse projects + their stories; pick one to open its graph/
          reader, or add another story into the same shared-graph project (spec §3.4). */}
      <Route path="/projects" element={<ProjectPicker />} />
      {/* Grzymalin S3: a story's landing hub — links to every one of its screens so a
          raw :storyId UUID never has to be typed to reach review/relations/etc. The
          exact /stories/:storyId path is the hub; the deeper screen paths render under
          StoryScreenLayout, which adds the "← Story hub" back-link so no screen is a
          one-way door. Two routes share the prefix: the leaf hub completes only the exact
          path, the layout completes the deeper ones (react-router path ranking). */}
      <Route path="/stories/:storyId" element={<StoryHub />} />
      <Route path="/stories/:storyId" element={<StoryScreenLayout />}>
        <Route path="structure" element={<OutlineEditor />} />
        {/* M2.S5: once structured, run extraction and view the entity graph. */}
        <Route
          path="graph"
          element={
            <Suspense fallback={<p className="p-6 text-sm text-gray-500">Loading graph viewer…</p>}>
              <GraphViewer />
            </Suspense>
          }
        />
        {/* M3.S4b: review the staged candidates an extraction produced (the human gate
            that commits entities to the graph — spec §3.3 Stage 4 / §8.3). */}
        <Route path="review" element={<ReviewQueue />} />
        {/* M3.S4f: decide on the staged relations between accepted entities (the human
            gate that commits edges to the graph — spec §3.3's 5th human action). */}
        <Route path="relations" element={<RelationQueue />} />
        {/* M4.S1: read the story with accepted entities highlighted inline (spec §3.5).
            Read-only — no editor dep, so it imports directly (no code-split needed). */}
        <Route path="reader" element={<TextReader />} />
        {/* Graph-quality S4b: work down the likely-duplicate entity pairs suggested over the
            accepted graph — accept (→ the existing merge) or dismiss each (human-gated). */}
        <Route path="duplicates" element={<DuplicatesQueue />} />
        {/* Graph-quality S6b: work down the suggested synonymous predicate/type label pairs —
            rename one form into the other graph-wide or dismiss each (human-gated). */}
        <Route path="normalise-names" element={<NormaliseNamesQueue />} />
      </Route>
    </Routes>
  );
}
