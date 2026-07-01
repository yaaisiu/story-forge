# Domain layer — the pure shapes and rules

> **Reference note.** What lives in `backend/src/story_forge/domain/` and what each piece is for.
> The code and [`backend/src/story_forge/AGENTS.md`](../../backend/src/story_forge/AGENTS.md) own
> the details and stay current — this note is a map of the territory, not a copy of it.

## What this layer is responsible for

`domain/` holds the project's pure business types and logic: the document-tree and
knowledge-graph shapes, and the deterministic rules that operate on them (parsing, chunking,
highlight resolution, merge planning, undo inversion). It is the bottom of the dependency graph —
it imports nothing infrastructural and performs **no I/O**: no HTTP, no database driver, no LLM,
no filesystem. A domain module takes plain values in and returns plain values (or raises a
`ValueError` subclass), which is why it is the layer the project unit-tests hardest, without a
database or network.

When the domain needs something only the outside world can provide, it does **not** reach for it —
it defines a `typing.Protocol` for the capability and lets an adapter implement it (the layering
rule in [`AGENTS.md`](../../backend/src/story_forge/AGENTS.md)). The persisted shapes here map
one-to-one onto the spec's data model (spec [`§6.4`](../../story-forge-poc-spec.md)); IDs are
app-generated UUIDs, stable across the Postgres/Neo4j split.

## Modules

### `models.py` — the document-tree shapes
The structural hierarchy Project → Story → Chapter → Scene → Paragraph as plain Pydantic models,
field-aligned to the DB columns and JSON wire format (no mapping layer). Also `EntityMention` (the
back-reference recording where a graph entity appears in the text — the cross-store seam, since
`entity_id` points at a Neo4j node with no Postgres FK), `MentionSuppression` (a negative "this
span is *not* a highlight" record), and the lightweight `ProjectSummary` / `StorySummary` read
projections the pickers list. [`domain/models.py`](../../backend/src/story_forge/domain/models.py)

### `graph.py` — the knowledge-graph shapes
`GraphEntity` and `GraphRelation` — the *persisted* Neo4j node and edge shapes, deliberately
distinct from the agents' extraction-time candidates. Both carry an open-world, free-string `type`
(never an enum) and free-form JSON `properties`; several name/embedding fields are nullable because
they are only resolved at a later milestone. [`domain/graph.py`](../../backend/src/story_forge/domain/graph.py)

### `extraction.py` — the Pre-NER candidate shape
`CandidateSpan`: one low-confidence proper-noun span found by the spaCy baseline, with its char
offsets, raw spaCy label (kept for provenance), and the type it was mapped to. Deliberately
minimal — the richer LLM entity shape is built later in the pipeline, not here.
[`domain/extraction.py`](../../backend/src/story_forge/domain/extraction.py)

### `parsing.py` — upload → text + paragraph blocks
`parse_document` turns an upload's bytes + suffix into a `ParsedDocument` (raw text plus paragraph
blocks); `.txt`/`.md` decode-and-split-on-blank-lines, `.docx` via python-docx. `split_paragraphs`
is the one canonical blank-line rule shared with the chunker so paragraph indexing matches end to
end. A `ParseError` (a `ValueError`) signals input the caller rejects with a 400 — no
library-specific exception ever leaks out. [`domain/parsing.py`](../../backend/src/story_forge/domain/parsing.py)

### `chunking.py` — markdown outline → persistable tree
Deterministic manual/hybrid chunking: `parse_manual_outline` reads markdown heading *levels*
(`##` chapter, `###` scene, `#` story-title dropped) into an `Outline` tree of `OutlineChapter` /
`OutlineScene`, with stray prose landing in implicit untitled containers so no text is lost.
`outline_to_tree` flattens that tree into ordered `Chapter`/`Scene`/`Paragraph` rows under a
`story_id` — assigning `order_index` and threading parent ids, but leaving persistence to the
adapter. `paragraph_range_problem` is the single home for the auto-chunker's range invariant
(every paragraph `[0, count)` covered, nothing past the end — graph-quality §3 S1): both the
agent's retried check and the coordinator's terminal backstop call it.
[`domain/chunking.py`](../../backend/src/story_forge/domain/chunking.py)

