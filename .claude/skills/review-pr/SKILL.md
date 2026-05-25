---
name: review-pr
description: Story Forge PR review — a thorough correctness/bug-finding pass PLUS the project-specific lens (spec & plan fidelity, layering, §6.7 security gaps, test discipline, portfolio hygiene, merge-readiness). Loads the diff + the spec/plan/CLAUDE.md context a generic reviewer lacks, then reports findings grouped by severity. Report-only — it recommends, it never merges. Run on the current branch's PR (or local branch diff) as your own-review, complementing Codex.
---

# Review a Story Forge PR

This is the **"your own review"** step the merge flow requires (root `CLAUDE.md` →
*Merge flow*): feature branch → PR → CI + Codex → **fold review notes** → squash-merge.
Codex is complementary but partial — it spots *some* of what matters and misses much. This
skill is the deeper pass, with two things a generic reviewer doesn't have: (1) a deliberate
correctness/bug hunt, and (2) the Story Forge lens — our spec, our layering, our security
baseline, our test and hygiene rules.

**Two standing rules for this skill:**

- **Report-only. It recommends; it never merges, pushes, or edits the code under review.**
  Findings go to the user, grouped by severity; the user decides what to fold in.
- **Be concrete or say nothing.** Every finding cites `file:line` and the specific rule or
  bug it touches. "Looks fine" is not a finding; "could be cleaner" without a reason is
  noise. A clean section is a *valid, valuable* result — say so explicitly.

Work through the steps in order. Don't eyeball where a `grep`/command can be exact.

## 0. Load context (the part generic reviewers skip)

- **The diff.** If a PR exists for the branch: `gh pr diff <N>` (and `gh pr view <N>` for
  the description + CI state). No PR yet: `git diff main...HEAD` and `git log main..HEAD`.
  Identify every file touched and *why the PR says* it's touched.
- **The spec.** Open the `story-forge-poc-spec.md` section(s) the PR implements or amends
  (the PR body / commit usually names them). The spec is the source of truth.
- **The plan.** Read the current-session tasks and the **Decided** / **Blocked** entries in
  `PLAN_SHORT.md` — the PR must honor decisions already made (or justify changing them).
- **The conventions.** Read the directory-level `CLAUDE.md` for every area the diff touches
  (`backend/`, `backend/src/story_forge/`, `frontend/`, …) plus the root `CLAUDE.md`.

State the change in one sentence before reviewing it. If you can't, that's finding #1.

## 1. Correctness & bug-finding pass (the deliberate hunt)

Read the changed code as an adversary looking for what breaks. Don't just confirm the happy
path the tests assert — find the cases nobody wrote a test for. Check, concretely:

- **Logic & control flow** — off-by-one, inverted conditions, wrong boundary (`<` vs `<=`),
  early return skipping cleanup, unreachable branches, loop that retries with identical
  inputs (does the retry actually *do* anything different?).
- **Dispatch-level confusion in nested structures** — when code branches on a property at
  one level of a tree (e.g. `if chapter.title is None`), check that the invariant being
  preserved isn't at the *neighboring* level. The hybrid-chunking bug (PR #13) dispatched
  on chapter-untitled and re-LLM'd the whole span, silently discarding an explicitly-titled
  scene the author put *before* the first chapter heading (an explicit child of an implicit
  parent). Walk one level past the branch you wrote.
- **Edge / empty / malformed inputs** — empty string/list, `None`/`null`, zero, missing
  dict keys, unexpected types, oversize input, non-UTF-8 bytes, duplicate or out-of-range
  values (e.g. a `paragraph_range` that overlaps, reverses, or skips paragraphs).
- **Error handling** — exceptions caught too broadly or too narrowly; the wrong exception
  type expected (does `model_validate_json` raise what the `except` actually catches?);
  errors swallowed; a failure path that leaves state half-written (e.g. file on disk but DB
  rolled back — recall the orphaned-sandbox cross-cutting note).
- **Async / resource** — un-awaited coroutine, blocking call in async code, client/connection
  not closed, shared mutable state across requests, ordering assumptions between awaits.
- **Data integrity** — IDs generated/used consistently across the Postgres/Neo4j split;
  `order_index` renumbering; transactions committed/rolled back on the right paths.
