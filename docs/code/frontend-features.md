# Frontend features — the screens

> **Reference note.** What lives in `frontend/src/features/` and what each folder is for.
> The code and [`frontend/src/AGENTS.md`](../../frontend/src/AGENTS.md) own the details and stay
> current — this note is a map of the territory, not a copy of it.

## What this layer is responsible for

`features/` holds the application's screens, one folder per screen or concern, mirroring the
pipeline the spec describes (upload → chunk → extract → review → graph/reader). Each folder owns its
React components plus the pure logic those components lean on. The conventions in
[`frontend/src/AGENTS.md`](../../frontend/src/AGENTS.md) are strict here: **one component per file,
no business logic in a component** — components render and dispatch, and the only effect they own is
a keydown subscription, never a data fetch (server state is TanStack Query's job).

The pipeline's non-trivial logic is therefore factored *out* of the components and into pure,
unit-tested modules beside them: the outline parser, the graph-element mappers, the reader's
highlight/offset math, the review-queue keyboard reducers, the property-editor and merge-conflict
mappers. Keeping the logic pure shrinks each component to a thin, testable render-and-dispatch
surface and isolates the genuinely untestable parts (a cytoscape canvas, a Tiptap mount) behind a
narrow prop interface so the rest can be unit-tested with that mount mocked, and the mount itself
covered by the real-browser smoke walk.

## Feature folders

### `upload/` — pick or drop a story file
The entry point: choose or drag a `.txt`/`.md`/`.docx` file, POST it, and on success show the
detected language and paragraph count from the typed response. Failures are keyed off the typed
`ApiError.status` (415 / 413 / 400 each get distinct copy) rather than parsing a detail string — the
spec §6.7 typed-client posture. A single component;
[`features/upload/UploadScreen.tsx`](../../frontend/src/features/upload/UploadScreen.tsx).

### `chunking/` — outline view and manual chunking editor
Closes the structuring step: the user picks a mode (auto / manual / hybrid), and in manual/hybrid
mode edits a textarea of markdown with a *live preview* of the parsed outline before submitting.
That preview is driven by [`features/chunking/outlineParse.ts`](../../frontend/src/features/chunking/outlineParse.ts) —
a TS mirror of the backend's `parse_manual_outline` (the backend re-parses on submit, so the two
**must** agree on what becomes a chapter / scene / paragraph; unit tests pin the rules). The screen
itself is [`features/chunking/OutlineEditor.tsx`](../../frontend/src/features/chunking/OutlineEditor.tsx).

### `extraction-review/` — the candidate review queue (Stage 4)
The human gate that turns staged candidates into graph entities (spec §3.3 / §8.3): read the pending
queue, render one card per candidate, and commit the reviewer's accept/reject. The spec §8.3 keyboard
scheme (J/K navigate, A/N/R/M decide) is the primary driver, expressed as a pure reducer in
[`features/extraction-review/reviewQueue.ts`](../../frontend/src/features/extraction-review/reviewQueue.ts)
so the [`ReviewQueue.tsx`](../../frontend/src/features/extraction-review/ReviewQueue.tsx) container
stays render-and-dispatch; [`CandidateCard.tsx`](../../frontend/src/features/extraction-review/CandidateCard.tsx)
presents one candidate's review set and mirrors the keys for the mouse.
[`EntityPicker.tsx`](../../frontend/src/features/extraction-review/EntityPicker.tsx) is the manual
escape hatch — search *all* the project's accepted entities to hand-pick a merge target a true
duplicate the cascade's top-3 missed; it is reused across the reader's merge and relation-add flows.

### `relation-review/` — the relation review queue
The sibling gate for *edges* (spec §3.3's 5th human action / §8.3): read a story's committable
relations, render one [`RelationCard.tsx`](../../frontend/src/features/relation-review/RelationCard.tsx)
per item, and commit the author's commit/reject. Its keyboard scheme — a subset of the candidate
queue's (J/K navigate, A commit, R reject; no merge target to cycle, since a relation has two already-
resolved endpoints) — lives in
[`features/relation-review/relationQueue.ts`](../../frontend/src/features/relation-review/relationQueue.ts),
keeping [`RelationQueue.tsx`](../../frontend/src/features/relation-review/RelationQueue.tsx) thin. The
card shows the extractor's *surface* triple (subject — predicate → object), not resolved canonical
names — a recorded v1 simplification.

