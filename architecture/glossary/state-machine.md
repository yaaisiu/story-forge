---
type: glossary-term
slug: state-machine
updated: 2026-06-02
status: living
related: ["[[idempotency]]", "[[invariant]]"]
---

# state machine (maszyna stanów)

**Definition:** a model of a thing's life as a fixed set of named **states** plus the *only*
legal **transitions** between them — including terminal states and explicitly impossible moves.

**Answers:** "what states can this be in, and which changes are allowed?"

**First encountered in:** [[overview]]

Modelling *state machines, not naïve status flags* catches whole bug classes: a transition's
**guard** enforces an invariant (the move is legal only if a precondition holds) and its
**effect** writes the evidence (e.g. an audit row). In Story Forge the candidate lifecycle
(`extracted → … → merged | created | rejected`) and the ingest job are the two to draw.
