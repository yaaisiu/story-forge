// Story hub (Grzymalin S3 — app navigation, owner Session 102).
//
// A per-story landing page: every screen a story has is one click from here, so a
// raw `:storyId` UUID never has to be typed into the URL bar to reach review /
// relations / duplicates / normalise-names / structure. Reached from the project
// picker's story rows; deep-linkable and reload-safe (the header names the story via
// GET /stories/{id}, and the screen links need only the id in the URL).
//
// Components render and dispatch (frontend/src/CLAUDE.md): the story detail lives in
// the query hook, the screen list is the shared STORY_SCREENS source of truth (also
// driving the router). A transient title-fetch failure (503/network) keeps the nav grid
// so a store hiccup doesn't strand the author; a genuine 404 (story gone) instead shows a
// clear not-found state with no dead links.

import { Link, useParams } from "react-router-dom";

import { useStory } from "../../lib/api/useStory";
import { isoDate } from "../../lib/utils";
import { STORY_SCREENS } from "./storyScreens";

export function StoryHub() {
  const { storyId } = useParams<{ storyId: string }>();
  const story = useStory(storyId);
  const notFound = story.isError && story.error.status === 404;

  return (
    <main className="mx-auto flex max-w-4xl flex-col gap-6 p-8">
      <header className="flex flex-col gap-2">
        <Link
          data-testid="hub-back-to-projects"
          to="/projects"
          className="self-start text-sm font-medium text-blue-600 hover:underline"
        >
          ← All projects
        </Link>
        {story.isSuccess ? (
          <>
            <h1 data-testid="hub-title" className="text-2xl font-semibold">
              {story.data.title}
            </h1>
            <p className="text-sm text-gray-600">Ingested {isoDate(story.data.ingested_at)}</p>
          </>
        ) : notFound ? (
          <>
            <h1 data-testid="hub-title-notfound" className="text-2xl font-semibold">
              Story not found
            </h1>
            <p className="text-sm text-gray-600">
              This story doesn&rsquo;t exist — it may have been deleted. Head back to your projects.
            </p>
          </>
        ) : story.isError ? (
          // A transient failure (503 / network) — the title is unknown, but the screen links
          // only need the id in the URL, so keep the hub usable rather than block navigation.
          <h1 data-testid="hub-title-error" className="text-2xl font-semibold text-gray-500">
            Story
          </h1>
        ) : (
          <h1 data-testid="hub-title-loading" className="text-2xl font-semibold text-gray-400">
            Loading story…
          </h1>
        )}
      </header>

      {/* No screen links for a story that doesn't exist — they would all be dead ends. */}
      {!notFound && (
        <nav className="grid grid-cols-1 gap-3 sm:grid-cols-2">
          {STORY_SCREENS.map((screen) => (
            <Link
              key={screen.key}
              data-testid={`hub-link-${screen.key}`}
              to={`/stories/${storyId}/${screen.suffix}`}
              className="flex flex-col gap-1 rounded border border-gray-200 px-4 py-3 hover:border-blue-400 hover:bg-gray-50"
            >
              <span className="font-medium text-gray-900">{screen.label}</span>
              <span className="text-xs text-gray-500">{screen.description}</span>
            </Link>
          ))}
        </nav>
      )}
    </main>
  );
}
