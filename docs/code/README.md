# Code reference — what's where, layer by layer

A descriptive map of the Story Forge codebase for a reader (or another agent) who wants to
understand **what each part is and what it's for** without opening every file. One note per layer:
each gives the layer's responsibility, a walk through its modules, and how it connects to its
neighbours.

This is the **reference** layer. Two companions sit either side of it:

- [`../CODE_GUIDE.md`](../CODE_GUIDE.md) — the **navigation** layer: where to *start* reading and in
  what order. Read it first if you're new.
- The per-directory `AGENTS.md` files and the [spec](../../story-forge-poc-spec.md) — the
  **authoritative** layer: the conventions and the *what*-we-build, which stay current. When a note
  here and one of those disagree, **they win** — tell us, this note drifted.

These notes describe at *module altitude* — responsibilities and relationships, not signatures or
line-by-line behaviour. For the exact surface, follow the links into the code, whose docstrings
carry the per-symbol detail. (How they're written and kept honest: the `/document-code` skill's
`reference` mode, under the `code-scribe` doctrine.)

## The layers

**Backend** (`backend/src/story_forge/`) — strict layering `api → agents → domain → adapters`:

| Note | Layer | What it covers |
|---|---|---|
| [`backend-domain.md`](./backend-domain.md) | `domain/` | The pure shapes and deterministic rules — the bottom of the dependency graph, no I/O. |
| [`backend-agents.md`](./backend-agents.md) | `agents/` | The ingest pipeline and the human-gate write services — chunk → extract → match → judge → review → graph. |
| [`backend-adapters.md`](./backend-adapters.md) | `adapters/` | The I/O bridges — Postgres, Neo4j, the LLM providers, the filesystem. |
| [`backend-api.md`](./backend-api.md) | `api/` | The thin FastAPI HTTP surface and its OpenAPI contract. |

**Frontend** (`frontend/src/`) — React + TypeScript:

| Note | Area | What it covers |
|---|---|---|
| [`frontend-features.md`](./frontend-features.md) | `features/` | One folder per screen — upload, chunking, review queues, graph viewer, text reader. |
| [`frontend-data-layer.md`](./frontend-data-layer.md) | `lib/api/` + `app/` | The typed client, the TanStack Query hooks, and app wiring — the seam to the backend. |
