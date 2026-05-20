# CLAUDE.md — backend/

This directory holds the Python FastAPI backend.

## Conventions

- Python 3.12 (pinned via `.python-version`, capped `<3.13` in `pyproject.toml`)
- Environment managed by `uv` (`uv sync`, `uv run`)
- Dependency pins in `pyproject.toml` — exact versions, minimum 14 days old
- Format: `ruff format`. Lint: `ruff check`. Type: `mypy --strict` on `src/`
- Tests: `pytest`. Async tests with `pytest-asyncio`. Coverage tracked but not gated initially
- Logging: structlog, JSON in production-mode, pretty in dev. Never log auth headers, API keys, or PII

## Layering (strict — see `src/story_forge/CLAUDE.md` for details)

`api → agents → domain → adapters`. Domain depends on nothing infrastructural. Agents compose domain logic with an `LLMProvider` Protocol. Adapters implement protocols. API depends on agents and domain and (only via DI) on adapters.

## Test placement

- Unit tests: `tests/unit/<mirror of src path>/`
- Integration tests (real Neo4j, real Postgres, mocked LLMs): `tests/integration/`
- Agent tests with mocked `LLMProvider`: `tests/unit/agents/`
- E2E: `tests/e2e/`

## Running tests

Two tiers, separated by the `integration` pytest marker (registered in `pyproject.toml`):

```bash
uv run pytest -m "not integration"   # unit only — no Postgres, no network
uv run pytest -m integration         # integration only — needs Postgres
uv run pytest                        # both
```

Integration tests run against a throwaway database, never your dev data. The
session fixture in `tests/conftest.py` `CREATE DATABASE story_forge_test`, runs
`alembic upgrade head`, yields, then `DROP`s it. Each test gets a `db_conn`
(async psycopg) wrapped in a transaction that is rolled back on teardown, so
tests stay isolated without rebuilding the schema between them.

Prerequisites for the integration tier:
- Postgres up (`docker compose up -d` from the repo root).
- `backend/.env` defines `TEST_DATABASE_URL` — a **distinct** DB name
  (`story_forge_test`) on the same server as `DATABASE_URL`. `.env` is
  user-managed (never edited by the agent); the template lives in `.env.example`.

Alembic's `env.py` only injects `settings.database_url` when no URL was supplied,
so the fixture can point migrations at the test DB by setting `sqlalchemy.url` in
a `Config` it builds itself.

## Running locally

```bash
cd backend
uv sync
uv run uvicorn story_forge.main:app --reload --port 8000
```

Infra (Neo4j, Postgres, Ollama) comes from the root `docker compose up`.
