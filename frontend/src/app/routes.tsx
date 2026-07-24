// Route table — kept as one small module separate from AppShell so the routing
// surface has one obvious place to grow as features land in later sessions,
// and so AppShell stays a thin layout wrapper. Both the production composition
// (BrowserRouter in App.tsx) and the shell render test (MemoryRouter in
// AppShell.test.tsx) mount AppShell, which mounts AppRoutes — so this module
// is shared by both code paths.
import { lazy, Suspense, type ReactNode } from "react";

import { Route, Routes } from "react-router-dom";

import { OutlineEditor } from "../features/chunking/OutlineEditor";
import { DuplicatesQueue } from "../features/duplicate-review/DuplicatesQueue";
import { ReviewQueue } from "../features/extraction-review/ReviewQueue";
import { ProjectPicker } from "../features/projects/ProjectPicker";
import { NormaliseNamesQueue } from "../features/normalise-names/NormaliseNamesQueue";
import { RelationQueue } from "../features/relation-review/RelationQueue";
import { StoryHub } from "../features/story-hub/StoryHub";
import { StoryScreenLayout } from "../features/story-hub/StoryScreenLayout";
import { STORY_SCREENS } from "../features/story-hub/storyScreens";
import { TextReader } from "../features/text-reader/TextReader";
import { UploadScreen } from "../features/upload/UploadScreen";

// Code-split the graph viewer: it pulls in cytoscape (~225 kB gzip), which only
// the graph route needs — lazy-loading keeps it out of the initial bundle so the
// upload/outline flow stays lean. The chunk loads on first navigation to /graph.
const GraphViewer = lazy(() =>
  import("../features/graph-viewer/GraphViewer").then((m) => ({ default: m.GraphViewer })),
);

// The element for each per-story screen, keyed by STORY_SCREENS[].key. The paths + hub
// links come from STORY_SCREENS (one source of truth — see storyScreens.ts); this maps
// each key to what it renders. Spec origins: structure (M1), graph (M2.S5), review
// (M3.S4b, spec §3.3 Stage 4), relations (M3.S4f), reader (M4.S1, spec §3.5),
// duplicates (graph-quality S4b), normalise-names (graph-quality S6b).
const SCREEN_ELEMENTS: Record<string, ReactNode> = {
  structure: <OutlineEditor />,
  graph: (
    <Suspense fallback={<p className="p-6 text-sm text-gray-500">Loading graph viewer…</p>}>
      <GraphViewer />
    </Suspense>
  ),
  review: <ReviewQueue />,
  relations: <RelationQueue />,
  reader: <TextReader />,
  duplicates: <DuplicatesQueue />,
  "normalise-names": <NormaliseNamesQueue />,
};

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
          path, the layout completes the deeper ones (react-router path ranking). The
          sub-routes are generated from STORY_SCREENS so they can't drift from the hub's
          link grid (both derive from the same list). */}
      <Route path="/stories/:storyId" element={<StoryHub />} />
      <Route path="/stories/:storyId" element={<StoryScreenLayout />}>
        {STORY_SCREENS.map((screen) => (
          <Route key={screen.key} path={screen.suffix} element={SCREEN_ELEMENTS[screen.key]} />
        ))}
      </Route>
    </Routes>
  );
}