### `graph-viewer/` — the Neo4j graph visualization (spec §3.4)
Reads a story's entity graph and renders it with a force-directed layout, a node-details side panel,
navigation controls, and the agent-activity panel alongside; it also hosts the "Run extraction"
trigger for a freshly-structured story that has no graph yet. The cytoscape *runtime* is isolated in
[`GraphCanvas.tsx`](../../frontend/src/features/graph-viewer/GraphCanvas.tsx) (jsdom can't drive a
canvas — verified by the browser smoke; it uses the `cytoscape-fcose` layout extension and takes an
already-filtered element set plus the search-match ids to highlight/pan), fed by the pure
[`graphElements.ts`](../../frontend/src/features/graph-viewer/graphElements.ts) mapper that turns the
API's graph response into cytoscape elements plus a colour-by-type palette. Client-side navigation
(spec §3.4 — filter by entity type + connection density, search by name) is pure logic in
[`graphFilters.ts`](../../frontend/src/features/graph-viewer/graphFilters.ts) (`nodeDegrees` /
`elementDegrees` / `distinctTypes` / `filterGraph` / diacritic-folding `matchNodes`), which the
[`GraphViewer.tsx`](../../frontend/src/features/graph-viewer/GraphViewer.tsx) container runs over the
already-fetched payload (no backend round-trip) before handing the visible subset to the canvas; the
search box is debounced via the shared [`useDebouncedValue`](../../frontend/src/hooks/useDebouncedValue.ts)
hook. The container and [`NodeDetailsPanel.tsx`](../../frontend/src/features/graph-viewer/NodeDetailsPanel.tsx)
(read-only entity details) stay testable with the canvas mocked.

### `agent-activity/` — the live model/agent panel (spec §8.5)
A small persistent panel that makes the multi-model, agent-based architecture legible to anyone
browsing the UI: which agent ran most recently, the model/tier the router chose, that call's latency
and cost, plus today's running totals and budget headroom. It polls the LLM-status endpoint on a
short interval so it reflects an extraction run live. One component;
[`features/agent-activity/AgentActivityPanel.tsx`](../../frontend/src/features/agent-activity/AgentActivityPanel.tsx).

### `projects/` — the project / story navigation hub (multi-story)
The navigation hub multi-story needs: list every project, select one to list its stories, and from
there open a story's graph or reader — or add another story to the same project (routing back to
upload carrying the project id so the new story joins the shared graph). Selection is local UI state;
the lists come from query hooks. One component;
[`features/projects/ProjectPicker.tsx`](../../frontend/src/features/projects/ProjectPicker.tsx).

### `text-reader/` — the story reader (the largest folder)
A read-only projection of the accepted graph over the prose (spec §3.5): the story's text in a single
column with accepted entities highlighted inline (colour-by-type), a clickable entity side panel, an
ego-graph mini-view, and the manual-correction surface (right-click menu + popover). It is the folder
with the most parts, split along the project's render-thin / logic-pure line:

- **The container + render surface.**
  [`TextReader.tsx`](../../frontend/src/features/text-reader/TextReader.tsx) owns the data, the
  selection/flash state, and the correction mutation hooks, dispatching into the editor and panel.
  [`ReaderEditor.tsx`](../../frontend/src/features/text-reader/ReaderEditor.tsx) is the one component
  touching the Tiptap/ProseMirror *runtime* (the untestable mount, like the cytoscape canvases),
  drawing highlights as ProseMirror **decorations** — a render-time overlay, so the document text is
  never rewritten and positions stay stable. Tiptap was adopted even for this read-only view so the
  V2 editing modes inherit the engine, and because it gives a document model that maps a text
  selection back to (paragraph, paragraph-relative offset) without trusting the rendered DOM.
- **The pure reader logic** (unit-tested without a DOM):
  [`readerDoc.ts`](../../frontend/src/features/text-reader/readerDoc.ts) builds the paragraphs →
  ProseMirror document (each paragraph carries its id as a node attribute, for scroll-to-paragraph
  and selection-mapping); [`decorations.ts`](../../frontend/src/features/text-reader/decorations.ts)
  maps highlights → decorations, owning the **codepoint ↔ UTF-16 offset** conversion the backend's
  codepoint offsets and ProseMirror's UTF-16 positions require, plus the decoration DOM attributes;
  [`selectionOffsets.ts`](../../frontend/src/features/text-reader/selectionOffsets.ts) is its inverse,
  turning a UTF-16 text selection into the codepoint span the tag/suppress/boundary routes expect;
  [`occurrences.ts`](../../frontend/src/features/text-reader/occurrences.ts) derives the panel's
  occurrence timeline *from the already-rendered highlights* so the panel and the prose can never
  disagree.
