---
type: project
slug: project
updated: 2026-06-02
status: living
related: ["[[overview]]", "[[invariants]]", "[[open-questions]]"]
---

# Story Forge

## Identity

Story Forge is a **local, single-user web application** that helps a solo author analyze,
annotate, and edit long-form narrative text while building an evolving **knowledge graph**
(a database that stores things and the named relationships between them) of the story's
entities and relations in Neo4j. **As specified for V1** (the target capability — for what is
built today vs. planned, see [[overview]] "as-built"), the author uploads a raw draft; the
system splits it into chapters → scenes → paragraphs, extracts entities (characters, places,
objects, concepts) and their relations, and lets the author confirm every graph decision by
hand. *Today the upload/split/structure step works; LLM extraction and the graph write are
M2.S3–S4.* It runs entirely on the author's machine and is **public from day one** — it
doubles as a portfolio
piece demonstrating clean modular architecture, agent-based LLM orchestration, multi-model
routing, and secure-by-default infrastructure.

The authoritative description is the spec (`story-forge-poc-spec.md`); this note records only
the *stable architectural inputs* the vault reasons from. It does not restate the spec.

## Classification

**Web app** — specifically, *a local single-user web app whose dominant subsystem is an
agent-based ingest/enrichment pipeline*. Justification, grounded in the repo scan: a FastAPI
API layer (`backend/src/story_forge/api/`) and a React + Vite SPA (`frontend/src/`) served to
a browser on localhost, backed by Postgres + pgvector, Neo4j, and Ollama in docker-compose.
The architectural centre of gravity, though, is the §7 **ingest pipeline** (chunking → PreNER
→ extraction → cascade matching → graph write) — that is where the hardest "but what if"
questions concentrate, so much of the vault's later analysis will live at that altitude.

## Personas & trust (Layer 1)

There is exactly **one persona: the solo author**, operating at **full trust** on their own
local machine. A *persona* is a category of user defined by what they are trusted to do; a
*trust boundary* (**granica zaufania** — the line at which data crosses between contexts of
different trust levels) normally separates personas of different privilege. Story Forge has
**no human trust boundary**: no multi-user, no anonymous access, no remote callers (§2.3).

This is the single most consequential architectural input, because it *removes* an entire
class of concerns (authn/authz between users, tenant isolation, per-user rate limits) — and
relocates the real trust boundary elsewhere. The boundary that *does* exist is **machine ↔
external LLM provider**: the moment the author's text is sent to a cloud model, it crosses
out of the fully-trusted local context. That crossing — not a login screen — is where the
Security and Compliance/Audit layers do their work (see [[invariants]] #2, [[trust-boundary]]).

## Business (Layer 2)

Two drivers, equal weight (confirmed in interview — "both readers, equally"):

1. **A genuine personal tool.** The author writes in a coherent universe ("Wody Święte" /
   Holy Waters) and needs to turn a chaotic raw draft into a living, queryable world model —
   entities, relations, and eventually editorial + style-rewriting support, with the graph as
   the coherence anchor (§2.1).
2. **A public portfolio piece.** The repo is built in the open to *demonstrate* — not merely
   make — clean three-layer architecture, agent-based LLM orchestration, multi-tier model
   routing, and secure-by-default infra. "Architecture choices are demonstrated, not just
   made" (§2.2). This is why the spec, ADRs, plans, and `AGENTS.md` conventions are all
   visible, and why this very vault is committed.

Every feature's "why" must ladder up to one of these two. A feature that serves neither the
author's workflow nor the portfolio demonstration is out of scope (§2.3 — "not a content
generator, not multi-user, not productionable as-is").

## Source-of-truth registry

The single most valuable table in the vault: for each kind of fact, **where its one
authoritative copy lives**. The vault *references* these; it never copies them, because a copy
is a second source of truth — and two sources that can disagree is the bug this registry
exists to prevent (see [[source-of-truth]]).

| Fact / domain | Authoritative source |
|---------------|----------------------|
| Product requirements (what we build) | `story-forge-poc-spec.md` — **the** authority; the spec wins over reality unless explicitly amended |
| Strategic roadmap (V1/V2/V3 milestones) | `docs/PLAN_LONG.md` |
| Tactical plan (current milestone, session slices, handoff block) | `docs/PLAN_SHORT.md` |
| Architecture decisions (host project) | `docs/decisions/` (ADRs 0001 three-tier LLM, 0002 incubate meta-architect) |
| Per-directory conventions (Python, FastAPI, domain/adapter split, React, API client) | the seven `AGENTS.md` files (each `CLAUDE.md` is a symlink to its `AGENTS.md`) |
| Workflow rules (Karpathy rules, spec-then-test, merge flow, security baseline) | root `AGENTS.md` / `CLAUDE.md` |
| Runtime behaviour (what the code actually does today) | the code itself, `backend/src/story_forge/` and `frontend/src/` |
| Data model — relational (Postgres tables) | spec §6.4 + Alembic migrations (`backend/alembic/`) |
| Data model — graph (Neo4j constraints/indexes) | spec §6.4 + `infra/neo4j/init.cypher` (Alembic owns Postgres only) |
| Security baseline (the non-negotiables) | spec §6.7 |
| **Architectural projection layer** (invariants, state machines, consequence analysis, decision register) | **this vault** — the one thing the repo did not previously hold |

## Existing documentation referenced (deferred to, not duplicated)

- `story-forge-poc-spec.md` — full PoC spec (1098 lines): functional reqs (§3), tech
  architecture (§6), ingest pipeline (§7), UI (§8), roadmap (§9), open questions (§10),
  non-functional principles (§11), glossary (App. A), the "Wody Święte" test fixture (App. B),
  prompt skeletons (App. C).
- `docs/PLAN_LONG.md`, `docs/PLAN_SHORT.md`, `docs/AGENTS.md` (plan conventions).
- `docs/decisions/0001-three-tier-llm-strategy.md`, `0002-incubate-meta-architect-in-repo.md`.
- `README.md`, `SECURITY.md`, and the seven `AGENTS.md` convention files.

## Calibration

- **Architecture-vocabulary familiarity (operator, self-described):** **novice** — define every
  architectural term inline, EN + PL, and narrate the layer/station reasoning. This sets the
  initial progressive-disclosure tier to **Scaffolded (verbose)**. As the glossary fills, the
  density tightens automatically (the agent counts glossary terms and learning-log lines to
  choose tier; novice never bumps the tier *down*).
- **Primary reader:** **both, equally** — a working design tool for the author *and* a
  portfolio artefact an outsider reads cold. Every note is written so a stranger can open it
  without prior context.
- **Language:** English prose (matching the spec and `AGENTS.md` files); the glossary always
  carries the Polish term alongside the English, per the project's bilingual PL/EN nature.
