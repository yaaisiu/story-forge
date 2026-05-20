# CLAUDE.md — Story Forge

This file governs how Claude Code operates in this repository. Read it fully at the start of every session.

## What this project is

Story Forge is a local web application that helps a solo author analyze, annotate, and edit long-form narrative text, building a Neo4j knowledge graph of entities and relations. Single user, runs locally. The repository is public from day one and doubles as a portfolio piece: a working demonstration of clean modular architecture, agent-based LLM orchestration, multi-model routing, and secure-by-default infra.

**Source of truth:** `story-forge-poc-spec.md` at the project root. Always read it before working on a feature. If the spec disagrees with reality, the spec wins unless we explicitly amend it.

## Workflow rules (non-negotiable)

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

- **`PLAN_LONG.md`** — strategic, V1/V2/V3 milestones, stable.
- **`PLAN_SHORT.md`** — tactical, current milestone broken into tasks. Read at session start. Update at session end. Check off completed tasks. Add new ones. Strike through (don't delete) obsolete ones.

When implementation forces a spec change: **stop**. Propose the change. Once approved, update both plan files before resuming. Plans, spec, and code must not drift apart.

### 4. Directory-level CLAUDE.md

Every major directory has its own `CLAUDE.md` with conventions specific to that area. Read the directory's `CLAUDE.md` before working in it. Examples:
- `backend/CLAUDE.md` — Python conventions, FastAPI patterns
- `backend/src/story_forge/CLAUDE.md` — domain vs adapter separation rules, agent patterns
- `frontend/CLAUDE.md` — React/TypeScript conventions
- `frontend/src/CLAUDE.md` — component and state-management patterns

If a directory's `CLAUDE.md` contradicts this root file, the more specific (directory-level) file wins for that area — but flag the contradiction so we can fix it.

## Security baseline (always)

These are enforced by CI and pre-commit hooks, but you must respect them when writing code:

- Every dependency pinned to an exact version, **minimum 14 days old at time of pin**. No exceptions without explicit conversation. Same rule applies to Docker image tags in `docker-compose.yml` — pinned, ≥14 days old, CVE-scanned (Trivy).
- No secrets in code. Only `.env.example`. `.env` is gitignored.
- Docker services bind to `127.0.0.1` only. Non-root containers. Private bridge network.
- No telemetry libraries (no Sentry, PostHog, Mixpanel, analytics SDKs of any kind).
- API keys never logged. Auth headers stripped from logs.
- CORS strict — only `http://localhost:5173` and `http://localhost:3000` in dev.
- See §6.7 of the spec for the full list. Reread before touching infrastructure files.

## Public-portfolio hygiene

This repo is public. Treat every commit as something a stranger might read:

- No `TODO: explain later`. Either explain now or leave it out.
- Work on feature branches; **squash-merge** to `main` with a curated commit message per feature. Dirty WIP commits never reach `main`'s history. The linear `main` log should read like an intentional record of how the project was built.
- Throwaway experiments live as untracked scratch files (covered by `.gitignore`), not as branches that may accidentally get pushed.
- README, ADRs, CLAUDE.md files, and inline comments are written for an outsider.
- Generated artifacts (screenshots of the agent activity panel, sample graphs) belong in `docs/`, not as random files at the root.

## How to communicate with me

- One clear question at a time, with the options you're weighing.
- After finishing a unit of work: short summary (what was done, what tests pass, what's next, what's blocked).
- When the spec is wrong or contradictory: flag it before working around it.
- Long stretches without check-in are a smell. If you've been working for 30+ minutes without confirming direction, stop and confirm.

## Stack reminder (details in spec §6)

- Backend: FastAPI (Python 3.12), `uv` for env management
- Frontend: React + Vite + TypeScript, TanStack Query + Zustand, Tiptap editor
- Graph DB: Neo4j Community
- Relational DB: PostgreSQL with pgvector
- LLM tiers: local Ollama (Qwen3.5 9B Q4_K_M on 8GB VRAM), Ollama Cloud free tier (`gpt-oss:120b-cloud`), paid cloud (Anthropic / OpenAI / Grok), OpenRouter as meta-provider
- Embeddings: sentence-transformers (local, multilingual PL/EN)
- NER baseline: spaCy `pl_core_news_lg` + `en_core_web_lg`
- Agents: chunking, extraction, matching, judging — modular modules in `backend/src/story_forge/agents/`, each with its own prompt template and Pydantic output schema

## Reference docs

- `story-forge-poc-spec.md` — full PoC specification, source of truth
- `PLAN_LONG.md` — strategic milestones
- `PLAN_SHORT.md` — tactical task list, current milestone
- `docs/decisions/` — Architecture Decision Records (ADRs)

---

**You are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, clarifying questions before implementation rather than after mistakes, plans and spec consistent at session end.