- **The correction UI** (manual tagging / re-assign / suppress, spec §3.5):
  [`ReaderContextMenu.tsx`](../../frontend/src/features/text-reader/ReaderContextMenu.tsx) is the
  right-click menu whose items depend on whether the click landed on a highlight or a free selection;
  [`ReaderCorrectionPopover.tsx`](../../frontend/src/features/text-reader/ReaderCorrectionPopover.tsx)
  collects the follow-up input (tag-as-entity / re-assign);
  [`correction.ts`](../../frontend/src/features/text-reader/correction.ts) holds the shared types the
  editor, menu, popover, and container pass between them.
- **Merge from the panel** (spec §3.4 merge):
  [`MergeControls.tsx`](../../frontend/src/features/text-reader/MergeControls.tsx) lets the author
  absorb one entity into the open one, with a by-hand resolver for property keys both set differently;
  the conflict detection is the pure
  [`mergeConflicts.ts`](../../frontend/src/features/text-reader/mergeConflicts.ts), mirroring the
  backend's `detect_property_conflicts` so nothing is silently overwritten.
- **The ego-graph mini-view** (1-hop, spec §3.5):
  [`EgoGraphCanvas.tsx`](../../frontend/src/features/text-reader/EgoGraphCanvas.tsx) is the panel's
  isolated cytoscape mount (a neighbour tap re-targets the panel), fed by the pure
  [`egoElements.ts`](../../frontend/src/features/text-reader/egoElements.ts) mapper over a single
  entity's neighbourhood — the same boundary discipline as `graph-viewer/`.
- **The colour legend + palette:**
  [`Legend.tsx`](../../frontend/src/features/text-reader/Legend.tsx) renders a swatch per entity type
  present so the colour-by-type highlighting is decodable;
  [`palette.ts`](../../frontend/src/features/text-reader/palette.ts) is the colour-by-type helper — a
  fixed palette for common types plus a deterministic hash fallback that never throws on the open-world
  long tail (entity `type` is a free string, not an enum).
- **The entity side panel + its editors:**
  [`ReaderEntityPanel.tsx`](../../frontend/src/features/text-reader/ReaderEntityPanel.tsx) is the
  inspection-and-edit surface clicking a highlight opens — details, free-form `properties`, the
  ego-graph, the occurrence timeline, plus an edit mode and a relations add/remove section (the first
  reader → graph writes). Its property-row logic is the pure
  [`propertiesEditor.ts`](../../frontend/src/features/text-reader/propertiesEditor.ts) (dict ↔ editable
  rows, coercing each value by kind so a number stays a number), and
  [`formatPropertyValue.ts`](../../frontend/src/features/text-reader/formatPropertyValue.ts) is the
  shared defensive display formatter for those free-form values.
- **Undo:** [`UndoButton.tsx`](../../frontend/src/features/text-reader/UndoButton.tsx) reverses the
  last graph edit anywhere in the story (edit / merge / delete), so it sits in the reader header; it
  *previews before it reverses* (asks the backend what would be undone, shows it, then confirms).

## How it connects

Every screen reads and writes server state through the data-layer query/mutation hooks in
`frontend/src/lib/api/` (TanStack Query — e.g. `useReader`, `useStoryGraph`, `useEntityDetail`,
`useReviewCandidate`), and renders the typed domain shapes those hooks return. No component fetches
directly: there is no `useEffect(fetch …)` pattern, and a successful mutation invalidates the
relevant queries so the affected views refetch (a decided item drops off a queue; a corrected name
re-highlights in the reader). Those hooks and the generated client wrap the backend's HTTP API —
backend behaviour and the domain shapes it returns are described in the sibling reference notes:
[`frontend-data-layer.md`](./frontend-data-layer.md) (the hooks and typed client these screens call),
[`backend-api.md`](./backend-api.md) (the routes behind them), and
[`backend-domain.md`](./backend-domain.md) (the domain shapes they render).
