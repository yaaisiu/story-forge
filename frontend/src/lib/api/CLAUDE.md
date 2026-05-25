# CLAUDE.md — frontend/src/lib/api/

The typed API client lives here. Two parts:

- **`schema.d.ts`** — auto-generated from the backend's OpenAPI schema by
  `openapi-typescript@7.13.0`. **Never hand-edit this file.** Any change to a
  backend route signature is expected to show up here as a diff after a regen.
- **(later)** small hand-written TanStack Query hooks that consume the schema
  types — one file per logical operation. The first hook lands in Session 6
  with the upload mutation; the conventions (plain, commented, written for an
  outsider; `useQuery`/`useMutation` only, no `useEffect(fetch...)`) live in
  `frontend/src/CLAUDE.md`.

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
