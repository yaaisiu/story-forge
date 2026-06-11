# AGENTS.md — frontend/src/

Component and structure conventions for the React app.

## Folder structure (mirrors features in the spec §3-§5)

- `app/` — routing, providers, top-level layout
- `features/upload/` — file upload UI
- `features/chunking/` — outline view, manual chunking editor
- `features/extraction-review/` — review queue UI (Stage 4 of cascade, spec §3.3)
- `features/graph-viewer/` — Neo4j graph visualization
- `features/text-reader/` — story reader with inline entity highlights
- `features/agent-activity/` — persistent panel showing which agent ran, which model/tier was chosen, latency, cost (spec §8.5)
- `features/editor/` — V2 editing modes (later milestones)
- `components/ui/` — primitives
- `lib/api/` — generated API client
- `stores/` — Zustand stores
- `hooks/` — shared hooks

## Component rules

- One component per file, named after the file.
- Co-locate small helper components in the same file only if they are private and never reused.
- Props typed explicitly; no `any`.
- No business logic in components. Components render and dispatch. Logic lives in hooks or stores.

## Test-first, applied to React (root `AGENTS.md` §2 nuance)

The "write the failing test first" rule is strict for **logic** — hooks, pure functions
(parsers, the `graphElements` mapper), API clients: write the test that encodes the
behaviour, watch it fail, then implement. For **presentational components**, the honest
practice is _shape the component and its test together_ — JSX is often easier to get right
by writing the markup and the asserting test in one pass — but the bar at merge is the same:
**every behaviour a component owns has a test that exercises it** (states, branches, the
data-testid contract, user interactions), and an untestable surface is isolated and named
(e.g. `GraphCanvas`'s cytoscape mount, covered by the browser smoke, not jsdom). If you
wrote a component before its test, say so in the PR/`/review-pr` rather than implying strict
TDD order. Factor the logic _out_ of the component (into a hook or a pure module) precisely
so the hard-to-test part shrinks to render-and-dispatch. (Session 17: the M2.S5 viewer
components were shaped-then-tested; coverage was complete, disclosed in `/review-pr`.)

## Styling

- Tailwind utility classes; shadcn/ui components for primitives
- No CSS-in-JS libraries
- Design tokens via Tailwind config; never hardcode colors in components
