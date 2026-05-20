# PLAN_SHORT.md — Current milestone tactical plan

> Updated every working session. Read at start (`/resume-session`); update at end (`/wrap-session`).

<!-- ───────────────────────────── HANDOFF ─────────────────────────────
This block is the contract between `/wrap-session` (writes it) and
`/resume-session` (reads it). It always describes where the NEXT session
should start. Keep it short and literal. Do not delete the markers.
────────────────────────────────────────────────────────────────────── -->

## ▶ Session handoff (read this first)

- **Next session:** Session 2 — Upload + language detection + parsing
- **Read before starting:** this file, spec §3.1 (upload & text splitting), §7 (ingest pipeline, step by step), §6.4 (data model — `stories`/`projects`) and §6.3 (project structure — `api/stories.py`), `backend/CLAUDE.md`, `backend/src/story_forge/CLAUDE.md`
- **Verify on disk:** Postgres running with pgvector (`docker compose ps` → postgres healthy; user-managed `.env` + `backend/.env` exist but are gitignored — do not open them); `backend/.env` must define `TEST_DATABASE_URL` for the integration suite to run (per `backend/CLAUDE.md` "Running tests"); Session 1 anchors present — `backend/alembic/versions/*_create_document_tree.py`, `adapters/postgres_repo.py`, `domain/models.py`, `tests/conftest.py` (test-DB fixture), `tests/integration/`; no `api/stories.py` yet, no parsing/detection helpers in `domain/` yet — Session 2 creates these
- **Last session ended:** 2026-05-20 — Session 1 complete. Postgres document-tree schema + async-psycopg repo + integration-test harness landed; backend gate green (11 tests). On branch `session-1-persistence-foundation`, headed for a private-repo PR (CI validates the new pgvector service path).
- **Open blocks/questions:** First work step is a **failing upload-endpoint / parser test** (test-first). **Decide in-session: language-detection library** (`langdetect` vs `fasttext`) — see "Blocked / questions"; resolve before writing the detection helper. Session 3 (chunking threshold) decision still deferred.

<!-- ─────────────────────────── END HANDOFF ──────────────────────────── -->

## Current milestone: Milestone 1 — Upload & structure

**Goal:** upload a story file (txt / md / docx), detect its language, and produce a
structured outline (chapters → scenes → paragraphs) saved to Postgres. Outline editable
in the UI. ChunkingAgent (local Ollama + Ollama Cloud fallback) drives auto-chunking.

M1 is split into **6 sessions**, each sized for one Claude Code conversation. Each ends
green (lint/type/tests reported clean) and committed, and leaves a resume anchor so the
next session can pick up by reading this file. Order is by dependency — do not reorder
without updating the handoff block.

---

### Session 1 — Persistence foundation `[x]`

_No LLM, no HTTP. Pure schema + repository._

