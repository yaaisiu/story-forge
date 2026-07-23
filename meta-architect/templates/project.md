<!--
  PROJECT TEMPLATE.
  Lives in the vault at: architecture/PROJECT.md  — a LIVING SNAPSHOT of the project's stable
  inputs: identity, the system-altitude layers, where truth lives, and operator calibration.
  "Snapshot" does NOT mean immutable. The project WILL grow, and this note is updated IN PLACE
  as it does: explicitly (re-running `initialize` never auto-overwrites it), with `updated`
  bumped and the change logged to CHANGELOG.md. What is protected is blind clobbering, not
  evolution. The living ANALYSIS that grows from these inputs lives in SEPARATE notes (the
  seed system overview, components, proposals) — mixing stable inputs with evolving analysis
  makes both harder to trust.
-->
---
type: project
slug: project
updated: 2026-06-01
status: living
related: []
---

# <Project name>

## Identity

<One paragraph: what this project is, in plain language. From the interview, not invented.>

## Classification

<web app | CLI | library | service | data pipeline | infrastructure | plugin | other — and
one line on why.>

## Personas & trust (Layer 1)

<Who uses this, and at what trust level. e.g. "solo author (full trust, local); no external
or anonymous actors." Trust level is the seed of every later Security and Access question.>

## Business (Layer 2)

<Why this exists — the driver behind it (a need, a risk, a deal, a portfolio goal). The
system-altitude "why" that every feature's "why" must ladder up to.>

## Source-of-truth registry

<The single most valuable table in the vault: for each meaningful kind of fact, WHERE its
authoritative version lives. When the project already has docs, the vault REFERENCES them
here rather than copying — copying creates a second source of truth, which is the bug.>

| Fact / domain | Authoritative source |
|---------------|----------------------|
| <e.g. product requirements> | <e.g. `story-forge-poc-spec.md`> |
| <e.g. roadmap / milestones> | <e.g. `docs/PLAN_LONG.md`> |
| <e.g. runtime behaviour>    | <the code itself> |

## Existing documentation referenced

<Links/paths to docs that already exist and that this vault defers to (does not duplicate).
The vault's job is to ADD the architectural layer, not restate what's already written.>

## Calibration

- **Architecture-vocabulary familiarity (operator, self-described):** <novice | building |
  comfortable | advanced> — seeds the initial progressive-disclosure tier (see the agent's
  heuristic). After this, the glossary's growth drives density automatically.
- **Primary reader:** <who actually reads these notes — the operator, an outside visitor reading
  cold, the agents that orient from the vault, or some mix. Ask; don't assume the operator reads
  them. This drives how much a note explains and whether it is paced as a curriculum.>
- **Language:** <the working language for prose. If the project wants a second-language gloss on
  glossary terms, name it here; otherwise the glossary is single-language. Do NOT default to one —
  a bilingual glossary is a per-project choice, not a convention.>