### `language.py` — detect a story's language
`detect_language`: text in, an ISO 639-1 code out (`pl`/`en` for this app), via `langdetect` with a
pinned seed for reproducibility. Blank or feature-less text raises `ValueError` so the caller
rejects the upload rather than persisting a guess.
[`domain/language.py`](../../backend/src/story_forge/domain/language.py)

### `candidates.py` — the dedupe-cascade staging shapes
The *persisted* shapes of the candidate-lifecycle state machine (spec §3.3 / §7): `StagedCandidate`
(an extracted entity carrying the cascade's NEW-vs-MERGE proposal awaiting human review),
`CandidateDecision` (the append-only accept/reject evidence log), `StagedRelation` (an extracted
relation with surface endpoints awaiting the human "decide on relations" action), and
`AcceptedSnapshot` (the already-accepted graph a run matches against, read once per run). Key
non-obvious "why": the id helpers (`committed_entity_id`, `staged_relation_id`, `relation_edge_id`)
derive graph ids *deterministically* from candidate/triple inputs — the basis of the accept-path
retry-idempotency contract — and `normalize_name` is the tight casefold+strip key that links a
relation endpoint back to its entity candidate.
[`domain/candidates.py`](../../backend/src/story_forge/domain/candidates.py)

### `edge_evidence.py` — the read-side provenance of a committed edge
The pure assembly behind the edge-evidence read (graph-quality §3 S3): `build_edge_evidence` takes an
edge's `written` `staged_relations` rows plus a paragraph-id → text lookup the caller resolved, and
returns the `EdgeEvidence` shape (predicate + one `EdgeEvidenceSource` per source paragraph/quote).
Provenance is *one-to-many* — a content-addressed edge collapses the same fact across N paragraphs to
one edge but keeps N rows — and a zero-row edge (manually added, no staged relation) yields an empty
list rather than an error. No I/O; the cross-store fetch is the route's job.
[`domain/edge_evidence.py`](../../backend/src/story_forge/domain/edge_evidence.py)

### `highlights.py` — resolving where entities sit in the prose
A read-only projection of the accepted graph onto the text (spec §3.5). Because an
`entity_mention`'s char offsets are usually null, highlighting is first a *where-does-this-entity-sit*
problem, solved by render-time, word-boundary, case-insensitive string search over each entity's
surface forms. `resolve_highlights` does search-only arbitration (longest-match-wins,
non-overlapping); `reconcile_highlights` merges three sources — search hits, author-asserted stored
`ManualSpan`s (which win overlaps), and `Suppression`s (which subtract post-overlay).
`validate_manual_span` guards an author's tag range (raising `SpanInvalid` → 400). The standing
posture is **omit, don't guess**: an entity whose forms don't occur yields no highlight rather than
a wrong one. [`domain/highlights.py`](../../backend/src/story_forge/domain/highlights.py)

### `neighbourhood.py` — the 1-hop ego-graph for the side panel
`build_ego_graph` assembles a focal entity's direct neighbours plus the edges incident to it
(`EgoGraph` / `EgoNeighbour` / `EgoEdge`), each edge classified `out`/`in` by direction, from the
(edge, far-node) pairs the Neo4j adapter returns. Strict 1-hop, entity-incident only; self-loops
(a merge artifact) and non-incident or void-pointing edges are dropped, neighbours de-duped by id —
the same fail-closed, omit-don't-guess posture as `highlights.py`.
[`domain/neighbourhood.py`](../../backend/src/story_forge/domain/neighbourhood.py)

### `story_scope.py` — project graph → one story's subgraph
`filter_graph_to_story`: a project's graph is shared across its stories, and per-story membership is
*derived, not stored*. Given the caller's derived member-entity and story-paragraph id sets, this
projects the whole-project graph down to the "this story" subgraph the §3.4 toggle shows — keeping a
node iff it is a member, an edge iff both endpoints are members and it was asserted within the story
(or is a story-agnostic manual edge), which guarantees a self-contained subgraph with no dangling
edges. [`domain/story_scope.py`](../../backend/src/story_forge/domain/story_scope.py)

### Graph-edit family — edits, merges, and their reversal
These four modules cover the human *write* surface over committed graph state and the undo that
makes it reversible (spec §11 / INV-3):

- **`entity_edits.py`** — `apply_entity_edit` validates an `EntityEditPatch` onto a `GraphEntity`
  and returns the next state (or raises `EntityEditInvalid` → 400), enforcing the boundary rules
  (a non-blank type, at least one canonical name, open `properties`); `diff_entity` yields the
  changed-field list the before→after evidence is built from.
  [`domain/entity_edits.py`](../../backend/src/story_forge/domain/entity_edits.py)
- **`entity_merge.py`** — `plan_merge` consolidates one entity into another and emits a
  deterministic `MergePlan` of re-point / fold / discard-self-loop edge steps (or raises
  `EntityMergeInvalid`). Non-obvious "why": because an edge's id is content-addressed from its
  endpoints, re-pointing changes the id, so a move is delete-old-plus-create-new; property
  conflicts are surfaced (`detect_property_conflicts`) and must be resolved by hand, never silently
  overwritten. [`domain/entity_merge.py`](../../backend/src/story_forge/domain/entity_merge.py)
- **`graph_edit.py`** — `GraphEdit`, the append-only before→after evidence row that records one
  human edit (one shape for node-field edits and edge add/remove), with grouping fields
  (`operation_id` / `seq` / `op_kind`) so a multi-row action like a merge reverses as one unit. The
  substrate for undo and the correction-as-training-data flywheel.
  [`domain/graph_edit.py`](../../backend/src/story_forge/domain/graph_edit.py)
- **`graph_undo.py`** — `invert_operation` turns a grouped set of `GraphEdit` rows into an ordered
  `InversePlan` of side-effect-free `InverseAction` descriptions (recreate/restore/remove/reassign)
  plus a declarative `DriftCheck` that refuses the undo (→409) if the graph moved on since. Rows
  replay highest-`seq`-first to keep the graph consistent at each step; an unrecognised `op` raises
  `UndoNotInvertible` (fail loud, never silently skip). The pure half of the undo executor — the
  adapter applies the plan. [`domain/graph_undo.py`](../../backend/src/story_forge/domain/graph_undo.py)

## How it connects

This layer sits at the bottom: nothing in `domain/` imports from `api/`, `agents/`, or
`adapters/`. The other layers depend on it, not the reverse —

- **`agents/`** consume these shapes (and the Protocols the domain declares) to orchestrate the
  pipeline: chunking turns text into the `Outline` tree, extraction produces candidates that get
  staged as `StagedCandidate`/`StagedRelation`, and the edit/merge services drive Neo4j writes from
  a `MergePlan` / `InversePlan`.
- **`adapters/`** implement the domain's Protocols and map its shapes onto storage (e.g. the Neo4j
  repo maps `GraphEntity`/`GraphRelation` onto nodes/relationships; the highlight and ego-graph
  reads feed their resolvers).
- **`api/`** returns these shapes over HTTP and maps domain `ValueError`s (`ParseError`,
  `SpanInvalid`, `EntityEditInvalid`, `EntityMergeInvalid`, `UndoNotInvertible`) to the right
  status codes.

The strict layering and the per-area conventions live in
[`backend/src/story_forge/AGENTS.md`](../../backend/src/story_forge/AGENTS.md); the data model these
shapes realise is spec [`§6.4`](../../story-forge-poc-spec.md). The sibling reference notes for the
other layers: [`backend-agents.md`](./backend-agents.md), [`backend-adapters.md`](./backend-adapters.md),
and [`backend-api.md`](./backend-api.md).