- **External I/O contracts** — request/response shape vs the real API (Ollama `/api/chat`,
  psycopg, httpx); headers, timeouts, status handling; what happens on a 4xx/5xx/timeout.
- **Output-schema strength** — does the Pydantic/validation schema for LLM (or any external)
  output actually *enforce its invariants*, or does a **parseable-but-malformed** response
  (negative/reversed range, out-of-domain enum, empty required list) validate as **success**
  and silently skip the retry path? Constrain what the type can express, don't just name it.

For each suspected bug: state the input that triggers it and the wrong outcome. If you're
unsure it's real, say so and how to confirm — don't drop it, don't overstate it.

## 2. Spec & plan fidelity

- Does the change do what the **spec** section says — no more, no less? Flag silent
  divergence from the spec that did **not** go through the stop-and-amend flow.
- If the PR **amends** the spec: is the amendment actually present, justified, and are
  `PLAN_SHORT.md` / `PLAN_LONG.md` reconciled with it? Plans, spec, code must not drift.
- Does it honor the session's **Decided** entries (e.g. a chosen library, threshold, tier
  default)? A contradiction of a recorded decision is blocking unless the PR re-decides it.

## 3. Karpathy discipline (root `CLAUDE.md` §1)

- **Simplicity** — minimum code for the problem. Flag speculative features, abstractions for
  single-use code, configurability nobody asked for, dead config (a `Settings` field/knob
  with no reader). **Count both sides** when weighing a small abstraction: noise it *adds*
  (a new class/file) vs noise it *removes* (type-ignores, repeated boilerplate, branches).
  An abstraction that net-removes existing debt is a refactor, not speculation — simplicity
  argues *for* it, not against. (Story Forge example: a `Protocol` that replaces a concrete
  class type and drops a dozen `# type: ignore[arg-type]` markers in tests.)
- **Surgical** — no "improvements" to adjacent untouched code, no opportunistic refactors.
  Every changed line should trace to the PR's stated purpose; flag drive-by edits.

## 4. Layering & architecture (`backend/src/story_forge/CLAUDE.md`)

Mostly grep-able — verify, don't assume:

- `domain/` imports nothing from `api/`, `agents/`, or `adapters/` (pure, no I/O).
- `agents/` import the **`LLMProvider` Protocol**, never a concrete adapter (`OllamaProvider`,
  `httpx`, `neo4j`, `psycopg`).
- `api/` routes are thin — no business logic, no direct DB/graph access; go through domain.
- **FastAPI routes declare every non-2xx outcome they raise.** Every `HTTPException` a route
  raises (or maps from a domain exception) must have a matching entry on the decorator's
  `responses={status: {"model": ErrorResponse, "description": "..."}}` — otherwise the
  OpenAPI schema shows only the success status + the auto-added 422 validation error, and
  the generated TypeScript client (`frontend/src/lib/api/schema.d.ts`) can't model the
  failure paths it must handle. Walk every `raise HTTPException(...)` and every
  `except ...: raise HTTPException(...)` in the route body and verify the status code
  appears in `responses=`. The hand-rolled 422 case (where a domain error is mapped to 422
  with a `{detail: str}` body) is the one trap: declaring it would clobber FastAPI's
  validation typing — either remap to a different status, or leave 422 alone and document
  the overload as a cross-cutting follow-up.
- **Prompts live in `prompts/` as `.j2`**, never inline f-strings in agent code.
- **LLM output is always Pydantic-validated and retried** — no raw JSON trusted, and the
  schema is *strict* (step 1: malformed-but-parseable must fail, not pass).
- **Prompt construction is injection-safe** — untrusted text (an uploaded story, user input)
  rendered into a prompt must not be able to alter the prompt's *structure*: forge role
  markers / extra turns, escape its delimiter, or inject control tokens. Never recover
  structure (roles, sections) by reparsing output that was rendered **together with**
  untrusted content — derive structure from the trusted template, then render content into
  it. Treat "we interpolate user/document text into a prompt" as a finding to chase, not a
  feature to wave through.

## 5. Security baseline §6.7 — the gaps CI can't catch

