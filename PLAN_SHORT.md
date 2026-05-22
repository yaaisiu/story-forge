# PLAN_SHORT.md — Current milestone tactical plan

> Updated every working session. Read at start (`/resume-session`); update at end (`/wrap-session`).

<!-- ───────────────────────────── HANDOFF ─────────────────────────────
This block is the contract between `/wrap-session` (writes it) and
`/resume-session` (reads it). It always describes where the NEXT session
should start. Keep it short and literal. Do not delete the markers.
────────────────────────────────────────────────────────────────────── -->

## ▶ Session handoff (read this first)

- **Next step:** **Session 3 — LLM Protocol + OllamaProvider + ChunkingAgent (auto mode).** First work step is a *failing* test (the agent against a **mocked** `LLMProvider` — no real LLM in tests). First in-session decision: the **auto-chunking trigger threshold** — the word count above which a text routes to Ollama Cloud (free) instead of local; needs a concrete number (see Blocked/questions). Build the `LLMProvider` Protocol (`adapters/llm/base.py`, spec §6.5), a minimal `OllamaProvider` (`adapters/llm/ollama.py` — local tier; host swap + optional key reaches cloud-free, only what's needed now), `prompts/chunking.{pl,en}.j2` (Appendix C.1 skeleton) + a Pydantic output schema, and `agents/chunking_agent.py` (load prompt → call provider → parse + validate → retry on bad JSON; auto-chunk via local, fall back to cloud-free for longer texts).
- **Read before starting (Session 3):** this file; spec **§6.5** (LLM provider abstraction + agent pattern), **Appendix C.1** (chunking prompt skeleton), **§3.1** (auto/manual/hybrid splitting workflow), **§7 step 2** (structure); `backend/src/story_forge/CLAUDE.md` ("LLM adapter", "Agents", "Prompts" sections — agents import the `LLMProvider` Protocol, never a concrete adapter; prompts live in `prompts/`, never f-strings) and `backend/CLAUDE.md` ("Running tests").
- **Verify on disk:** `main` at `c692cba` (Session 2, PR #8). Session 2 anchors present: `api/stories.py` upload route, `domain/parsing.py`, `domain/language.py`, `adapters/db.py`, `adapters/upload_storage.py`, `tests/unit/{domain,adapters}/`, `tests/integration/test_upload.py`. Session 1 anchors still present (migration, `postgres_repo.py`, `domain/models.py`, `conftest.py`). **No `adapters/llm/` yet, no `agents/` yet, no `prompts/` yet** (Session 3 creates them). `backend/.env` must define `TEST_DATABASE_URL` for the integration suite (Session 3's agent tests are unit/mocked, but the suite as a whole still uses it).
- **Last session ended:** 2026-05-21 — **Session 2 merged** (PR #8, squash `c692cba`): `POST /stories/upload` (validate → sandbox → parse → detect PL/EN → persist `Project`+`Story`), I/O-pure `domain/parsing.py`+`domain/language.py` (seeded `langdetect`), `adapters/{db,upload_storage}.py`. 38 tests pass, `main` green (all four CI jobs). Two Codex notes folded pre-merge (URL options preserved, Content-Type params stripped). Retro encoded PR-first/`wrap-session`-last into the wrap skill + a `backend/CLAUDE.md` test-secrets convention.
- **Open blocks/questions:** **Session 3 first decision — auto-chunking trigger threshold** (a word-count number for local→cloud-free routing; first work step is the failing test). Deferred (post-M1): orphaned-sandbox-file cleanup (see Cross-cutting). No infra blockers — `main` green.

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

### Session 2 — Upload + language detection + parsing `[x]`

_Decision in-session: language-detection library — chose `langdetect` (see Decided)._

- [x] `POST /stories/upload` accepting txt / md / docx; size + MIME validation; uploads sandboxed to a dedicated dir
- [x] Parsing helpers: docx / md / txt → raw text + paragraph blocks (`domain/`)
- [x] Language detection helper — PL / EN
- [x] Persist `Story` (+ `Project`) via the Session 1 repo, storing raw text and detected language
- [x] Tests: upload happy path, rejected validation (bad MIME / oversize), detection units, parser units

**Done when:** uploading a file creates a `Story` row with detected language and stored raw text.
**Resume anchor:** `api/stories.py` upload route live; parsing + detection helpers in `domain/`.

### Session 3 — LLM Protocol + OllamaProvider + ChunkingAgent (auto mode) `[ ]`

_Decision in-session: long-text → cloud-free threshold heuristic (see Blocked/questions)._

- [ ] `LLMProvider` Protocol (`adapters/llm/base.py`) per spec §6.5
- [ ] Minimal `OllamaProvider` — one adapter, host/key swap reaches both tiers; **default tier is cloud_free** on this GPU-less host (local_small is a config swap when a GPU is available — spec §6.5 amended 2026-05-22)
- [ ] `prompts/chunking.pl.j2` + `prompts/chunking.en.j2` (Appendix C.1 skeleton) + Pydantic output schema
- [ ] `agents/chunking_agent.py` — load prompt → call provider → parse + validate → retry on failure. **Reframed as the auto/fallback path** for *unmarked* text; deterministic manual/hybrid (Session 4) is the everyday primary path (§3.1). Config knob `CHUNKING_LOCAL_MAX_WORDS=4000` gates local-vs-cloud *if* a local tier is configured
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

**At the M1 → M2 roll, also reorganise the planning docs:** move `PLAN_SHORT.md` and
`PLAN_LONG.md` into a proper `docs/` directory, and add a `docs/CLAUDE.md` that documents
the **plan conventions** in one place instead of leaving them implicit — at minimum: the
handoff-block contract (the `▶ Session handoff` markers shared by `/resume-session` ↔
`/wrap-session`), the Decided / Blocked / Done structure, and the **cross-cutting curation
rule** (cross-cutting items are scoped to the current milestone and are carried forward by
hand during each milestone roll — nothing moves automatically, so the roll must consciously
review and re-home them). Reconcile any path references (root `CLAUDE.md`, the two session
skills, README) after the move. _(Added 2026-05-21 — capture before the current short plan ends.)_

---

### Cross-cutting (do as the relevant session touches it)

- [ ] Update spec §10 if any open question hardens (extraction granularity, etc.)
- [ ] **Embedding read path** — `adapters/postgres_repo.py` reads `NULL AS embedding` (paragraphs never store embeddings in M1). When the embedding pipeline lands, add the `pgvector` dep + `register_vector_async`, switch `get_paragraph`/`list_paragraphs` to `SELECT ... embedding`, and start writing the column. (Codex review note, 2026-05-20.)
- [ ] **Orphaned sandbox files on upload failure** — `api/stories.py` writes the original file to the sandbox *before* the `Project`/`Story` inserts; if the DB write fails the transaction rolls back but the file is left on disk, pointing at a story that never persisted. Harmless on a single-user local app, so deferred. Fix when it bites or when a delete-story feature lands (clean up the file on insert failure, or write-after-commit). (Own-review note, 2026-05-21.)

### Blocked / questions

- ~~**[Issue #2](https://github.com/yaaisiu/story-forge/issues/2) — invalid neo4j container image tag.**~~ ✅ Resolved 2026-05-21 (PR #3, squash `6694e23`): neo4j → `5.26.25-community-ubi10`, 3 bundled-netty CVEs waived. See Decided + Done.
- ~~**[Issue #4](https://github.com/yaaisiu/story-forge/issues/4) — pgvector (+ ollama) images CVE-stale.**~~ ✅ Resolved 2026-05-21 (PR #6, squash `4cb92a2`): pgvector → `0.8.2-pg17-trixie` (7-day bend), ollama → `0.24.0`, both scoped-waivered; `WAIVERS.md` register added. `main` fully green. See Decided + Done.
- ~~**Decide in Session 2 — language-detection library:** `langdetect` vs `fasttext`.~~ ✅ Resolved 2026-05-21: chose **`langdetect`** (no out-of-band model artifact, ample accuracy for PL/EN prose). See Decided + Done.
- ~~**Decide in Session 3 — auto-chunking trigger heuristic:** which threshold decides "long enough → use Ollama Cloud instead of local"?~~ ✅ Resolved 2026-05-22: config knob `CHUNKING_LOCAL_MAX_WORDS=4000` (conservative); but moot on this GPU-less host where cloud_free is the default tier anyway (see Decided). See Decided.

### Decided

- **2026-05-22 — Chunking refocus + cloud_free default (Session 3).** Two linked decisions. (1) **GPU-less dev host** → the local_small tier is impractical (CPU-only 9B too slow for interactive use), so chunking defaults to **cloud_free** (Ollama Cloud); local_small stays a config swap for a GPU-backed host. Because both tiers speak the Ollama API, this is a host/key flip in `OllamaProvider`, not a code-path change. Spec §6.5 (hardware para + agent table) and §7 step 2 amended with rationale. (2) **LLM chunking is not the primary path.** §3.1 already defines three modes; manual (`## Chapter`/`### Scene` markers) + hybrid are deterministic, free, and more reliable than a small model on *marked* text — and paragraphs are already deterministic (`domain/parsing.py`). So `ChunkingAgent` is reframed as the auto/**fallback** path for *unmarked* text + the canonical first agent demonstrating the agent pattern (prompt + Pydantic schema + retry); the deterministic manual/hybrid chunker (Session 4) is the everyday primary path. Session order unchanged (3 = LLM auto, 4 = manual/hybrid + persistence). The `CHUNKING_LOCAL_MAX_WORDS=4000` threshold is kept as a config knob (conservative; meaningful only when a local tier is configured), not a hardcoded magic number. **Tests stay mocked** — the smallest Ollama Cloud model is the runtime default and fine for manual smoke checks, but agent unit tests use a mocked `LLMProvider` per `backend/src/story_forge/CLAUDE.md`.
- **2026-05-21 — Language detection: `langdetect==1.0.9` (Session 2).** Over `fasttext`: `langdetect` is pure-Python and ships its own profiles (no `lid.176` model artifact to download out-of-band — pinnable, offline-friendly, no extra supply-chain surface), and PL/EN is an easy discrimination on 5k–50k-word prose where fasttext's short-text accuracy edge doesn't apply. Seeded (`DetectorFactory.seed = 0`) for deterministic output.
- **2026-05-21 — Upload creates a new `Project` per file (Session 2).** A `Story` needs a `project_id` and there is no project-selection UI/endpoint yet, so the upload route creates a `Project` (name = filename stem, language = detected) alongside the `Story`. The detected language lives on `Project` (the `Story` model has no language field). Revisit when project management lands.
- **2026-05-21 — Sandboxed uploads stored without a DB path column (Session 2).** Original bytes are written to a dedicated dir (UUID-named, `0o700` dir / `0o600` file, no exec — spec §6.7), and the parsed text is stored in `Story.raw_text`; the saved path is *not* tracked in Postgres. Satisfies §6.7 with no spec/migration change. The dir chmod is explicit (not `mkdir(mode=…)`, which is umask-masked and ignored for an existing dir).
- **2026-05-21 — Per-request DB connection, no pool (Session 2).** `adapters/db.py` `get_connection` opens one `AsyncConnection` per request (commit on success / rollback on error). A pool (`psycopg_pool`) is deferred as speculative for a single-user local app. `libpq_kwargs` preserves URL query options (`sslmode`, timeouts) so a managed-Postgres URL still works (Codex P1); `conftest` reuses the same helper.
- **2026-05-21 — Process (retro): PR-first / `/wrap-session`-last, encoded in the wrap skill.** The session-close order is commit → PR → CI + Codex review → fold fixes → squash-merge → *then* `/wrap-session` (which lands the separate `docs: close Session N` commit). Added a preflight step 0 to `wrap-session` and reframed its step 8 (commit the wrap's *own* bookkeeping, not the feature). Also added a `backend/CLAUDE.md` test convention: bind credential-like values to a variable so `detect-secrets` doesn't flag them (prefer over baseline/pragma edits).
- **2026-05-21 — Issue #4 resolved: pgvector → `0.8.2-pg17-trixie`, ollama → `0.24.0`, both scoped-waivered (PR #6, `4cb92a2`).** pgvector pinned at 6 days old (the pre-approved §6.7 bend); trixie is the cleanest base pgvector ships (9 OS CVEs vs bookworm 13; older 0.8.1-trixie = 42; no UBI variant). Fixing pgvector unmasked a second stale image — ollama `0.22.1` (sequential Trivy masking, same as neo4j→pgvector in #2). ollama bumped to `0.24.0` (freshest aged stable, 7 days, no bend), which dropped the CRITICAL + 6 others (17 → 12 HIGH, 0 CRIT). Residual CVEs no tag can fix are waived per-CVE: pgvector's OS CVEs (no fresher rebuild exists) + bundled `gosu`/Go-stdlib; ollama's compiled-in Go-stdlib + `buger/jsonparser` — all assessed not network-reachable on a 127.0.0.1 single-user deployment (gnutls unused; mostly DoS; cert-validation needs MITM). Added **`infra/trivy/WAIVERS.md`**, a consolidated review register of every waived CVE across images (fixed-in versions + drop conditions), backreferenced from each scoped `.trivyignore`; waivers stay per-image, never repo-wide.
- **2026-05-21 — Process (retro): amended `/pin-image` with three lessons from Issue #4.** (1) When a local Trivy scan can't be read back — large images auto-background into a sandbox whose stdout/file-writes never reach disk — stop iterating locally; scaffold a header-only waiver, push, and harvest the exact CVEs from the CI Trivy log (CI is the source of truth). (2) Scan *every* image the security job scans up front — a red image masks staleness in every later image (bit us twice: neo4j→pgvector, pgvector→ollama). (3) Record each waiver in `WAIVERS.md`, not just the scoped file.
- **2026-05-20 — §6.7 exception pre-approved for Issue #4: pin `pgvector:0.8.2` even if <7 days old.** Rationale (user): it's a CVE-*fix* release from a known official publisher; a serious flaw in a ~6-day-old release would most likely already be public, and a still-unknown one is subtle enough that the age-soak wouldn't catch it regardless — so waiting only prolongs exposure to the *known* CVEs the bump fixes. Trivy-cleanliness + the documented waiver remain the real gates. Record the exception in the PR / waiver file when applied. (This is the "no exceptions without explicit conversation" clause being exercised, not removed.)
- **2026-05-21 — Docker image age soak lowered 14 → 7 days (images only; packages stay 14).** Base images come from known signed official publishers and the dominant risk is *known CVEs*, where a fresher rebuild is safer — so Trivy CVE-cleanliness is the primary gate and a 7-day soak still allows a compromised-tag alert to surface. Spec §6.7 amended (with rationale), root `CLAUDE.md` updated, new `/pin-image` skill encodes it. `check_dependency_age.py` untouched (it only scans PyPI/npm, never images).
- **2026-05-21 — neo4j pinned to `5.26.25-community-ubi10` + scoped netty waiver (Issue #2).** UBI-10 base reports 0 OS CVEs vs 14 (incl. 2 CRITICAL gnutls) on Debian `-trixie`; the 3 HIGH netty CVEs Neo4j bundles itself (no base variant fixes them) are waived with per-CVE justification in `infra/trivy/neo4j.trivyignore`, wired to the neo4j Trivy step only. All DoS/parsing-desync, unreachable on a 127.0.0.1 single-user deployment. Drop the waiver when Neo4j bumps netty ≥ 4.1.133.
- **2026-05-21 — Process (retro): created `/pin-image` skill** for the image-pinning ritual (Docker Hub tag/date lookup → 7-day check → **dockerized Trivy** variant scan → base choice / scoped-waiver → apply to compose + ci.yml). Corrects the stale M0 "no trivy in WSL" assumption: `docker run aquasec/trivy image …` works locally and is the verify-before-push path. `add-dependency` gained a one-line "images → use /pin-image" pointer.
- **2026-05-20 — Primary keys are app-generated UUIDs (`uuid4`), not serial integers.** Paragraph/entity IDs are referenced cross-store (Neo4j `source_paragraph_id`, `entity_mentions.paragraph_id`), so store-independent stable IDs avoid sequence coordination between Postgres and Neo4j. DB carries `gen_random_uuid()` as a safety default; the repo inserts the model's id explicitly.
- **2026-05-20 — The document-tree migration is hand-written raw SQL (`op.execute`), not `op.create_table`.** A faithful 1:1 transcription of spec §6.4 — including `vector(768)` — without pulling a pgvector SQLAlchemy type into the dep set just to express one column. `target_metadata` stays `None`; no ORM layer (repo is raw async psycopg, columns map 1:1 to domain fields).
- **2026-05-20 — Repo scope is Create/Read/Delete for now; generic Update deferred.** The realistic update is renumbering `order_index` on reorder, which lands with chunking persistence (Session 4); not added speculatively.
- **2026-05-20 — Recipe for adding an `.env`-backed setting recorded in `backend/CLAUDE.md`** (retro outcome): placeholder in `.env.example` → hand the user an append command → dependent tests stay red until set. Captures the friction this session so Neo4j creds / LLM keys don't re-derive it.
- **2026-05-20 — Integration tests use a dedicated `story_forge_test` DB, fixture-managed in the same Postgres instance.** A pytest session fixture creates it, runs `alembic upgrade head`, yields, then drops it. Chosen over an ephemeral compose service / testcontainers: no new dependency, dev data untouched, deterministic. CI gets a pgvector service container.
- **2026-05-20 — Sibling ordering column is `order_index` (plain integer ordinal).** Avoids `order` (SQL reserved word → forced quoting); same name used end-to-end (DB / Pydantic / JSON), no mapping layer. Integer ordinal renumbered on reorder; fractional/lexical rank deferred as speculative. Spec §6.4 amended (inline note), SQL updated.
- **2026-05-20 — M1 sliced into 6 resumable sessions** (this file's structure). Each session is one-conversation-sized, ends green + committed, and records a resume anchor in the handoff block. Driven by `/wrap-session` (end) and `/resume-session` (start).
- **2026-05-20 — API client generator: `openapi-typescript`** (over `orval`/`hey-api`). Emits TS types + a tiny typed `openapi-fetch` client from the backend's `openapi.json`; we hand-write the TanStack Query hooks in `src/lib/api/`, keeping them plain/commented for an outsider. Chosen for the smallest dependency surface and most legible data layer in a portfolio repo.

### Done in previous sessions

- **2026-05-21 — Session 2 complete: story upload → validate → sandbox → parse → detect → persist (PR #8, squash `c692cba`).** `POST /stories/upload` (spec §7 step 1) accepts `.txt`/`.md`/`.docx`, validates (extension allowlist → 415, Content-Type with params stripped, 10 MiB cap → 413, empty/unparseable → 400), sandboxes the original (UUID-named, `0o700` dir / `0o600` file, no exec — §6.7, dir chmod explicit so it holds for a pre-existing dir), parses to raw text + paragraph blocks, detects PL/EN, and persists a `Project` (detected language) + `Story` (raw text). I/O-pure `domain/parsing.py` + `domain/language.py` (seeded `langdetect`); `adapters/{db,upload_storage}.py`; thin `api/stories.py` wired in `main.py`. New deps exact-pinned ≥14d, no advisories: `langdetect==1.0.9`, `python-docx==1.2.0`, `python-multipart==0.0.27`. **38 tests pass** (parser/detection/storage/db units + upload integration: happy txt→en & docx→pl, 415/413/400, sandbox write+perms, charset-param accept); ruff + mypy --strict + dep-age clean; `main` green (all four CI jobs). **Review:** two Codex notes folded in pre-merge — `libpq_kwargs` now preserves URL query options (sslmode/timeouts) and the route strips Content-Type parameters; own-review also de-duplicated `conftest`'s copy of `libpq_kwargs` and filed a cross-cutting note for orphaned-sandbox-file cleanup on upload failure (deferred, harmless single-user). **Process (retro):** encoded PR-first/`wrap-session`-last in the wrap skill (preflight step 0 + reframed step 8) and added a `backend/CLAUDE.md` test convention (bind secret-keyword values to a variable so detect-secrets doesn't flag them). **Lesson:** a happy-path test that hard-codes a clean `Content-Type` ("text/plain") hides the real-world parameterized form ("text/plain; charset=utf-8") — test the input the browser actually sends.
- **2026-05-21 — Issue #4 closed: both CVE-stale images fixed, `main` fully green (infra/governance, no M1 code).** pgvector `0.8.1-pg17-bookworm` → `0.8.2-pg17-trixie` (the pre-approved 7-day-rule bend for a CVE-fix release; trixie carries 9 OS CVEs vs bookworm's 13, and older is strictly worse — 0.8.1-trixie = 42). Fixing it unmasked a second stale image, ollama `0.22.1` (sequential-Trivy masking, the same pattern neo4j→pgvector showed in #2) → bumped to `0.24.0` (freshest aged stable, 7 days, no bend; dropped the CRITICAL + 6 others, 17 → 12 HIGH). Residual CVEs that no tag can fix are waived per-CVE in scoped `infra/trivy/{pgvector,ollama}.trivyignore` — pgvector's OS CVEs (no fresher rebuild) + bundled `gosu`/Go-stdlib, and ollama's compiled-in Go-stdlib + `buger/jsonparser` — each with a reachability assessment (none network-reachable on a 127.0.0.1 single-user non-root deployment: gnutls unused since Postgres TLS is OpenSSL, no DTLS, no systemd daemon; ollama CVEs are mostly DoS a trusted local caller self-inflicts, the two cert-validation ones need MITM of outbound TLS). Added `infra/trivy/WAIVERS.md`, a consolidated review register (every waived CVE across neo4j/pgvector/ollama with fixed-in versions + drop conditions) for periodic re-checking. Applied to `docker-compose.yml`, the CI backend `postgres` service container, the wrapper `infra/ollama/Dockerfile`, and both Trivy scan steps. pgvector waiver verified locally (dockerized Trivy → exit 0); ollama CVE list enumerated from the CI Trivy run. Squash-merged (PR #6, `4cb92a2`), Issue #4 closed. **Process (retro):** amended `/pin-image` — local-Trivy-unreadable → push-and-harvest-from-CI fallback; scan all images up front; record waivers in `WAIVERS.md`. **Lesson:** the sequential-Trivy unmask is now a confirmed *pattern*, not a one-off — fixing image N reveals staleness in image N+1, so sweep every image the security job scans before declaring it will go green. And in this environment local Trivy on large images is unusable (sandboxed background), so CI is the authoritative scanner.
- **2026-05-21 — Issue #2 fixed + image-pinning process hardened (infra/governance, no M1 code).** neo4j repointed from the nonexistent `5.26.25-community-bullseye` to `5.26.25-community-ubi10` in `docker-compose.yml` (neo4j + neo4j-init) and `ci.yml`; UBI-10 zeroes the 14 Debian OS CVEs, and the 3 bundled-netty HIGH CVEs are waived with per-CVE justification in `infra/trivy/neo4j.trivyignore` (scoped to the neo4j scan step). Verified with **dockerized Trivy** (exact CI flags → exit 0) and `docker compose config`; CI confirmed the neo4j scan step passes. Squash-merged (PR #3, `6694e23`), Issue #2 closed. The fix unmasked a separate pre-existing pgvector CVE-staleness problem → filed **[Issue #4](https://github.com/yaaisiu/story-forge/issues/4)** (security CI stays red on it until ~05-22 when the fix image ages in); merged with that red accepted as diagnosed/unrelated per the green-main norm. **Process (retro):** lowered the image age soak 14 → 7 days (images only) — spec §6.7 amended with rationale, root `CLAUDE.md` updated; created the `/pin-image` skill (corrects the stale "no trivy in WSL" assumption — dockerized Trivy is the local verify path) and added an `add-dependency` pointer. **Lesson:** an aged exact pin has *two* rot modes — a nonexistent tag (Session 1) **and** CVE-staleness as new advisories land against frozen packages (this session); and sequential Trivy steps mask downstream image failures, so scan *all* compose images locally up front.
- **2026-05-20 — Session 1 complete: persistence foundation.** Postgres document tree (Project → Story → Chapter → Scene → Paragraph, spec §6.4) shipped end to end: I/O-pure Pydantic domain models (`domain/models.py`, UUID PKs, `order_index`); a raw-SQL Alembic migration (cascade FKs, `vector(768)`, `CREATE EXTENSION vector`, child-lookup indexes, reversible downgrade); an async-psycopg repo (`adapters/postgres_repo.py`, C/R/D). Integration-test harness landed: `tests/conftest.py` owns a throwaway `story_forge_test` DB (create → `alembic upgrade head` → yield → drop) with a transactional `db_conn`, and an `integration` marker so unit tests need no Postgres. CI backend job gained a `pgvector/pgvector:0.8.1-pg17-bookworm` service container + `TEST_DATABASE_URL`. Docs: README "Running tests" + status → M1; `backend/CLAUDE.md` test-DB lifecycle. Backend gate green — 11 tests (1 unit + 10 integration), ruff + mypy clean. Incidental: fixed the Alembic ruff post-write hook (`console_scripts` → `exec`, it had never run) and refreshed `.secrets.baseline` for the CI throwaway password + Alembic URL placeholder. **Process (retro):** added the "Adding a setting that tests/app read from `.env`" recipe to `backend/CLAUDE.md`; rejected splitting incidental fixes into separate commits (squash-merge collapses them anyway; the commit body discloses them). **Merge + review:** addressed two Codex review notes before merge — a test-DB drop guard (refuse to `DROP` the app DB or any non-`*test*` name; unit-tested) and documenting/tracking the deferred embedding read path. Squash-merged to `main` (PR #1, `ff95dc2`); private repo created. **Lesson:** the first-ever CI run surfaced two latent M0 bugs (nonexistent `trivy-action@0.32.0` tag → fixed to `v0.36.0`; invalid `neo4j` image tag → [Issue #2](https://github.com/yaaisiu/story-forge/issues/2)). An exact pin that is ≥14 days old can still be a tag that does not exist — only a real pull/scan proves it. Standing up the remote + CI at M0 (not M1) would have caught these earlier.
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
