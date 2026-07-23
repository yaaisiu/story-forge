# AGENTS.md — backend/

This directory holds the Python FastAPI backend.

## Conventions

- Python 3.12 (pinned via `.python-version`, capped `<3.13` in `pyproject.toml`)
- Environment managed by `uv` (`uv sync`, `uv run`)
- Dependency pins in `pyproject.toml` — exact versions, minimum 14 days old
- Format: `ruff format`. Lint: `ruff check`. Type: `mypy --strict` on `src/`
- Tests: `pytest`. Async tests with `pytest-asyncio`. Coverage tracked but not gated initially
- Logging: **none implemented yet** — the backend emits no operational logs (`structlog` is not a dependency; nothing calls `logging`). Planned shape when it lands: structured logs (e.g. structlog), JSON in prod / pretty in dev, and — per §6.7 — **never** log auth headers, API keys, or PII. Until then §6.7 "keys never logged" holds *vacuously*; the manual key-leak smoke (see "Manual real-provider smoke" below) is the regression guard for when logging arrives. Tracked in `docs/PLAN_LONG.md` → "Operational logging & observability — later". (Don't conflate this with training-data capture, which is the `llm_calls` ledger + planned `edit_history`, not stdout logs.)

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

**High-entropy hex literals trip the hex-entropy plugin.** Any long hex string in code —
not just secrets — is flagged. It is not a secret; add `# pragma: allowlist secret` on
that line. Two cases have bitten so far:
- **Alembic revision ids.** A generated `revision: str = "<hex>"` in a migration file is
  flagged. **Add the pragma to *both* the `revision` and the `down_revision` lines
  proactively:** whether a given hash trips depends on its entropy, not its role, so don't
  assume the `down_revision` "slips through" — in Session 15 the `down_revision` hash
  tripped while the `revision` (already pragma'd) did not. Pragma both and you never
  iterate against the hook.
- **Pinned model / commit SHAs.** A pinned artifact revision — e.g. the §6.7 HuggingFace
  model `MODEL_REVISION = "<40-char-sha>"` in `agents/embedding_agent.py` (Session 21) — is
  a content address, not a credential, but trips the same plugin. Pragma the line.

(This very note tripped the hook by quoting a real hash — so it doesn't anymore; that's
the foot-gun in miniature.)

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

**A test-first integration test for a new module must still *import* cleanly.**
pytest collects (imports) every test file *before* it deselects by marker, so a
new `tests/integration/test_*.py` whose top-level `import story_forge.adapters.X`
points at a not-yet-created module raises a collection error that breaks even
`pytest -m "not integration"` — the fast/commit tier, not just the integration run.
So when you write the failing test first (TDD), create the module + its symbols
(even as a stub) in the same step, so the red is an *assertion/connection* failure,
not a collection crash that takes the unit tier down with it. (Session 15, the
neo4j adapter.)

Prerequisites for the integration tier:
- Postgres up (`docker compose up -d` from the repo root).
- `backend/.env` defines `TEST_DATABASE_URL` — a **distinct** DB name
  (`story_forge_test`) on the same server as `DATABASE_URL`. `.env` is
  user-managed (never edited by the agent); the template lives in `.env.example`.

Alembic's `env.py` only injects `settings.database_url` when no URL was supplied,
so the fixture can point migrations at the test DB by setting `sqlalchemy.url` in
a `Config` it builds itself.

**Troubleshooting — `collation version mismatch` on the integration tier.** If the
session fixture's `CREATE DATABASE story_forge_test` (or any query) fails with
`template database "template1" has a collation version mismatch` (… created using
collation version 2.36, but the operating system provides 2.41), the host's glibc
was upgraded under the running Postgres data volume — common on a WSL/distro update.
It is a local-environment papercut, **not** a repo bug. Refresh the dev container's
collation once (idempotent), then re-run:
```bash
for db in template1 postgres storyforge; do
  docker compose exec -T postgres psql -U storyforge -d "$db" \
    -c "ALTER DATABASE $db REFRESH COLLATION VERSION;"
done
```
(Session 17: this blocked the integration tier locally until refreshed; CI is
unaffected — its Postgres service container is freshly built each run.)

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
# the model-loading tests auto-skip without them). The embedding cascade — Stage-2
# matching, S4 duplicate-suggestions, and S6 label-vocabulary — needs a SEPARATE
# `embeddings` group (`sentence-transformers` + ~2 GB torch), also not installed by
# default. Install both for any real run that extracts, matches, or curates the graph:
uv sync --group models --group embeddings
# (A run that only touches an embedding-free path can use just `--group models`; but the
# label-vocabulary / duplicate-suggestion endpoints 500 with `No module named
# 'sentence_transformers'` if `embeddings` is missing — Session 96 lost a smoke to this.)
# First run only — migrate the dev DB. Tests use a throwaway DB (Session 1's
# conftest fixture), so this gap is invisible until a real request hits an
# unmigrated `storyforge` DB and 500s with `relation "..." does not exist`.
# Idempotent; safe to re-run.
uv run alembic upgrade head
uv run uvicorn story_forge.main:app --reload --port 8000
```

Infra (Neo4j, Postgres, Ollama) comes from the root `docker compose up`.

## Live/manual testing against the dev stores — name disposably, clean up by id

A manual or live verification (running the app, hitting `/upload` + `/structure` + `/extract`,
a smoke script) writes **real data to the dev Postgres / Neo4j / upload sandbox** — the same
stores that hold the owner's actual work. Two rules so a throwaway test can never endanger it:

- **Name it disposably.** Give test uploads/projects a clearly throwaway name (a `DELETEME`
  marker or a date), so it can't be confused with real data at a glance.
- **Clean up by the exact id, after inspecting — never by name.** Look at what's there first
  (`SELECT id, name, created_at …`), confirm the id you created, and delete *that id* (FKs cascade
  project → story → chapters → scenes → paragraphs). **Never delete by name** — names collide.
  (Earned Session 71, 2026-06-29: an S1 live smoke named its story `oakhaven`, identical to the
  owner's real graph; there were three `oakhaven` projects and a delete-by-name would have wiped two
  real ones — deleting the exact test id `2d184fed…` was the safe path. The `llm_calls` cost ledger
  has no story/project column, so a test call's row isn't attributable — leave it rather than risk a
  real row.)
- **An ad-hoc script that connects with `settings.database_url` must not let a traceback reach the
  transcript — the URL embeds the password and psycopg prints the whole conninfo on error.** This is
  not a logging leak (the backend emits no logs, see *Conventions*); it is the *exception* path, and
  it fires on the most ordinary mistakes — a typo'd column name, a wrong table. `psycopg.ProgrammingError`
  renders as `missing "=" after "postgresql+psycopg://storyforge:<the real password>@…"`, so one
  throwaway query against a misremembered schema puts the credential in front of whoever is watching.
  Redirect stderr (`2>/dev/null`) or wrap the connect+execute in `try/except` that prints only
  `type(exc).__name__`, and check the column names against the migration first rather than guessing.
  Two practical notes for such scripts: strip the SQLAlchemy driver prefix (`str(settings.database_url).replace("+psycopg", "")`)
  because raw `psycopg.AsyncConnection.connect` rejects it, and prefer asserting a *property* of a
  secret (length, shape, "does the repo contain it") over printing the value. (Earned Session 100:
  a `label_a`-vs-`label_lo` column guess leaked the dev DB password into the session transcript;
  `.env` was correctly untracked and gitignored, so nothing was committed and no rotation was needed.)

## Manual real-provider smoke (M2 close) + §6.7 key-leak check

The unit tests mock every provider. This is the **manual** smoke that exercises *real*
egress and confirms §6.7 ("API keys never logged; auth headers stripped from logs")
under a real call — the part CI can't do (no keys in CI). Run it locally where keys are
configured; it is deliberately not automated. `.env` is user-managed — the agent never
reads it; the commands below read keys the same way the app does.

**What actually runs — a doublet, not a "triplet".** With no direct vendor adapters
shipped (OpenRouter is the only paid route — ADR 0003), and OpenRouter **not wired into
the app** (`main.py` configures only the `cloud_free` tier; an unconfigured tier raises
rather than misroutes — a YAGNI kept until a heavy task needs `cloud_strong`), the real
surface is:

- **Ollama Cloud (`cloud_free`)** — wired into the app; exercised by a real extract.
- **OpenRouter free model (`cloud_strong`)** — exercised standalone via
  `scripts/check_openrouter.py` (the app can't route to it yet).

**1 — Connectivity (one real call each, cheap):**

```bash
python3 scripts/check_ollama_cloud.py                              # reads OLLAMA_CLOUD_API_KEY
OPENROUTER_MODEL=<your-free-model-id> python3 scripts/check_openrouter.py   # reads OPENROUTER_API_KEY
```

Each prints `OK` on a 200 + parseable body, `FAIL: …` otherwise, and skips cleanly
(exit 0) if its key is unset.

**2 — Real end-to-end extract (Ollama Cloud), capturing all process output:**

```bash
docker compose up -d                                              # neo4j + postgres
cd backend && uv sync --group models --group embeddings && uv run alembic upgrade head
uv run uvicorn story_forge.main:app --port 8000 2>&1 | tee /tmp/sf-smoke.log
# In another shell: upload a short text → POST /stories/{id}/structure →
# POST /stories/{id}/extract → GET /stories/{id}/graph; confirm entities appear and
# the §8.5 panel shows which tier/model ran.
```

Also force an **error path** — the real leak risk is an exception/traceback, not a log
line: point `EXTRACTION_MODEL` at a bogus model so the provider 4xx/5xx's, and confirm
the failure surfaces (502) without the key.

**3 — The key-leak assertion (the actual §6.7 check) over the captured output:**

```bash
set -a; source backend/.env; set +a   # your action — load keys for the grep
grep -F "$OPENROUTER_API_KEY"  /tmp/sf-smoke.log && echo "LEAK!" || echo "clean (no OpenRouter key)"
grep -F "$OLLAMA_CLOUD_API_KEY" /tmp/sf-smoke.log && echo "LEAK!" || echo "clean (no Ollama key)"
grep -nE "Bearer |Authorization:"   /tmp/sf-smoke.log || echo "clean (no auth-header strings)"
```

Expected: all "clean". **Today this passes vacuously** — the backend emits no operational
logs (see the `## Conventions` logging note + `docs/PLAN_LONG.md` "Operational logging &
observability"), so the only way a key could surface is an exception that formats the
header, which the adapters don't do. When operational logging lands, re-run this as the
redaction **regression guard**.