CI already gates dep-age/exact-pins, Trivy image scans, detect-secrets, npm audit. **Don't
re-litigate those** — spot the things those tools miss:

- An API key / `Authorization` / `X-API-Key` value that reaches a log line.
- A **functional** value in `.env.example` (must be a non-working placeholder).
- Any handling of `.env` / `backend/.env` by the agent (forbidden — must be user-managed).
- A new service/bind that isn't `127.0.0.1`-only, a root container, a wildcard CORS origin,
  a telemetry/analytics import.
- A **prompt-injection vector** — untrusted document/user text reaching the model in a way
  that can change the prompt's control structure (the structural check is step 4; flag any
  new prompt path that interpolates untrusted content so it gets that scrutiny).
- A new package/image pin that *slipped past* CI framing (e.g. added but not actually
  scanned, or an image tag change without the `/pin-image` waiver bookkeeping).

## 6. Test discipline (root `CLAUDE.md` §2, `backend/CLAUDE.md`)

- Is there a **test for every new behavior**, and does it encode the spec (not just assert
  the happy path)? Were tests plausibly written first?
- **Agent tests use a mocked `LLMProvider`** — no real LLM/network in unit tests.
- Integration tests carry the `integration` marker; unit tests need no Postgres/network.
- Tests live in the mirrored path (`tests/unit/<src path>/`, `tests/integration/`,
  `tests/unit/agents/`). Credential-like literals bound to a variable (detect-secrets).
- Do the assertions actually exercise the risk found in step 1, or only the obvious case?
- **Render-test wrappers must be load-bearing.** Every provider / context / router /
  fixture wrapping a render test must be exercised by the asserted-on subtree, or by an
  explicit sentinel component that throws when the wrapper is absent (e.g. a tiny child
  calling `useQueryClient()` to fail loudly if no `QueryClientProvider` is in scope). A
  decorative wrapper makes the test pass whether or not the production composition is
  wired right — the test docstring then *overclaims* what it defends. Rule of thumb: if
  you can delete the wrapper from the test and the test still passes, the wrapper is a lie.
- **A new test runner / category / glob is wired into CI before merge.** If this PR adds
  a test framework (vitest, Playwright, a new pytest marker, a new file glob), check that
  `.github/workflows/ci.yml` actually invokes it (`grep` the job for the runner name /
  npm script / pytest invocation). A test that runs only locally is half a test — it
  defends today's commit but not tomorrow's. Skipping this check structurally bypasses
  the test-driven rule for the session's headline artifact.

## 7. Portfolio hygiene (root `CLAUDE.md` → Public-portfolio hygiene)

The repo is public; every line is read by a stranger.

- Comments / docstrings / names written for an outsider; no `TODO: explain later`.
- No leftover scratch, commented-out code, or debug prints.
- Curated commit message + PR body that read as an intentional record.
- Generated artifacts (screenshots, sample graphs) under `docs/`, not the repo root.

## 8. Merge-readiness

- CI: all jobs green? If red, is it *pre-existing, unrelated, and diagnosed* (the only
  allowed exception per the green-main bar), and is that stated + tracked?
- Are deferred items tracked (a GitHub issue or a `PLAN_SHORT.md` cross-cutting note), not
  silently dropped? Unrelated discoveries split out rather than scope-crept in?
- Have prior review notes (Codex / earlier passes) been folded or explicitly deferred?

## 9. Report

Give the user one structured close-out:

- **One-line summary** of the change and an overall read (ready / needs work / blocked).
- **Findings grouped by severity**, each with `file:line` and the rule/bug:
  - **Blocking** — a bug, a spec/decision contradiction, a §6.7 violation, missing tests for
    new behavior, or red CI without a sanctioned reason. Must fix before merge.
  - **Should-fix** — real problems that aren't merge-blockers (weak test coverage, an awkward
    but correct construction, a missing tracked-deferral note).
  - **Nit** — style/readability/polish; optional.
- **Checked and clean** — name the dimensions you verified and found fine, so a green review
  means something rather than "I didn't look."

Then stop. The user folds what they choose into the branch (this skill doesn't edit code or
merge). If they want findings as inline PR comments, point them at the `code-review` skill's
`--comment` mode rather than posting from here.
