---
type: glossary-term
slug: source-of-truth
updated: 2026-06-02
status: living
related: ["[[compliance-audit-layer]]"]
---

# source of truth (źródło prawdy)

**Definition:** the **one** authoritative home for a given fact. Everywhere else that needs the
fact *references* it rather than copying it.

**Answers:** "if two places disagree about this, which one is right?"

**First encountered in:** [[project]]

A copy is a *second* source of truth, and two copies that can drift apart is the bug this concept
prevents. The vault's defining discipline is to **reference** the spec, plans, and code (see the
registry in [[project]]) and add only the architectural layer they don't already hold.
