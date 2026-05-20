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

## Running locally

```bash
cd backend
uv sync
uv run uvicorn story_forge.main:app --reload --port 8000
```

Infra (Neo4j, Postgres, Ollama) comes from the root `docker compose up`.
