# AGENTS.md — backend/

This directory holds the Python FastAPI backend.

## Conventions

- Python 3.12 (pinned via `.python-version`, capped `<3.13` in `pyproject.toml`)
- Environment managed by `uv` (`uv sync`, `uv run`)
- Dependency pins in `pyproject.toml` — exact versions, minimum 14 days old
- Format: `ruff format`. Lint: `ruff check`. Type: `mypy --strict` on `src/`
- Tests: `pytest`. Async tests with `pytest-asyncio`. Coverage tracked but not gated initially
- Logging: structlog, JSON in production-mode, pretty in dev. Never log auth headers, API keys, or PII

## Layering (strict — see `src/story_forge/AGENTS.md` for details)

`api → agents → domain → adapters`. Domain depends on nothing infrastructural. Agents compose domain logic with an `LLMProvider` Protocol. Adapters implement protocols. API depends on agents and domain and (only via DI) on adapters.

## Test placement

- Unit tests: `tests/unit/<mirror of src path>/`
- Integration tests (real Neo4j, real Postgres, mocked LLMs): `tests/integration/`
- Agent tests with mocked `LLMProvider`: `tests/unit/agents/`
- E2E: `tests/e2e/`

**Test the agent's contract, not a model's accuracy.** For agents wrapping a
statistical model (the spaCy PreNER baseline; any future finetuned NER), assert the
*behaviour we own* — labels mapped to the §3.2 taxonomy, offsets preserved, the right
spans surfaced/dropped — not whether the model labels each token correctly. The baseline
is recall-first and *expected* to mislabel (e.g. `en_core_web_lg` tags "Old Bronek" as
ORG); corrections feed the data flywheel (see `docs/PLAN_LONG.md`). Factor the pure logic
(label-mapping, filtering, offset wiring) out of the model call so it stays unit-tested in
CI without loading a heavy model — the model wheels live in the optional `models`
dependency group and the model-loading tests `skipif`-skip when absent.

**Secret-keyword values in tests:** when a test needs a credential-like value (a
password, API key, token — e.g. asserting on a parsed DB URL), bind it to a local
variable rather than writing the literal next to the keyword (`password="…"`,
`api_key="…"`). `detect-secrets` flags the literal form and blocks the commit. Binding
to a variable sidesteps it cleanly — prefer that over editing `.secrets.baseline` or
adding an inline `# pragma: allowlist secret`. **The variable name itself must not
contain the secret keyword:** `fake_key = "k"` then `api_key=fake_key` passes;
`api_key = "k"` still trips, because the literal sits next to the keyword. (The
plugin matches `<keyword> = <literal>`, not just the kwarg call site.)

**Alembic revision ids trip the hex-entropy plugin.** A generated `revision: str =
"<hex>"` in a migration file is flagged as a high-entropy string. It is not a secret —
add `# pragma: allowlist secret  (alembic revision id, not a secret)` on that line.
(The `down_revision` hash usually has lower entropy and slips through; the head
`revision` is the one that trips.)

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

## Adding a setting that tests or the app read from `.env`

Recurring recipe (e.g. `TEST_DATABASE_URL` here; Neo4j creds and LLM API keys
later). The agent never edits `.env`, so every new setting follows three steps:

1. Add a **non-functional placeholder** to the matching `.env.example` (repo-root
   or `backend/`), plus the field on `Settings` in `config.py`.
2. Hand the user a **ready-to-run command** to append the real value to their
   `.env` — derive it from an existing line where possible (e.g. copy
   `DATABASE_URL` and swap the db name), so they don't hand-edit secrets.
3. Flag that the **dependent tests/app stay red until the user sets it** — don't
   race ahead to run the dependent step before they confirm it's in place.

## Running locally

```bash
cd backend
uv sync
# PreNER (spaCy) needs the pretrained model wheels, which are ~950 MB and live in
# the optional `models` dependency group — NOT installed by default (keeps CI lean;
# the model-loading tests auto-skip without them). Install them for any real run:
uv sync --group models
# First run only — migrate the dev DB. Tests use a throwaway DB (Session 1's
# conftest fixture), so this gap is invisible until a real request hits an
# unmigrated `storyforge` DB and 500s with `relation "..." does not exist`.
# Idempotent; safe to re-run.
uv run alembic upgrade head
uv run uvicorn story_forge.main:app --reload --port 8000
```

Infra (Neo4j, Postgres, Ollama) comes from the root `docker compose up`.
