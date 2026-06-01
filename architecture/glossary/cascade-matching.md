---
type: glossary-term
slug: cascade-matching
updated: 2026-06-02
status: living
related: ["[[model-tier-routing]]", "[[human-in-the-loop]]", "[[open-world-ontology]]"]
---

# cascade matching (kaskadowe dopasowanie)

**Definition:** Story Forge's multi-stage decision for "is this extracted candidate a *new*
entity or one that already exists?" — cheap deterministic checks first, expensive ones only when
needed, a human always last.

**Answers:** "is this the same entity we already know, and how little can we spend to be sure?"

**First encountered in:** [[overview]]

Four stages (§3.3), escalating only on ambiguity: **Stage 1** fuzzy string match (RapidFuzz,
free) → **Stage 2** embedding similarity (local model) → **Stage 3** LLM-as-judge (the *only*
token spend, only on hard cases) → **Stage 4** human review (always, for anything uncertain).
This is the product's core mechanism and its loudest [[fail-closed]] + [[human-in-the-loop]]
surface. Lands in M3; until then [[invariants]] INV-8 holds (no dedupe at all).
