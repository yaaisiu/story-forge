# Frontend data layer — API client, query hooks, app wiring

> **Reference note.** What lives in `frontend/src/lib/api/` and `frontend/src/app/`, and what each
> piece is for. The code and [`frontend/src/AGENTS.md`](../../frontend/src/AGENTS.md) /
> [`frontend/AGENTS.md`](../../frontend/AGENTS.md) own the details and stay current — this note is a
> map of the territory, not a copy of it.

## What this layer is responsible for

This is the seam between the React screens and the backend. Every call to the API goes through a
**TanStack Query** hook layered over a thin, typed `fetch` client; the request/response types come
from a TypeScript contract generated from the backend's OpenAPI schema, so a backend route change
shows up here as a type error rather than a silent drift. **No component fetches directly** — the
house rule (`frontend/src/AGENTS.md`) is `useQuery`/`useMutation` only, never `useEffect(fetch...)`,
so components render and dispatch while caching, retries, and request state live in the hooks.

The hooks share a small discipline that keeps views fresh: **query-key factories** (one exported
function per cached view, so keys are spelt once and reused), **invalidation-on-mutation** (a write
invalidates every cached view its effect dirties — see the AGENTS.md note on that failure mode), and
**stale-while-revalidate** reads (a 30 s `staleTime` paints cached data instantly on revisit). The
client itself is deliberately tiny (a hand-typed `fetch`, no `openapi-fetch` dependency) and errors
are surfaced as a typed `ApiError` so callers discriminate failure modes by HTTP status, never by
string-matching a message.

## The typed client (`lib/api/client.ts` + generated `schema.d.ts`)

[`client.ts`](../../frontend/src/lib/api/client.ts) is a hand-written `fetch` wrapper: a small set of
verb helpers (`getJson`, `postJsonBody`, `patchJsonBody`, `del`, `postFormJson`) that build the
request, parse the JSON body, and on any non-2xx throw an `ApiError` carrying the HTTP `status`, a
human-readable `detail`, and the raw parsed `body`. The `detail` is unwrapped from **both** backend
error shapes by `extractDetail`: the project's `ErrorResponse` (`{detail: string}`) and FastAPI's
auto-generated `HTTPValidationError` (`{detail: ValidationError[]}`, joined into one string) — and
the raw `body` is kept on the error for the rare caller that must branch on the validation-error
structure. `del` tolerates the `204 No Content` empty body; `postFormJson` leaves the `Content-Type`
unset so the browser sets the multipart boundary itself.

[`schema.d.ts`](../../frontend/src/lib/api/schema.d.ts) is **generated** (by `openapi-typescript`
from the backend's OpenAPI snapshot) and is **never hand-edited** — it is the typed contract the
hooks import their request/response types from (`components["schemas"][...]`). Regeneration and the
"regen doesn't update consumers" trap are documented in
[`lib/api/AGENTS.md`](../../frontend/src/lib/api/AGENTS.md).

## The query/mutation hooks (`lib/api/use*.ts`)

One file per logical operation (~25 hooks), each exporting its query-key factory, its schema-derived
types, and the hook. They fall into a few groups by concern:

- **Read queries** — `useProjects` / `useProjectStories` (the multi-story picker), `useStoryGraph`
  (the entity graph, with a `story`/`project` scope param folded into the key), `useReader` (story
  text + inline highlights), and `useEntityDetail` (one entity's properties + 1-hop ego-graph for the
  side panel). Shared patterns: a 30 s stale-while-revalidate window, and **disabled-until-id**
  (`enabled: Boolean(storyId)`) so a query never fires with `undefined` in the path during an initial
  render or deep-link race. `useEntitySearch` is the read used by the reviewer's manual-handpick
  duplicate search.

- **Ingest mutations** — `useUploadStory` (`POST /stories/upload`), `useStructureStory` (build the
  document tree, auto/manual/hybrid), and `useExtractStory` (run the resumable extraction pass).
  These drive the pipeline forward; `useUploadStory` invalidates the project + story lists off its
  response's `project_id`.

- **Review-queue hooks** — `useCandidates` / `useReviewCandidate` (the Stage-4 entity review gate)
  and `useRelations` / `useDecideRelation` / `useAddRelation` / `useRemoveRelation` (the relation
  decide gate and manual edge writes). An accept/decide invalidates the queue (so the decided item
  drops off) and, when it writes the graph, the story graph too.

- **Human-edit mutations** — the manual write surface over committed graph state:
  `useEntityEdit` / `useDeleteEntity` / `useMergeEntities`, the occurrence-level
  `useSuppressOccurrence` / `useTagOccurrence` / `useChangeBoundaries`, and `useUndo` (reverses the
  last graph edit; previews without mutating cache, applies with a fan-out invalidation of reader +
  graph + every entity-detail bundle). These are the human-reached writes that feed the
  correction-as-evidence flywheel.

- **Status poll** — `useLlmStatus` reads `GET /llm/status` (today's spend, GPU-seconds, per-task
  breakdown, last call) for the §8.5 agent-activity panel, using `refetchInterval` to short-poll
  while mounted so the panel reflects an in-flight run live.

The per-hook request/response shapes, the exact endpoints, and the precise invalidation set for each
mutation live in the hook files and [`lib/api/AGENTS.md`](../../frontend/src/lib/api/AGENTS.md) — read
those, not a copy here.

## App wiring (`app/`)

[`AppShell.tsx`](../../frontend/src/app/AppShell.tsx) is a thin wrapper that just renders the route
table — it assumes a router and a `QueryClientProvider` are mounted above it (production wraps it in
`BrowserRouter`; the render test wraps it in `MemoryRouter`), so it stays trivial to test and
compose. [`routes.tsx`](../../frontend/src/app/routes.tsx) is the one-module route table mapping each
URL to a feature screen (upload, projects, structure, graph, review, relations, reader); the graph
viewer is `lazy`-loaded to keep cytoscape out of the initial bundle.
[`queryClient.ts`](../../frontend/src/app/queryClient.ts) is a `createQueryClient()` **factory** (not
a singleton, so tests build their own with `retry: false`) whose defaults suit a single-user local
app: no retries, no refetch-on-focus, a 30 s `staleTime`. There are no `src/stores/` (Zustand) or
`src/hooks/` directories yet — cross-component client state hasn't needed them.

## How it connects

The hooks call the backend's `api/` routes and feed the `features/` screens: a screen calls a hook,
the hook calls the typed client, the client calls a FastAPI route, and the route returns a
domain-shaped JSON body the hook's schema types describe. The feature screens that consume these
hooks and the backend routes they call each have their own reference note:
[`frontend-features.md`](./frontend-features.md) (the screens) and
[`backend-api.md`](./backend-api.md) (the routes behind the client).
