# API layer — the HTTP surface

> **Reference note.** What lives in `backend/src/story_forge/api/` and what each piece is for.
> The code and [`backend/src/story_forge/AGENTS.md`](../../backend/src/story_forge/AGENTS.md) own
> the details and stay current — this note is a map of the territory, not a copy of it.

## What this layer is responsible for

`api/` is the HTTP edge of the backend: FastAPI routers that turn requests into calls on the layers
below and shape their results back into JSON. The routes are **thin** — they validate input,
delegate the real work to `agents/` (orchestration) and `domain/` (business logic), and depend on
adapters (Neo4j, Postgres, LLM providers, file storage) **only via dependency injection**, never by
constructing them. No business logic lives here: a route handler that reasoned about the graph
instead of asking the domain to would be the layering smell `AGENTS.md` warns against.

The layer's other job is the **contract**. The OpenAPI schema FastAPI derives from these routes —
their request/response models and their declared error outcomes — is dumped to a snapshot and
generates the typed TypeScript client the frontend uses. So a route's `responses=` map and its
Pydantic models aren't decoration; they are the source of the frontend's view of the API. Every
non-2xx outcome a route can return is declared explicitly so the typed client can model the failure
paths (404 / 409 / 502 / …), not just the happy path.

## Route groups

### `stories.py` — the story lifecycle

The large router (prefix `/stories`): the whole single-story pipeline plus every human edit on top
of it. The routes fall into groups, end-to-end across spec §7's pipeline and §3.3–§3.5's review and
correction surfaces. See [`api/stories.py`](../../backend/src/story_forge/api/stories.py).

- **Ingest** — `POST /upload` (accept a document, parse + language-detect, persist a project +
  story), `POST /{story_id}/structure` (build and persist the chapter/scene/paragraph tree),
  `POST /{story_id}/extract` (run the §3.3 extraction-and-judging cascade and stage candidates for
  review). These delegate to the chunking / extraction coordinators wired in `main.py`.
- **Read** — `GET /{story_id}/graph` (the entity graph as nodes + edges for the read-only viewer,
  with the §3.4 story-vs-project scope toggle), `GET /{story_id}/reader` (the story text with
  accepted entities highlighted inline, §3.5), `GET /{story_id}/entities/{entity_id}` (one entity's
  detail bundle + its 1-hop local graph for the reader side panel), and `GET /{story_id}/entities`
  (search the project's accepted entities for the Stage-4 *manual handpick*).
- **Review queue** — `GET /{story_id}/candidates` and accept / reject
  (`POST .../candidates/{candidate_id}/accept|reject`) drive the §3.3 Stage-4 human review of staged
  entity candidates; `GET /{story_id}/relations` and `POST .../relations/{relation_id}/decide` are
  the parallel queue for proposed relations. Accept/decide are the only paths that commit to the
  graph. The candidate view is enriched for *verifiable* merges (graph-quality §3 S3): the merge
  target's resolved name plus each alternative's type/aliases/sample quote. `GET
  /{story_id}/relations/{edge_id}/evidence` is the paired read — the recorded source paragraph(s) +
  quote(s) behind one committed edge (empty for a manually-added edge); it writes nothing.
- **Human graph edits** — `PATCH /{story_id}/entities/{entity_id}` (edit name/aliases/type/
  properties), `POST /{story_id}/relations` and `DELETE /{story_id}/relations/{edge_id}` (add /
  remove a relation edge directly), `POST /{story_id}/entities/{entity_id}/merge` (merge one entity
  into a survivor), and `DELETE /{story_id}/entities/{entity_id}` (delete an entity with its
  relations and occurrences). These reach the graph through the entity-edit service.
- **Occurrence correction** — `POST /{story_id}/paragraphs/{paragraph_id}/tags` (tag a text span as
  an existing or brand-new entity), `.../suppressions` (hide or re-assign a highlighted occurrence),
  and `.../boundaries` (change a highlight's span) are the §3.5 in-reader corrections.
- **Undo** — `POST /{story_id}/graph-edits/undo` reverses the newest not-yet-undone graph operation
  in the story's project, the general undo affordance behind the human edits above.

### `projects.py` — projects

Two read-only list routes (prefix `/projects`) that back a project/story picker: every project with
its story count, and a single project's stories (404-ing an unknown project so the picker can tell
"no such project" from "a project with no stories yet"). Project *creation* stays implicit-on-upload
— there is no `POST /projects` yet. See
[`api/projects.py`](../../backend/src/story_forge/api/projects.py).

### `llm.py` — agent-activity / cost status (spec §8.5)

A single thin read route, `GET /llm/status`, that the agent-activity panel (spec §8.5) consumes:
today's paid spend against the daily-budget cap, remaining budget, GPU-seconds and call counts, a
per-task-type breakdown, and the most recent call — all read from the `llm_calls` ledger via the
cost store. GPU *quota remaining* is deliberately not reported (it would need a live account-API
call); the route surfaces observed GPU-seconds rather than a number it can't yet obtain. See
[`api/llm.py`](../../backend/src/story_forge/api/llm.py).

### `responses.py` — the shared error shape

One model, `ErrorResponse` (a single `detail: str`), declared by every route's `responses=` map. It
is the body FastAPI's `HTTPException` produces, named once so the generated TypeScript client can
type the failure outcomes. There is exactly one such shared model across all routers — see
[`api/responses.py`](../../backend/src/story_forge/api/responses.py).

## Conventions that matter here

These are owned by [`backend/src/story_forge/AGENTS.md`](../../backend/src/story_forge/AGENTS.md)
("API routes"); read it before adding or changing a route.

- **Declare every non-2xx outcome.** Every status a route can `raise` must appear in the decorator's
  `responses={status: {"model": ErrorResponse, ...}}`, all using the one shared `ErrorResponse`.
  Without it the OpenAPI schema (and the typed frontend client) sees only the success status.
- **The 422 trap.** FastAPI auto-attaches a 422 *validation* shape to every route; declaring 422
  yourself for a domain error clobbers it and breaks the client's discrimination of the two cases.
  Remap the domain error to a different status (e.g. 413) instead.
- **Thin routes, no business logic.** Handlers validate and delegate; the graph reads/writes go
  through `domain/` and `agents/`, never Neo4j-in-the-handler. Adapters arrive by DI.

## How it connects

Routes call the orchestration in `backend/src/story_forge/agents/` and the pure logic in
`backend/src/story_forge/domain/`; the concrete adapters they need (Neo4j repo, Postgres
connection/stores, LLM coordinators, cost store, edit/review services) are constructed once in
[`main.py`](../../backend/src/story_forge/main.py) onto `app.state` and injected into handlers via
FastAPI `Depends`. `main.py` mounts the three routers (`stories`, `projects`, `llm`) and adds a
`/health` route. The OpenAPI schema these routes define is dumped
(`backend/scripts/dump_openapi.py`) and generates the frontend's typed client at
[`frontend/src/lib/api/schema.d.ts`](../../frontend/src/lib/api/schema.d.ts), which is how the
frontend data layer consumes this surface.

The neighbouring layers each have a reference note: [`backend-agents.md`](./backend-agents.md) (the
services these routes call), [`backend-domain.md`](./backend-domain.md) (the shapes they return),
and [`frontend-data-layer.md`](./frontend-data-layer.md) (the typed client that consumes this HTTP
surface).
