# Story Forge

A local web application for analyzing, annotating, and editing long-form narrative text — building a Neo4j knowledge graph of entities and relations along the way. Single-user, runs locally on a Linux/macOS dev machine.

This repo is **also a public portfolio piece**: a working demonstration of clean modular architecture, agent-based LLM orchestration, multi-model routing, and secure-by-default container infrastructure. See "What is this" below if you arrived here looking for that angle.

---

## Prerequisites

The dev environment expects a Linux-family shell (this README is bash-only; we develop on WSL2 Debian). Tooling required:

- `docker` (Compose v2)
- `git`
- `python3` (system; uv will install the project's pinned 3.12)
- `uv` ([install](https://docs.astral.sh/uv/getting-started/installation/))
- `node` ≥ 20 and `npm`
- `pre-commit`
- `detect-secrets`

Optional but recommended for the security CI step locally:
- `trivy` ([install](https://aquasecurity.github.io/trivy/))

---

## First-time setup

```bash
git clone <this-repo-url> story-forge
cd story-forge

# 1. Generate the two .env files
cp .env.example .env
cp backend/.env.example backend/.env

# 2. Fill in the secrets in both .env files
#    Generate random passwords with: openssl rand -hex 24
#    Paste real API keys where applicable (Ollama Cloud, Anthropic, OpenAI, Grok, OpenRouter)

# 3. Install pre-commit hooks
pre-commit install
pre-commit install --hook-type pre-push

# 4. Bring up infra (Neo4j, Postgres + pgvector, Ollama)
docker compose up -d
# Wait for healthchecks — the one-shot neo4j-init service applies infra/neo4j/init.cypher automatically.
# pgvector's CREATE EXTENSION runs once on first Postgres start via the mounted init.sql.

# 5. Install backend deps + run unit tests (no DB needed)
(cd backend && uv sync && uv run pytest -m "not integration" -q)
#    The integration suite additionally needs Postgres up (step 4) and a
#    TEST_DATABASE_URL line in backend/.env — see "Running tests" below.

# 6. Install frontend deps + start dev server
(cd frontend && npm install && npm run dev)

# 7. In a third terminal, start the backend
(cd backend && uv run uvicorn story_forge.main:app --reload --port 8000)
```

Open <http://localhost:5173>. The page fetches `http://localhost:8000/health` and renders ok / loading / error.

---

## Day-to-day dev workflow

Three terminals:

```bash
# infra
docker compose up

# backend
cd backend && uv run uvicorn story_forge.main:app --reload --port 8000

# frontend
cd frontend && npm run dev
```

### Running tests

The backend suite splits into two tiers, separated by the `integration` marker:

- **Unit** — pure, no Postgres. `cd backend && uv run pytest -m "not integration" -q`
- **Integration** — exercise a real Postgres. `cd backend && uv run pytest -m integration -q`
  (or just `uv run pytest -q` for both).

Integration tests never touch your dev database. A pytest session fixture owns a
throwaway DB end to end: it `CREATE DATABASE story_forge_test`, runs
`alembic upgrade head`, yields for the session, then `DROP`s it. Two prerequisites:

1. Postgres is up (`docker compose up -d` — step 4 above).
2. `backend/.env` defines `TEST_DATABASE_URL` pointing at a **distinct** DB name
   (`story_forge_test`) on that server. The `backend/.env.example` template carries
   the line; the simplest fill is to copy your `DATABASE_URL` and swap the trailing
   db name to `story_forge_test`. CI sets this via its Postgres service container.

### Verification commands

Everything that CI runs, locally:

```bash
# compose validity
POSTGRES_USER=v POSTGRES_PASSWORD=v POSTGRES_DB=v NEO4J_AUTH=neo4j/v \
  docker compose config --quiet

# backend (pytest -q runs both tiers; needs Postgres up + TEST_DATABASE_URL — see "Running tests")
(cd backend && uv sync && uv run ruff check . \
   && uv run ruff format --check . && uv run mypy && uv run pytest -q)

# frontend
(cd frontend && npm install && npm run lint && npm run format:check && npm run build)

# dependency-age + non-exact-pin sweep
python3 scripts/check_dependency_age.py

# secret scan against the committed baseline
detect-secrets scan --baseline .secrets.baseline

# container CVE scan (requires trivy)
for img in $(grep -E '^\s+image:' docker-compose.yml | awk '{print $2}'); do
  trivy image --severity HIGH,CRITICAL --exit-code 1 "$img"
done

# everything pre-commit can run
pre-commit run --all-files
```

---

## Branch + commit conventions

- Work happens on feature branches; **squash-merge** to `main` with a single curated commit per feature.
- Dirty WIP commits never reach `main`'s history. The linear `main` log should read like an intentional record of how the project was built.
- Throwaway experiments live as untracked scratch files (covered by `.gitignore`), not as branches.

---

## What is this (portfolio framing)

Story Forge is built in the open as a public PoC and doubles as a portfolio piece. Specifically, it demonstrates:

- **Agent-based LLM pipeline.** Chunking, extraction, matching, and judgment live in `backend/src/story_forge/agents/` as modular agents — each owns one task, one prompt template (Jinja2), one Pydantic output schema, and a preferred model tier.
- **Multi-model routing.** One `LLMProvider` Protocol; swappable adapters for local Ollama, Ollama Cloud free tier, and paid cloud via OpenRouter (the preferred paid route, reaching Grok/Anthropic/Google/OpenAI through one endpoint; direct vendor adapters added as needed). A small router picks a tier per call and fails over within a tier (network error, rate limit, schema-parse failure → next configured provider, swap logged).
- **Clean three-layer backend.** `api/` → `agents/` → `domain/` → `adapters/`. The domain is pure (no I/O); adapters implement protocols; agents compose. Every layer has its own `CLAUDE.md` with conventions.
- **Security-by-default infra.** Every container non-root, localhost-bound, on a private network. Every dependency pinned to an exact version ≥ 14 days old. Container images CVE-scanned in CI. No telemetry libraries. CORS strict. Secrets only in `.env`.
- **Spec-and-test-driven workflow.** `story-forge-poc-spec.md` is the source of truth; `docs/PLAN_LONG.md` / `docs/PLAN_SHORT.md` are living plans (conventions in `docs/CLAUDE.md`); ADRs in `docs/decisions/`. The commit history records the discipline.

For the full picture, read `story-forge-poc-spec.md` (the PoC spec), then the LLM ADRs `docs/decisions/0001-three-tier-llm-strategy.md` (three-tier strategy, superseded-in-part) and `docs/decisions/0003-llm-router-provider-order-and-budget.md` (router, provider order, budget), then `CLAUDE.md` files at the root and inside each major directory.

---

## License

MIT — see `LICENSE`.

## Security

See `SECURITY.md` for the vulnerability-reporting channel.

## Status

Active development. **M1 (Upload & structure) complete** as of 2026-05-26; entering **M2 (Basic extraction)** next — see `docs/PLAN_SHORT.md`.
