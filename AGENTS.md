# AGENTS.md — Story Forge

This file governs how AI coding agents operate in this repository. Read it fully at the start of every session.

## What this project is

Story Forge is a local web application that helps a solo author analyze, annotate, and edit long-form narrative text, building a Neo4j knowledge graph of entities and relations. Single user, runs locally. The repository is public from day one and doubles as a portfolio piece: a working demonstration of clean modular architecture, agent-based LLM orchestration, multi-model routing, and secure-by-default infra.

**Source of truth:** `story-forge-poc-spec.md` at the project root. Always read it before working on a feature. If the spec disagrees with reality, the spec wins unless we explicitly amend it.

## Workflow rules (non-negotiable)

### 0. Concurrent agents share this working tree

Two AI agents may work in this repository: **Claude Code** (running directly in WSL) and
**Codex Desktop** (on the Windows/UNC view of the *same* WSL checkout). They share **one
working tree**, so each must assume the other may have left uncommitted changes:

- **Stage explicit paths for your commit — never `git add -A` / `git add .`.** Add only the
  files your change owns, so you cannot sweep the other agent's in-flight work into your PR.
- **If `git status` shows changes you did not make, surface them — do not absorb or delete
  them.** Keep them out of your commit; land them on their own branch/PR or hand them back to
  the user. (Session 9: Codex's `AGENTS.md` / `.codex/` edits appeared mid-session and were
  landed separately as PR #32, keeping the architecture-vault PR surgical.)
- **Codex runtime boundary:** when operating from Codex Desktop, read `.codex/RUNTIME_NOTES.md`
  before using local shell results as evidence (PowerShell/UNC host, no WSL shell access, the
  filemode/symlink-artifact caveat). Claude Code in WSL keeps its normal Linux shell workflow.

### 1. Karpathy rules — apply on every change

- **Don't assume. Don't hide confusion. Surface tradeoffs.** State assumptions explicitly. If uncertain, ask. If multiple interpretations exist, present them — don't pick silently.
- **Simplicity first.** Minimum code that solves the problem. No speculative features, no abstractions for single-use code, no configurability that wasn't asked for. If you wrote 200 lines and it could be 50, rewrite.
- **Surgical changes.** Touch only what you must. Don't "improve" adjacent code. Don't refactor things that aren't broken. Every changed line must trace to my request.
- **Goal-driven execution.** Transform tasks into verifiable goals. Write the test first. Loop until the test passes. "Make it work" is not a success criterion.

### 2. Spec- and test-driven, in this order

Per feature, every time:

1. Read the relevant spec section. If absent or wrong, propose an amendment and wait for approval before changing it.
2. Write the failing test that encodes the spec.
3. Implement minimally until the test passes.
4. Refactor for clarity; remove anything not earning its place.

No production code is written before tests for it exist.

### 3. Two-horizon planning — read and update every session

- **`docs/PLAN_LONG.md`** — strategic, V1/V2/V3 milestones, stable.
- **`docs/PLAN_SHORT.md`** — tactical, current milestone broken into one-conversation sessions. Read at session start. Update at session end. Check off completed tasks. Add new ones. Strike through (don't delete) obsolete ones.

The current milestone is sliced into numbered **sessions**, each sized for a single conversation. The top of `docs/PLAN_SHORT.md` carries a **Session handoff** block that always points at where the next session starts. Two skills maintain this loop — use them actively, but they assist the workflow, they don't replace judgement:

- **`/resume-session`** — run at the **start** of every working conversation. Reads the handoff block, verifies the on-disk anchors, surveys git, opens the named spec sections, and reports drift before any code is written. If the user hasn't run it, offer to.
- **`/wrap-session`** — run **near the end** of every working conversation. Reports the green-state checks, updates the task lists, refreshes Decided/Blocked, appends a dated Done line, rewrites the handoff block for the next session, and reminds about commit hygiene. When you sense a session is wrapping up, suggest it — don't let work end with the plan stale.

When implementation forces a spec change: **stop**. Propose the change. Once approved, update both plan files before resuming. Plans, spec, and code must not drift apart.

### 4. Directory-level AGENTS.md

Every major directory has its own `AGENTS.md` with conventions specific to that area. Read the directory's `AGENTS.md` before working in it. Examples:
- `backend/AGENTS.md` — Python conventions, FastAPI patterns
- `backend/src/story_forge/AGENTS.md` — domain vs adapter separation rules, agent patterns
- `frontend/AGENTS.md` — React/TypeScript conventions
- `frontend/src/AGENTS.md` — component and state-management patterns

If a directory's `AGENTS.md` contradicts this root file, the more specific (directory-level) file wins for that area — but flag the contradiction so we can fix it.

Each `CLAUDE.md` is a **symlink to its sibling `AGENTS.md`** — one source of truth, read by both Claude Code (`CLAUDE.md`) and Codex/other agents (`AGENTS.md`). Develop on Linux, WSL, or macOS, which honour symlinks; a Windows-native checkout needs `git config core.symlinks true`. Reading the repo through Windows/UNC from WSL can report spurious symlink/filemode diffs — those are host artifacts, not repo changes.

## Security baseline (always)

These are enforced by CI and pre-commit hooks, but you must respect them when writing code:

When *I* propose relaxing one of these §6.7 rules, neither refuse reflexively nor silently comply: run the stop-and-amend-spec-first flow — flag that it touches a stated non-negotiable, surface the tradeoff with a written rationale a stranger would accept, get the explicit decision, amend `story-forge-poc-spec.md` first, then reconcile `AGENTS.md` / skills / plan.

- Every dependency (`pyproject.toml` / `package.json`) pinned to an exact version, **minimum 14 days old at time of pin**. No exceptions without explicit conversation. Docker image tags in `docker-compose.yml` follow a parallel rule with a **shorter 7-day soak** — pinned exact tag, ≥7 days old, CVE-scanned (Trivy), because official base images are signed/vendored and freshness reduces CVE exposure (rationale in spec §6.7). Use the `/pin-image` skill for image pins; `/add-dependency` for packages.
- No secrets in code. Only `.env.example`. `.env` is gitignored.
- **The agent never reads, creates, or edits `.env` / `backend/.env`.** Secret material is user-managed; the agent only ever touches `.env.example` templates and hands the user commands to run themselves. (Enforced deterministically by `deny` rules in `.claude/settings.json`, not just convention.)
- `.env.example` placeholders must be **non-functional** (e.g. `USE_ROOT_POSTGRES_PASSWORD`, `replace-me-with-openssl-rand-hex-24`) — never real or working default credentials, even for `127.0.0.1`-bound local services.
- Docker services bind to `127.0.0.1` only. Non-root containers. Private bridge network.
- No telemetry libraries (no Sentry, PostHog, Mixpanel, analytics SDKs of any kind).
- API keys never logged. Auth headers stripped from logs.
- CORS strict — only the four loopback origins for the dev frontends in dev: `http://localhost:5173`, `http://127.0.0.1:5173`, `http://localhost:3000`, `http://127.0.0.1:3000`. Both name forms because Vite binds to `127.0.0.1` by default and the browser's `Origin` header reflects the URL bar, not DNS resolution. No wildcards. (Spec §6.7.)
- See §6.7 of the spec for the full list. Reread before touching infrastructure files.

## Public-portfolio hygiene

This repo is public. Treat every commit as something a stranger might read:

- No `TODO: explain later`. Either explain now or leave it out.
- Work on feature branches; **squash-merge** to `main` with a curated commit message per feature. Dirty WIP commits never reach `main`'s history. The linear `main` log should read like an intentional record of how the project was built.
- Throwaway experiments live as untracked scratch files (covered by `.gitignore`), not as branches that may accidentally get pushed.
- README, ADRs, AGENTS.md files, and inline comments are written for an outsider.
- Generated artifacts (screenshots of the agent activity panel, sample graphs) belong in `docs/`, not as random files at the root.

### Merge flow

Per feature (and at session close): feature branch → **open a PR so CI actually runs** (the only place the service-container / image-scan jobs execute) → await checks **and** code review → **fold review notes into the branch before merging** (don't merge known-flagged code; document + track anything deliberately deferred) → **squash-merge** to `main` with a curated message. The session-close bookkeeping is its own `docs: close Session N` PR (see `/wrap-session`); the feature is merged before that wrap runs.

- **Review model (changed 2026-06-08).** Your own **`/review-pr` is the primary review gate** — run it on your own work before every merge. The external Codex review is now **secondary / best-effort** (the ChatGPT subscription was cancelled; Codex may not run at all), so **don't block a merge waiting on it**; fold its notes only if it actually appears. Because there is no longer a guaranteed second reviewer, raise your own bar: for *substantive code* changes where a missed bug is costly, run the heavier multi-agent **`/code-review`** in addition to `/review-pr` — the PR-#36 lesson is that a second reviewer once caught two real bugs the single self-review pass missed, and that safety net is now thinner. (If Codex/automated PR review does keep working, treat it as a bonus, not a dependency.) **Solo-review blind spot:** self-review structurally can't catch what you didn't think to check, so for PRs that **flip decision-state across many homes** (a proposal→accepted, a spec amendment, an ADR), don't trust recall — run the `/review-pr` §2 reconciliation sweep as an *explicit pass* (grep the proposal slug + status words across `INDEX.md` + both plan files; diff each decision against the task that implements it) **before** claiming clean. PR #39 is the cautionary case: the self-review asserted §2 clean and still left three stale homes for external review to find.

- **Green-main bar.** Don't merge on red CI. The one exception: a failure that is *pre-existing, unrelated to the PR, and diagnosed* — merge is allowed if that's stated explicitly and tracked.
- **Split unrelated bugs out.** A pre-existing infra/bug discovery that isn't this PR's concern gets its own GitHub issue, not scope-creep. Small *incidental* fixes the PR already touches can ride along, disclosed in the commit body.

## How to communicate with me

- One clear question at a time, with the options you're weighing.
- After finishing a unit of work: short summary (what was done, what tests pass, what's next, what's blocked).
- When the spec is wrong or contradictory: flag it before working around it.
- Long stretches without check-in are a smell. If you've been working for 30+ minutes without confirming direction, stop and confirm.

## Where knowledge lives — document in the repo, not in agent memory

Durable knowledge belongs in the **project files a human will actually read**, not in
private agent memory. Decisions, rationales, conventions, and follow-ups go into the
granular file that owns them — the spec (`story-forge-poc-spec.md`), the plans
(`docs/PLAN_*.md`), the relevant `AGENTS.md`, or a skill — so the next contributor (and
the next session) finds them by reading the repo. This is a public portfolio: the record
of *how* and *why* we build must be in the open, version-controlled, and reviewable.

- Prefer the most specific home: a layering rule → that directory's `AGENTS.md`; a
  workflow rule → here or a skill; a decision → `docs/PLAN_SHORT.md` **Decided**; a roadmap
  shift → `docs/PLAN_LONG.md`; a spec change → the spec (via the stop-and-amend flow).
- **Reconcile a decision across *every* home in one pass — a fact lives in more places than you
  changed.** When you record or resolve a decision (amend the spec, land an ADR, flip a doc
  `proposed → accepted`, overturn a prior choice), the authoritative home is only the first edit.
  Then sweep the **whole repo** (not just the files you touched) for every other home of that fact:
  the spec's other sections, `README.md`, every `AGENTS.md`, both plan files, the `architecture/`
  vault — *and* the notes that merely *track* it (ADR registries, priority queues, as-built/status
  snapshots, doc pointers), which phrase it in different words a keyword grep won't catch. Bring any
  accepted artifact's **whole body** to resolved (not just a top banner), give a resolved dated
  report a banner + matching `status:`, and leave append-only history (superseded-ADR text,
  `CHANGELOG`) intact. **Verify by exhaustive grep proactively** — doing this at authoring time is
  what stops a reviewer (or six review passes — see PR #34) from finding the stale leftovers. The
  review-side mirror of this rule lives in `/review-pr` §2.
- Agent memory, if used at all, is a temporary scratchpad. **At `/wrap-session`, migrate
  anything durable out of memory into the proper project file, then clear it** — never let
  a decision live only in memory where a collaborator can't see it.
- **Web research runs in the main loop**, not a background subagent — subagents can't
  surface permission prompts, so `WebSearch`/`WebFetch`/`Bash` get auto-denied for them.

## Stack reminder (details in spec §6)

- Backend: FastAPI (Python 3.12), `uv` for env management
- Frontend: React + Vite + TypeScript, TanStack Query + Zustand, Tiptap editor
- Graph DB: Neo4j Community
- Relational DB: PostgreSQL with pgvector
- LLM tiers: local Ollama (Qwen3.5 9B Q4_K_M on 8GB VRAM), Ollama Cloud free tier (chunking: `gpt-oss:20b-cloud`; heavier passes: `gpt-oss:120b-cloud` or Qwen3.5 cloud variants), paid cloud via **OpenRouter** (preferred — one endpoint to many models; the only paid adapter built in M2.S2), with direct Grok / Anthropic / Google / OpenAI adapters as needed. Order + rationale: spec §6.5 / `docs/decisions/0003`
- Embeddings: sentence-transformers (local, multilingual PL/EN)
- NER baseline: spaCy `pl_core_news_lg` + `en_core_web_lg`
- Agents: chunking, extraction, matching, judging — modular modules in `backend/src/story_forge/agents/`, each with its own prompt template and Pydantic output schema

## Reference docs

- `story-forge-poc-spec.md` — full PoC specification, source of truth
- `docs/PLAN_LONG.md` — strategic milestones
- `docs/PLAN_SHORT.md` — tactical task list, current milestone
- `docs/AGENTS.md` — plan conventions (handoff-block contract, Decided/Blocked/Done structure, cross-cutting curation rule)
- `docs/decisions/` — Architecture Decision Records (ADRs)
- `architecture/` — the **meta-architect vault**: the architectural *projection* layer (named invariants, state machines, decision register, per-feature decompositions, dated review sweeps, teaching glossary). **Orienting context, not a source of truth** — it references the spec/plans/code and never overrides them; on disagreement the source wins and the vault is what drifted. Navigate from `architecture/INDEX.md`; conventions + the source-of-truth boundary are in `architecture/AGENTS.md`. The `meta-architect:*` skills (deferred from the rituals per `docs/decisions/0002`) are its only writers; everyone else reads it for orientation. Consult it when planning a milestone, decomposing a branchy feature, or checking which invariant guards a change.

---

**You are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, clarifying questions before implementation rather than after mistakes, plans and spec consistent at session end.
