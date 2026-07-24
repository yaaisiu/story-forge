---
type: project
slug: project
updated: 2026-07-24
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
hand. *V1 is **feature-complete** (M0–M4): upload → structure → LLM extraction → the §3.3 human-gated
cascade → graph write → an inline-highlight reader with an editable entity side panel (edit, merge,
delete, undo, manual tagging) → narrowed multi-story (a new story reuses the project graph). The
multi-story live smoke passed (Session 54). **Public-readiness** (portfolio/spec/doc polish) closed at
the Session-68 roll, and the **Graph-quality** milestone — curating the over-extracted graph in place
rather than re-running extraction — is **complete as of Session 100** (S0–S7: chunker data-loss fix,
graph navigation, edge evidence, duplicate-entity suggestion, canvas editing, name normalisation, the
reader correction loop). The next milestone is the **Grzymalin reality check** (opened Session 102, 2026-07-24):
run the pipeline **unaided** on a *real*, English, non-fiction research corpus (about the village of
Grzymalin near Legnica; half-synthetic Gemini Deep Research), replacing the synthetic/over-extracted
Oakhaven sample as the working material. It **realises the prerequisite** the fork was gated on — the fork
between deeper extraction work (spec §5) and **V2 Editing** (§4) stays deliberately **open**, to be locked in
the milestone's last session on the run's evidence, because the working graph has been hand-curated and no
longer shows what the pipeline produces.* It runs
entirely on the author's machine and is **public from day one** — it doubles as a portfolio
piece demonstrating clean modular architecture, agent-based LLM orchestration, multi-model
routing, and secure-by-default infrastructure.

The authoritative description is the spec (`story-forge-poc-spec.md`); this note records only
the *stable architectural inputs* the vault reasons from. It does not restate the spec.

## Classification

**Web app** — specifically, *a local single-user web app whose dominant subsystem is an
agent-based ingest/enrichment pipeline*. Justification, grounded in the repo scan: a FastAPI
API layer (`backend/src/story_forge/api/`) and a React + Vite SPA (`frontend/src/`) served to
a browser on localhost, backed by Postgres + pgvector, Neo4j, and Ollama in docker-compose.
The architectural centre of gravity, though, is the §7 **ingest pipeline** (chunking → extraction
→ cascade matching → human review → graph write) — that is where the hardest "but what if"
questions concentrate, so much of the vault's later analysis will live at that altitude. (A spaCy
**PreNER** baseline is *built but dormant* — §7 Step 3 deferred 2026-06-25; the live extraction is
LLM-only, so PreNER is not a stage in the pipeline as it runs today.)

## Personas & trust (Layer 1)

There is exactly **one persona: the solo author**, operating at **full trust** on their own
local machine. A *persona* is a category of user defined by what they are trusted to do; a
*trust boundary* (**granica zaufania** — the line at which data crosses between contexts of
different trust levels) normally separates personas of different privilege. Story Forge has
**no human trust boundary**: no multi-user, no anonymous access, no remote callers (§2.3).

