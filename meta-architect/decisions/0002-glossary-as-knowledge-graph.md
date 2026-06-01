---
type: adr
slug: 0002-glossary-as-knowledge-graph
updated: 2026-06-01
status: accepted
related:
  - "[[0001-nine-layer-model]]"
---

# ADR 0002 — Glossary as a knowledge graph: one note per term

> A meta-architect design decision. Lean MADR form: two options, no security/data boundary
> crossed — so the escalation triggers in `templates/adr.md` do not fire, and the record
> stays lean. (This is the escalation rule dogfooding itself in the *quiet* direction.)

## Context and problem statement

The glossary is meant to outlive the project — a personal reference work the operator can
wander and learn from. "Wander" implies an Obsidian graph of concepts. The obvious
implementation — one `glossary.md` with each term as a `###` heading, cross-linked via
`[[glossary#term]]` — does NOT produce that graph: Obsidian collapses every in-file heading
link to a single node (the `glossary` file). The result reads as linked but renders as one
dot. The graph is only as expressive as its nodes are granular.

## Considered options

- **A — Single `glossary.md`, terms as headings**, cross-linked with `[[glossary#term]]`.
- **B — One note per term** in `glossary/<term>.md`, cross-linked with `[[term]]`; a
  generated `glossary.md` serves as the index. *(chosen)*

## Decision

Adopt **Option B**. Each concept is its own note (`type: glossary-term`) and therefore its
own graph node; `related` draws true concept-to-concept edges. A generated `glossary.md`
(`type: glossary`) indexes them. Links are declared once, in one direction — Obsidian's
backlinks panel supplies the reverse view for free.

## Consequences

- **Good:** A real, navigable knowledge graph — concept nodes, working backlinks, wander-able
  in Obsidian. Delivers the "reference work I'd value independently of the project" goal.
  Term notes are also linkable from anywhere (`[[trust-boundary]]` resolves to a real node).
- **Cost we accept:** Many small files instead of one; the agent maintains per-term notes and
  prunes stale `related` edges (which `review-architecture` can flag as ghost references).
- **Follow-ups:** The progressive-disclosure heuristic now counts term notes in `glossary/`
  (not headings in one file). Add `glossary-term` to the canonical `type` enum (done in
  `templates/vault-note.md`). The `initialize` skill scaffolds a `glossary/` directory plus a
  generated `glossary.md` index.
