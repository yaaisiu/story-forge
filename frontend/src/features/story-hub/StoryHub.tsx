// Story hub (Grzymalin S3 — app navigation, owner Session 102).
//
// A per-story landing page: every screen a story has is one click from here, so a
// raw `:storyId` UUID never has to be typed into the URL bar to reach review /
// relations / duplicates / normalise-names / structure. Reached from the project
// picker's story rows; deep-linkable and reload-safe (the header names the story via
// GET /stories/{id}, and the screen links need only the id in the URL).
//
// Components render and dispatch (frontend/src/CLAUDE.md): the story detail lives in
// the query hook, the screen list is static data. The nav grid renders even if the
// title fetch fails — navigation only needs the id, so a store hiccup doesn't strand
// the author on a dead page.

import { Link, useParams } from "react-router-dom";

import { useStory } from "../../lib/api/useStory";

/** The screens a story owns, in pipeline order (structure → curate the graph). Each
 *  links to `/stories/{id}/{suffix}`. Static presentational data — not business logic. */
const STORY_SCREENS: ReadonlyArray<{
  key: string;
  suffix: string;
  label: string;
  description: string;
}> = [
  {
    key: "structure",
    suffix: "structure",
    label: "Structure",
    description: "The chapters, scenes, and paragraphs detected in the text.",
  },
  {
    key: "reader",
    suffix: "reader",
    label: "Read",
    description: "The story text with accepted entities highlighted inline.",
  },
  {
    key: "graph",
    suffix: "graph",
    label: "Graph",
    description: "The knowledge graph of entities and their relations.",
  },
  {
    key: "review",
    suffix: "review",
    label: "Review candidates",
    description: "Accept or reject the entities extraction proposed.",
  },
  {
    key: "relations",
    suffix: "relations",
    label: "Review relations",
    description: "Decide the relations staged between accepted entities.",
  },
  {
    key: "duplicates",
    suffix: "duplicates",
    label: "Duplicates",
    description: "Merge or dismiss likely-duplicate entities.",
  },
  {
    key: "normalise-names",
    suffix: "normalise-names",
    label: "Normalise names",
    description: "Unify synonymous predicate and type labels graph-wide.",
  },
];

function isoDate(value: string): string {
  return value.slice(0, 10);
}

export function StoryHub() {
  const { storyId } = useParams<{ storyId: string }>();
  const story = useStory(storyId);

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
        ) : story.isError ? (
          // The title read failed, but the screen links only need the id in the URL —
          // keep the hub usable rather than blocking navigation on a header fetch.
          <h1 data-testid="hub-title-error" className="text-2xl font-semibold text-gray-500">
            Story
          </h1>
        ) : (
          <h1 data-testid="hub-title-loading" className="text-2xl font-semibold text-gray-400">
            Loading story…
          </h1>
        )}
      </header>

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
    </main>
  );
}
