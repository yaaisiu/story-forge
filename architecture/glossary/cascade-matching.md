---
type: glossary-term
slug: cascade-matching
updated: 2026-06-15
status: living
related: ["[[model-tier-routing]]", "[[human-in-the-loop]]", "[[open-world-ontology]]"]
---

# cascade matching

**Definition:** Story Forge's multi-stage decision for "is this extracted candidate a *new*
entity or one that already exists?" — cheap deterministic checks first, expensive ones only when
needed, a human always last.

**Answers:** "is this the same entity we already know, and how little can we spend to be sure?"

**First encountered in:** [[overview]]

The contract — the four stages, their methods, and the similarity thresholds — lives in spec
§3.3; the vault does not restate it. The *architectural force* worth naming: the stages are
ordered **cheapest-first** (free deterministic checks before any token spend) and **fail-closed**
— anything the automated stages can't resolve with confidence falls through to the human,
never auto-merges. That makes it the product's loudest [[fail-closed]] + [[human-in-the-loop]]
surface. Landed in M3.S4a (intercept-before-write, ADR 0004): the temporary [[invariants]] INV-8
(no dedupe) is retired — the cascade now *proposes* and the human commits (INV-1 / INV-9).
