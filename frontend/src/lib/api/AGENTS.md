# AGENTS.md — frontend/src/lib/api/

The typed API client lives here. Two parts:

- **`schema.d.ts`** — auto-generated from the backend's OpenAPI schema by
  `openapi-typescript@7.13.0`. **Never hand-edit this file.** Any change to a
  backend route signature is expected to show up here as a diff after a regen.
- **(later)** small hand-written TanStack Query hooks that consume the schema
  types — one file per logical operation. The first hook lands in Session 6
  with the upload mutation; the conventions (plain, commented, written for an
  outsider; `useQuery`/`useMutation` only, no `useEffect(fetch...)`) live in
  `frontend/src/AGENTS.md`.

## Regenerating

Two steps, deliberately separate so the frontend build is hermetic (no live
backend dependency at build/CI time):

```bash
# 1) From repo root — refresh the committed schema snapshot.
uv --project backend run python backend/scripts/dump_openapi.py \
    frontend/openapi.json

# 2) From frontend/ — regenerate the TypeScript client from the snapshot.
npm run generate:api
```

Commit both `openapi.json` and `schema.d.ts` together. A PR that changes one
without the other means the snapshot drifted from the generated client — a
review red flag.

**Regenerating the client does NOT update its consumers — grep them.** When a
backend route's request/response _shape_ changes (a renamed/added/removed field,
e.g. M3.S4a's `ExtractResponse.{entities_written,relations_written}` →
`candidates_staged`), regenerating `schema.d.ts` updates the _types_ but leaves
every hand-written usage — hooks, components, and especially **test fixtures**
that build the old shape — referencing the gone field. Those fail `tsc` (the
`build` step), not lint. So after a regen, `grep -rn "<old_field>\|<new_field>"
frontend/src` and reconcile each hit. (M3.S4a / PR #63: three test fixtures kept
`entities_written` and bounced the frontend CI build — the regen looked done but
the consumers weren't. Review-side mirror: `/review-pr` §2.)

## Derive an HTTP status code's meaning from the backend route, not a sibling feature

When a hand-written hook or component branches on a response **status code** — an
error-message mapper, a retry decision, a 4xx/5xx discriminator — read what that status
_actually means_ off the backend route that raises it (`backend/src/story_forge/api/`),
**not** a status→meaning mapping copy-adapted from a sibling feature. The generated
`schema.d.ts` names every declared status (`responses=`) but not its semantics, so a
copied mapper silently inherits the _wrong_ meaning when the new route uses the same code
differently. And a **test fixture that fabricates an error body** (`jsonResponse(409,
{detail: "..."})`) must use a status + detail the real route can return — a fabricated
body validates fiction and makes the broken mapping pass green.

(M3.S4f / PR #78: `RelationQueue`'s `decideMessage` copy-adapted the candidate queue's
mapper and mapped **409 → "already decided"**, but the decide route returns 409 for a
_stale/held endpoint_ (`RelationEndpointsUnresolved`) and already-decided is a **200**
with `already_decided:true`. The test stubbed a `409 {detail:"relation already decided"}`
the backend never sends, so it passed and _masked_ the inversion. The single `/review-pr`
even listed "409 surfaces an error" as checked-clean without opening the route; the
multi-agent `/code-review` caught it. Review-side mirror: `/review-pr` §2.)

## A mutation invalidates _every_ cache its write dirties — not just the obvious one

When a mutation hook (or a component's `onSuccess`) succeeds, enumerate **every** query whose
data the write just changed and invalidate **all** of them — not only the list the feature is
"about". A write usually touches more than one cached view: an upload changes the per-story graph
_and_ the project list _and_ that project's story list; an accept changes the review queue _and_
the graph. Missing one leaves that view stale until its `staleTime` lapses — looks like the write
silently failed. Trace the write's effects across the cache, then invalidate each. Key the
invalidation off data you reliably have (often the **response body**, e.g. the returned
`project_id`), so it's correct for every branch (new-project vs add-into-existing). Cross-check:
for each query hook that could display the mutated entity, is there a matching
`invalidateQueries` on the write path? (Earned M4 multi-story, Session 53: `useUploadStory`
invalidated nothing, so the new `/projects` + `/projects/{id}/stories` lists were stale for the
30 s `staleTime` after an upload — the picker looked broken. Caught by the slice's multi-agent
`/code-review`, not the self-review. Note the **converse** limit, deferred to `docs/BACKLOG.md`:
graph invalidation keyed on `["story-graph", <storyId>]` does _not_ reach a _sibling_ story's
project-scoped view — invalidating the whole `["story-graph"]` family is the V1 fix.)

## Why `openapi-typescript` runs via `npx`, not as a devDependency

`openapi-typescript@7.13.0` declares a peer of `typescript@^5.x` while this
project is on `typescript@6.0.3`. Upstream hasn't bumped the peer yet (verified
2026-05-25 against npm registry). Installing it as a devDependency hits
`ERESOLVE`; running it on demand via `npx -y openapi-typescript@7.13.0` (pinned
exactly in `package.json`'s `generate:api` script) avoids polluting the
dependency tree while keeping the version explicit. Trade-off acknowledged:
this single tool isn't visible to `scripts/check_dependency_age.py` or
`npm audit`. At pin time (2026-05-25) the version was 103 days old and
OSV-clean (`https://api.osv.dev/v1/query`, npm ecosystem, returned `{}`).
Revisit when upstream supports TS 6 and the peer relaxes.
