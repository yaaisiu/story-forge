# Code guide — where to start reading

A newcomer's map of the Story Forge codebase. This is **navigation only**: it tells you what to
read and in what order, then hands you off to the authoritative docs. It deliberately does **not**
restate them — the per-directory `AGENTS.md` files and the spec own the details and stay current;
this page just points.

> **Want a description of what's where, layer by layer?** The [`code/`](code/) reference notes
> (one per layer — domain, agents, adapters, api, the two frontend areas) *describe* each module's
> responsibility and its key pieces. This page tells you where to start; those tell you what each
> part is.

> **The two sources of truth.** *What* the app does → [`story-forge-poc-spec.md`](../story-forge-poc-spec.md).
> *How the code is organised* → the `AGENTS.md` file in each directory (conventions, layering,
> pitfalls). When this guide and one of those disagree, **they win** — tell us, this page drifted.

## Read in this order

1. **The spec — skim two sections.** [`§3 Functional requirements`](../story-forge-poc-spec.md)
   (the *what*: ingest → graph → viewer) and [`§6 Technical architecture`](../story-forge-poc-spec.md)
   (the *how*: stack, data model, agent orchestration). [`§7`](../story-forge-poc-spec.md) is the
   ingest pipeline step by step.
2. **The README [Architecture](../README.md) section** — the one-screen orientation: the agent
   inventory, multi-model routing, the layered backend, the security baseline.
3. **The backend, by layer.** Start at
   [`backend/src/story_forge/AGENTS.md`](../backend/src/story_forge/AGENTS.md) — it states the
   strict layering (`api → agents → domain → adapters`) and the agent pattern. Then read the code
   dependencies-first (bottom-up): `domain/` (the shapes) → `agents/` (the pipeline) → `api/` (the
   HTTP surface) → `adapters/` (the I/O bridges to Postgres, Neo4j, the LLM providers). Module
   docstrings carry the per-file rationale and spec cross-references.
4. **The frontend.** [`frontend/src/AGENTS.md`](../frontend/src/AGENTS.md) for the
   feature-folder structure and component rules;
   [`frontend/src/lib/api/AGENTS.md`](../frontend/src/lib/api/AGENTS.md) for the
   OpenAPI-generated client and how HTTP status is mapped.
5. **Design rationale.** [`docs/decisions/`](decisions/) (ADRs — why the major choices were made)
   and the [`architecture/`](../architecture/INDEX.md) vault (named invariants, state machines,
   per-feature decompositions; orienting context, not a source of truth — see its
   [`AGENTS.md`](../architecture/AGENTS.md)).

## One request, traced

A chapter is ingested and becomes graph (authoritative step-by-step: spec
[`§7`](../story-forge-poc-spec.md)):

**upload** (`api/stories.py` `upload_story`) **→ chunk** into chapters/scenes (`agents/chunking_*`)
**→ extract** entity & relation candidates per chunk (`agents/extraction_*`) **→ embed & match**:
each candidate is embedded and matched against existing entities via the cascade, with a judge
weighing in (`agents/embedding_agent.py`, `agents/candidate_staging.py`, `agents/matching_agent.py`,
`agents/judge_agent.py`) **→ human review**: the human accepts or rejects each candidate
(`agents/candidate_review.py`) **→ graph**: accepted entities/relations are written to Neo4j
(`adapters/neo4j_repo.py`) and surfaced in the viewer. Every LLM call is routed across the model
tiers by `adapters/llm/router.py` (spec [`§6.5`](../story-forge-poc-spec.md), ADR
[`0003`](decisions/0003-llm-router-provider-order-and-budget.md)). This is the coarse shape; spec
[`§7`](../story-forge-poc-spec.md) is the authoritative step-by-step.

## Directory map

```
backend/src/story_forge/
  domain/      domain models — the entity/relation/graph/document shapes (spec §6.4)
  agents/      the pipeline — chunking, extraction, matching, judging, embedding, review
  api/         FastAPI routes — the HTTP surface
  adapters/    I/O bridges — Postgres, Neo4j, and the LLM providers (adapters/llm/)
  prompts/     Jinja2 prompt templates, one per agent

frontend/src/
  features/    one folder per screen — upload, chunking, extraction-review,
               relation-review, graph-viewer, agent-activity, text-reader, projects
  lib/api/     OpenAPI-generated client + query hooks
  app/         app shell and routing
```

Each directory's own `AGENTS.md` (where present) is the current, authoritative word on its
conventions — read it before changing code there.
