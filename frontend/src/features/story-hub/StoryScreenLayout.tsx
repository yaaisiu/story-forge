// Story-screen layout (Grzymalin S3 — app navigation, owner Session 102).
//
// Wraps every per-story screen (structure / reader / graph / review / relations /
// duplicates / normalise-names) with a single "← Story hub" back-link, so a subscreen
// is never a one-way door — the up-navigation chain subscreen → hub → projects always
// exists. Applied once as a route-level layout (routes.tsx) rather than pasted into each
// screen's several render branches, so the screens (and their tests) stay untouched.
//
// The layout owns the viewport height (`h-screen` column: fixed-height back-link bar +
// a scrollable Outlet region) so a screen never has to add the back-link's height to its
// own. This is why GraphViewer's root is `h-full` (fills the region), not `h-screen`
// (which, stacked below the bar, would overflow the page by the bar's height). The
// content screens flow at their natural height and the region scrolls when they exceed it.

import { Link, Outlet, useParams } from "react-router-dom";

export function StoryScreenLayout() {
  const { storyId } = useParams<{ storyId: string }>();
  return (
    <div className="flex h-screen flex-col">
      <div className="shrink-0 px-6 pt-4">
        {storyId && (
          <Link
            data-testid="back-to-hub"
            to={`/stories/${storyId}`}
            className="text-sm font-medium text-blue-600 hover:underline"
          >
            ← Story hub
          </Link>
        )}
      </div>
      <div className="min-h-0 flex-1 overflow-y-auto">
        <Outlet />
      </div>
    </div>
  );
}
