# CLAUDE.md — frontend/src/

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

## Styling

- Tailwind utility classes; shadcn/ui components for primitives
- No CSS-in-JS libraries
- Design tokens via Tailwind config; never hardcode colors in components