_Test-DB harness comes first (it's the failing-test scaffolding), then the schema._

- [x] **Test harness:** add `test_database_url` to `config.py` + `backend/.env.example`; `tests/conftest.py` session fixture that `CREATE DATABASE story_forge_test` → `alembic upgrade head` → yields → `DROP DATABASE`; an `integration` pytest marker so unit tests need no Postgres
- [x] **CI:** add a `pgvector/pgvector:0.8.1-pg17-bookworm` service container + test env to the backend job in `.github/workflows/ci.yml` (currently runs `pytest` with no DB)
- [x] **Docs:** README + `backend/CLAUDE.md` — infra-up, test-DB lifecycle, unit-only vs integration commands
- [x] Domain models (Pydantic) for the document tree: `Project`, `Story`, `Chapter`, `Scene`, `Paragraph` (`domain/`, I/O-pure)
- [x] First Alembic migration: create `projects`, `stories`, `chapters`, `scenes`, `paragraphs` (spec §6.4, `order_index` not `order`); enable the `vector` extension via `op.execute` if absent
- [x] `adapters/postgres_repo.py` — async psycopg session + basic CRUD for the new tables (C/R/D; generic Update deferred to the Session 4 reorder, where `order_index` renumber is the realistic update)
- [x] Tests: migration up/down; repo CRUD (integration, against `story_forge_test`)

**Done when:** `alembic upgrade head` builds the schema and repo CRUD tests pass (locally + CI).
**Resume anchor:** migration file under `backend/alembic/versions/` + `adapters/postgres_repo.py` exist; domain models present; `tests/conftest.py` test-DB fixture present.

### Session 2 — Upload + language detection + parsing `[ ]`

_Decision in-session: language-detection library (see Blocked/questions)._

- [ ] `POST /stories/upload` accepting txt / md / docx; size + MIME validation; uploads sandboxed to a dedicated dir
- [ ] Parsing helpers: docx / md / txt → raw text + paragraph blocks (`domain/`)
- [ ] Language detection helper — PL / EN
- [ ] Persist `Story` (+ `Project`) via the Session 1 repo, storing raw text and detected language
- [ ] Tests: upload happy path, rejected validation (bad MIME / oversize), detection units, parser units

**Done when:** uploading a file creates a `Story` row with detected language and stored raw text.
**Resume anchor:** `api/stories.py` upload route live; parsing + detection helpers in `domain/`.

### Session 3 — LLM Protocol + OllamaProvider + ChunkingAgent (auto mode) `[ ]`

_Decision in-session: long-text → cloud-free threshold heuristic (see Blocked/questions)._

- [ ] `LLMProvider` Protocol (`adapters/llm/base.py`) per spec §6.5
- [ ] Minimal `OllamaProvider` — local tier (host swap + optional key reaches cloud-free; only what's needed now)
- [ ] `prompts/chunking.pl.j2` + `prompts/chunking.en.j2` (Appendix C.1 skeleton) + Pydantic output schema
- [ ] `agents/chunking_agent.py` — load prompt → call provider → parse + validate → retry on failure; auto-chunk via local, fall back to cloud-free for longer texts
- [ ] Tests: agent with **mocked** `LLMProvider`; schema-validation + retry path

**Done when:** the agent turns raw text into a proposed outline against a mocked provider; retry-on-bad-JSON proven.
**Resume anchor:** `agents/chunking_agent.py`, `adapters/llm/base.py`, `adapters/llm/ollama.py`, `prompts/chunking.*.j2` exist.

### Session 4 — Chunking modes + outline persistence `[ ]`

- [ ] Manual / hybrid chunking: parse `## Chapter` / `### Scene` markdown anchors into a tree; agent fills the gaps in hybrid mode (`domain/`)
- [ ] Endpoint to run/accept chunking and save the outline (chapters/scenes/paragraphs) to Postgres
- [ ] Tests: manual parse, hybrid fill, persist e2e (mocked LLM)

**Done when:** full ingest → outline persisted, in all three modes (auto / manual / hybrid).
**Resume anchor:** backend M1 complete; chunking endpoints persist the tree.

### Session 5 — Frontend foundation `[ ]`

_No feature UI yet — just the shell M0 never built._

- [ ] Add Tailwind + shadcn/ui base, React Router, and a TanStack Query provider in `src/app/`
- [ ] Convert or remove the M0 `/health` page (uses a forbidden `useEffect(fetch...)`)
- [ ] Generate the API client with `openapi-typescript` from the backend's `openapi.json` into `src/lib/api/`; hand-write TanStack Query hooks (plain, commented)
- [ ] Tests: app shell renders with routing + query provider

**Done when:** the app shell renders under React Router with a TanStack Query provider; typed API client generated.
**Resume anchor:** `src/app/` wired (router + providers); `src/lib/api/` populated.

### Session 6 — Frontend upload + outline UI `[ ]`

- [ ] Upload screen: file picker, drag-drop, language indicator
- [ ] Outline view: markdown-style editor with `## Chapter` / `### Scene` markers + live preview
- [ ] TanStack Query hooks wired to the generated client (`src/lib/api/`)
- [ ] One e2e happy-path test (upload → outline)

**Done when:** the full M1 flow is usable in the browser.
**Resume anchor:** M1 done — update `PLAN_LONG.md` and roll the handoff block to Milestone 2.

---

### Cross-cutting (do as the relevant session touches it)

- [ ] Update spec §10 if any open question hardens (extraction granularity, etc.)

### Blocked / questions

- **Decide in Session 2 — language-detection library:** `langdetect` (pure-Python, tiny, no model download) vs `fasttext` (faster/more accurate, needs the `lid.176` model artifact). Both must satisfy the exact-pin ≥14-day rule. _(Deferred to M1 by decision 2026-05-20; revisit with a grounded comparison at that task.)_
- **Decide in Session 3 — auto-chunking trigger heuristic:** which threshold decides "long enough → use Ollama Cloud instead of local"? Probably a word-count threshold; needs a number.

### Decided

- **2026-05-20 — Primary keys are app-generated UUIDs (`uuid4`), not serial integers.** Paragraph/entity IDs are referenced cross-store (Neo4j `source_paragraph_id`, `entity_mentions.paragraph_id`), so store-independent stable IDs avoid sequence coordination between Postgres and Neo4j. DB carries `gen_random_uuid()` as a safety default; the repo inserts the model's id explicitly.
- **2026-05-20 — The document-tree migration is hand-written raw SQL (`op.execute`), not `op.create_table`.** A faithful 1:1 transcription of spec §6.4 — including `vector(768)` — without pulling a pgvector SQLAlchemy type into the dep set just to express one column. `target_metadata` stays `None`; no ORM layer (repo is raw async psycopg, columns map 1:1 to domain fields).
- **2026-05-20 — Repo scope is Create/Read/Delete for now; generic Update deferred.** The realistic update is renumbering `order_index` on reorder, which lands with chunking persistence (Session 4); not added speculatively.
- **2026-05-20 — Recipe for adding an `.env`-backed setting recorded in `backend/CLAUDE.md`** (retro outcome): placeholder in `.env.example` → hand the user an append command → dependent tests stay red until set. Captures the friction this session so Neo4j creds / LLM keys don't re-derive it.
- **2026-05-20 — Integration tests use a dedicated `story_forge_test` DB, fixture-managed in the same Postgres instance.** A pytest session fixture creates it, runs `alembic upgrade head`, yields, then drops it. Chosen over an ephemeral compose service / testcontainers: no new dependency, dev data untouched, deterministic. CI gets a pgvector service container.
- **2026-05-20 — Sibling ordering column is `order_index` (plain integer ordinal).** Avoids `order` (SQL reserved word → forced quoting); same name used end-to-end (DB / Pydantic / JSON), no mapping layer. Integer ordinal renumbered on reorder; fractional/lexical rank deferred as speculative. Spec §6.4 amended (inline note), SQL updated.
- **2026-05-20 — M1 sliced into 6 resumable sessions** (this file's structure). Each session is one-conversation-sized, ends green + committed, and records a resume anchor in the handoff block. Driven by `/wrap-session` (end) and `/resume-session` (start).
- **2026-05-20 — API client generator: `openapi-typescript`** (over `orval`/`hey-api`). Emits TS types + a tiny typed `openapi-fetch` client from the backend's `openapi.json`; we hand-write the TanStack Query hooks in `src/lib/api/`, keeping them plain/commented for an outsider. Chosen for the smallest dependency surface and most legible data layer in a portfolio repo.

### Done in previous sessions

- **2026-05-20 — Session 1 complete: persistence foundation.** Postgres document tree (Project → Story → Chapter → Scene → Paragraph, spec §6.4) shipped end to end: I/O-pure Pydantic domain models (`domain/models.py`, UUID PKs, `order_index`); a raw-SQL Alembic migration (cascade FKs, `vector(768)`, `CREATE EXTENSION vector`, child-lookup indexes, reversible downgrade); an async-psycopg repo (`adapters/postgres_repo.py`, C/R/D). Integration-test harness landed: `tests/conftest.py` owns a throwaway `story_forge_test` DB (create → `alembic upgrade head` → yield → drop) with a transactional `db_conn`, and an `integration` marker so unit tests need no Postgres. CI backend job gained a `pgvector/pgvector:0.8.1-pg17-bookworm` service container + `TEST_DATABASE_URL`. Docs: README "Running tests" + status → M1; `backend/CLAUDE.md` test-DB lifecycle. Backend gate green — 11 tests (1 unit + 10 integration), ruff + mypy clean. Incidental: fixed the Alembic ruff post-write hook (`console_scripts` → `exec`, it had never run) and refreshed `.secrets.baseline` for the CI throwaway password + Alembic URL placeholder. **Process (retro):** added the "Adding a setting that tests/app read from `.env`" recipe to `backend/CLAUDE.md`; rejected splitting incidental fixes into separate commits (squash-merge collapses them anyway; the commit body discloses them).
- **2026-05-20 — Session 1 groundwork (no production code).** Amended spec §6.4: `order` → `order_index` with a naming/ordering convention note (squash-merged to `main`). Added the `/retro` process-retrospective skill, referenced from `/wrap-session`. Decided the test-DB approach (fixture-managed `story_forge_test`). Diagnosed why `docker compose up postgres` failed (missing root `.env`); user created `.env`/`backend/.env` themselves and verified Postgres + pgvector running locally. Clarified `backend/.env.example` DATABASE_URL password sourcing (and refreshed `.secrets.baseline` rather than using a leak-prone allowlist pragma). Hardened secret handling: tracked `.claude/settings.json` denies agent `Read`/`Edit`/`Write` on `.env`, plus matching `CLAUDE.md` security clauses. Expanded Session 1 task list with the test harness + CI Postgres service + docs work that must precede the schema. Fixed a `/wrap-session` ordering bug — the `/retro` prompt now runs *before* the bookkeeping steps so their output is captured (it previously ran last, leaving the wrap stale).
- **2026-05-20 — M1 planning.** Restructured this file into 6 sessions; added `/wrap-session` and `/resume-session` skills and referenced them in root `CLAUDE.md`. No production code written.
- **2026-05-19 — M0 (Setup) complete.** Repo skeleton scaffolded end-to-end:
  - Foundation: `LICENSE` (MIT), `SECURITY.md`, `.gitignore`, setup-first `README.md`, root `CLAUDE.md`.
  - Governance: `PLAN_LONG.md`, this file, `docs/decisions/0001-three-tier-llm-strategy.md`.
  - Infra: `docker-compose.yml` (Neo4j, Postgres+pgvector, Ollama, one-shot `neo4j-init`), `infra/ollama/Dockerfile` (non-root wrapper), `infra/neo4j/init.cypher` (constraints + indexes), `infra/postgres/init/01-pgvector.sql`.
  - Env: split `.env.example` (repo-root + `backend/.env.example`).
  - Backend: `pyproject.toml` (hatchling, exact pins ≥14d), `src/story_forge/{main,config,__init__}.py`, Alembic harness, async `/health` test via `httpx.ASGITransport`.
  - Frontend: Vite + React 19 + TypeScript 6 skeleton, eslint flat config, prettier, `/health` smoke page.
  - Scripts: `check_dependency_age.py` (strict on ranges + age), `check_ollama_cloud.py`.
  - CI: GitHub Actions with `backend`, `frontend`, `security` (incl. Trivy on 3 images), and `ollama-cloud-smoke` jobs.
  - Pre-commit: detect-secrets v1.5.0 (with baseline), ruff lint + format, whitespace hooks, dep-age as pre-push.
  - Lockfiles generated: `backend/uv.lock`, `frontend/package-lock.json`, `.secrets.baseline`.
  - Verification clean: compose config, ruff/ruff-format/mypy-strict/pytest, eslint/prettier/build, dep-age (24/24 deps), detect-secrets.
  - Deferred: local Trivy scan (no `trivy` in WSL — CI handles it); `pre-commit run --all-files` (no git repo yet, per Phase 2 rule).

---

## How the two skills use this file

- **`/resume-session`** (session start) reads the **Session handoff** block, verifies the on-disk anchors it names, runs `git log`/`git status`, opens the spec sections listed, and confirms reality matches before work begins.
- **`/wrap-session`** (session end) runs the green-state checks (report-only), checks off completed tasks, strikes (does not delete) obsolete ones, appends a dated line to **Done in previous sessions**, refreshes **Blocked / questions** and **Decided**, and rewrites the **Session handoff** block to point at the next session. It then reminds you to commit on a feature branch (squash-merge hygiene).
- **When a spec change happened:** both skills stop and require `story-forge-poc-spec.md` + `PLAN_LONG.md` to be reconciled with this file before continuing.
