---
type: glossary-term
slug: invariant
updated: 2026-06-02
status: living
related: ["[[state-machine]]", "[[fail-closed]]"]
---

# invariant (niezmiennik)

**Definition:** a rule the system must never break, across every edge case, race, and partial
failure — a design contract, not a preference.

**Answers:** "what must stay true no matter what happens?"

**First encountered in:** [[invariants]]

An invariant nobody *enforces* is just a wish, so each one names its **guard** — the exact place
a transition is refused if the rule would break. Story Forge's invariants are collected in
[[invariants]] (e.g. "no entity is merged without a human").
