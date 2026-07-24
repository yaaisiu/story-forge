// Story-screen layout (Grzymalin S3 — app navigation, owner Session 102).
//
// Wraps every per-story screen (structure / reader / graph / review / relations /
// duplicates / normalise-names) with a single "← Story hub" back-link, so a subscreen
// is never a one-way door — the up-navigation chain subscreen → hub → projects always
// exists. Applied once as a route-level layout (routes.tsx) rather than pasted into each
// screen's several render branches, so the screens (and their tests) stay untouched.

import { Link, Outlet, useParams } from "react-router-dom";

export function StoryScreenLayout() {
  const { storyId } = useParams<{ storyId: string }>();
  return (
    <>
      <div className="px-6 pt-4">
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
      <Outlet />
    </>
  );
}
