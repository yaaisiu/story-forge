// The per-story screens — the single source of truth shared by the story hub's link
// grid (StoryHub) and the router's per-story sub-routes (app/routes.tsx). Deriving both
// from this one list means a screen can never be routable-but-unlinked (unreachable from
// the hub, the exact failure the hub exists to prevent) or linked-but-unroutable.
// Order is the pipeline order the hub displays: structure → curate the graph.

export interface StoryScreen {
  /** Stable key; also the routes.tsx element lookup key. */
  key: string;
  /** Path segment under `/stories/:storyId/`. */
  suffix: string;
  /** Hub card title. */
  label: string;
  /** Hub card one-line description. */
  description: string;
}

export const STORY_SCREENS: readonly StoryScreen[] = [
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
