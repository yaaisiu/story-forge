# PLAN_SHORT.md — Current milestone tactical plan

> Updated every working session. Read at start; update at end.

## Current milestone: Milestone 1 — Upload & structure

**Goal:** ability to upload a story file (txt / md / docx), detect its language, and produce a structured outline (chapters → scenes → paragraphs) saved to Postgres. Outline editable in the UI.

### Tasks

- [ ] Backend: `POST /stories/upload` accepting txt / md / docx; size + MIME validation; uploads sandboxed to a dedicated dir
- [ ] Language detection helper (`langdetect` or `fasttext`) — PL / EN
- [ ] First Alembic migration: create `projects`, `stories`, `chapters`, `scenes`, `paragraphs` tables (spec §6.4); enables `vector` extension via `op.execute` if not already present
- [ ] Postgres repository (adapters/postgres_repo.py) — async psycopg session, basic CRUD for the new tables
- [ ] LLM Protocol + minimal `OllamaProvider` adapter (local tier only at first)
- [ ] `ChunkingAgent` with Jinja2 prompt (`prompts/chunking.pl.j2`, `prompts/chunking.en.j2`) + Pydantic output schema; auto-chunking via local Ollama, falling back to Ollama Cloud for longer texts
- [ ] Manual / hybrid chunking modes (anchors inserted by user, agent fills the rest)
- [ ] Frontend: upload screen (file picker, drag-drop, language indicator)
- [ ] Frontend: outline view (markdown-style editor with `## Chapter` / `### Scene` markers; live preview)
- [ ] Frontend: TanStack Query + the generated API client (`src/lib/api/`)
- [ ] Tests: unit tests for the chunking domain helpers; agent test with mocked `LLMProvider`; one e2e happy-path test
- [ ] Update spec §10 if any open question hardens (extraction granularity, etc.)

### Blocked / questions

- Which auto-chunking trigger heuristic decides "long enough → use Ollama Cloud instead of local"? Probably word-count threshold; needs a number.

### Done in previous sessions

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

## When this file changes

- **Start of session:** read it, refresh memory of where we are.
- **During work:** check off tasks as you complete them; add tasks as they emerge; strike through (don't delete) ones that became obsolete.
- **End of session:** ensure the file reflects reality, write a one-line summary of what was accomplished into the "Done in previous sessions" area, list any open questions or blocks.
- **When a spec change happens:** review this file and `PLAN_LONG.md` together. Both updated before resuming work.