**Re-confirmed by the owner 2026-07-23 (Session 101)** — still one person, their own machine, fully
trusted. **But with a stated expiry, new at that re-confirmation:** the owner would like the tool to
become *"usable one day — and not only for me"* (see Layer 2). That does **not** change anything today
and needs no spec amendment (§2.3's "not multi-user" is a *PoC* scope statement and still holds), but it
does change how the assumption should be *leaned on*: "single-user forever" is no longer a safe premise
to build **irreversibly** against. Concretely — a shortcut that is merely *unused* under one user is
fine; one that would be *wrong* under many, and expensive to undo, now deserves a note at the time it is
taken. The live example is the S7 label-embedding cache, keyed on the bare label and deliberately shared
across projects — harmless under one trusted user, a shared mutable structure sitting *below* the
tenancy key if this aspiration is ever realised ([[open-questions]] OQ-35 W-1).

This is the single most consequential architectural input, because it *removes* an entire
class of concerns (authn/authz between users, tenant isolation, per-user rate limits) — and
relocates the real trust boundary elsewhere. The boundary that *does* exist is **machine ↔
external LLM provider**: the moment the author's text is sent to a cloud model, it crosses
out of the fully-trusted local context. That crossing — not a login screen — is where the
Security and Compliance/Audit layers do their work (see [[invariants]] #2, [[trust-boundary]]).

## Business (Layer 2)

Two drivers — today weighted toward the portfolio / architecture-exploration side, with real use
aspirational. **Re-confirmed and sharpened by the owner 2026-07-23 (Session 101):** *"mainly a portfolio
and learning project, but one day I would like it to be usable — and not only for me."* Two things
follow. The **weighting is unchanged** (portfolio/learning primary), so this is not a scope change. But
the aspiration is now **broader than the original framing** — it was "a tool for *this* author"; it is
now "a tool other people could use", which reaches past §2.3's single-user PoC scope and gives the
Layer-1 persona assumption a stated expiry (see above). Nothing to build now; something to stop
foreclosing.

1. **An authoring tool — designed-for, currently aspirational.** Story Forge is *built for* a
   solo author working in a coherent fictional universe ("Wody Święte" / Holy Waters — the
   project's recurring **test fixture**, App. B): turning a chaotic raw draft into a living,
   queryable world model of entities and relations, with editorial + style-rewriting support
   later and the graph as the coherence anchor (§2.1). For the PoC there is **no real
   manuscript** — the sample content is LLM-generated — so today this driver is *aspirational*:
   genuine authoring or research use is a longer-term aim, while the immediate motivation is
   exploring the architecture and the spec-driven build process itself.
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
| Architecture decisions (host project) | `docs/decisions/` (ADRs 0001 three-tier LLM [superseded-in-part], 0002 incubate meta-architect, 0003 LLM router / provider order / budget) |
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
- `docs/decisions/0001-three-tier-llm-strategy.md`, `0002-incubate-meta-architect-in-repo.md`,
  `0003-llm-router-provider-order-and-budget.md`.
- `README.md`, `SECURITY.md`, and the seven `AGENTS.md` convention files.

## Calibration

**Recalibrated by the owner 2026-07-23 (Session 101), replacing the bootstrap-interview settings.**
The honest correction is the first line below, and it retires the teaching layer's original *audience*
— not the teaching itself.

- **Primary reader: NOT the operator.** The owner states plainly that he does not read these notes.
  That retires the bootstrap assumption that the vault is partly a tool for teaching *him* architecture
  vocabulary. The two readers that remain are both real: **an outside visitor reading cold** (this is a
  public portfolio repo) and **the agents that orient from the vault** before working. Write for those
  two. Practically this means the notes should stay self-contained and jargon-explaining — a stranger
  must be able to open any note without prior context — but they should stop being paced as a
  curriculum for one specific person.
- **Vocabulary level: still beginner-friendly, deliberately.** *"Informative, usable for the
  beginner"* (owner). So the progressive-disclosure tier does **not** tighten to terse expert prose
  just because the glossary is full: define a term on first appearance, keep the reasoning narrated
  enough to follow. The audience changed; the accessibility bar did not.
- **Language: English only.** *"For sure we don't need Polish there"* (owner). The bilingual EN + PL
  glossary convention existed to teach the operator in his first language, and that purpose is retired
  with the reader change above. **Going forward: no new Polish terms in vault notes.** The project
  remains bilingual in its *content* domain — the stories are Polish, and spec App. A keeps its own
  terminology — but that is a property of the text being analysed, not of the architecture notes
  describing the system. **The Polish glosses were stripped in Session 103 (2026-07-24):** all 36
  glossary term-notes are now English-only (the two non-Polish parentheticals — `agent (…)` and
  `backend-for-frontend (BFF)` — and the `(SCA)` acronym were preserved), the `glossary.md` index and
  two inline body glosses too. The strip scope had been mis-recorded as "22" from a diacritics-only
  grep; the true set was ~34 of the 36 (see [[open-questions]] OQ-36).
