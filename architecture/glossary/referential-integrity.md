---
type: glossary-term
slug: referential-integrity
updated: 2026-06-16
status: living
related:
  - "[[idempotency]]"
  - "[[human-in-the-loop]]"
  - "[[open-world-ontology]]"
  - "[[candidate-lifecycle]]"
---

# referential integrity

**Definition:** the rule that a reference always points at something that exists — an edge may join
only two nodes that are both present, never a "half" edge into the void. A *dangling reference* is
one whose target is absent (not yet created, or already gone).

**Answers:** "the LLM proposed a relation `Janek —WIELDS→ the sword` as two surface strings — why
can't we just write that edge the moment we see it?"

**First encountered in:** [[m3-relation-write]]

Because an extracted relation names its endpoints as **surface strings** scoped to one paragraph, and
an entity *id* only exists after a human accepts that candidate ([[human-in-the-loop]], INV-1), the
edge has **no valid endpoints to reference** at extraction time. Writing it eagerly would create a
dangling edge — exactly the integrity violation this term names. Story Forge keeps integrity by
writing **lazily**: an edge is committed only once **both** surface endpoints *resolve* to accepted
entity ids, and the resolution targets the **committed** id (so a merged endpoint points at the
survivor, not a vanished provisional node). This is also why "re-point edges after a merge" mostly
*dissolves* under intercept-before-write — the edge is born already pointing at the right node, rather
than written first and corrected later. The Neo4j adapter reinforces it: `create_relation` does
`MATCH (s),(o) ... CREATE`, so a missing endpoint simply writes no edge instead of a dangling one.
Distinct from [[idempotency]] (which asks "what if the *same* write runs twice"): integrity is about
*where a reference points*, idempotency about *how many times it fires*.
