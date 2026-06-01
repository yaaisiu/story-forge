<!--
  COMPONENT TEMPLATE.
  Lives in the vault at: architecture/components/<slug>.md  — one file per major component.
  A "component" is a part of the system with a single clear responsibility and an owner of
  some facts. These notes are the map `decompose-requirement` reads to find what a new
  requirement ripples INTO, and that `review-architecture` checks for drift against the code.
-->
---
type: component
slug: example-component
updated: 2026-06-01
# Components evolve with the system, so they sit in the long-lived "living" status.
status: living
related:
  - "[[some-other-component]]"
---

# <Component name>

## Responsibility

<ONE sentence: what this component is responsible for. If you need "and", consider whether
it's really two components. (Single responsibility — pojedyncza odpowiedzialność: a component
should have one reason to change.)>

## Source of truth

<Which facts does THIS component authoritatively own? e.g. "the canonical chunk boundaries
for a document." Doctrine #4: every meaningful fact has exactly one home — name it here so
no other note can silently claim the same ownership.>

## Interfaces

- **Exposes:** <what other components/users call on it>
- **Consumes:** <what it depends on to do its job>

## Invariants

<Rules this component must never break, across any edge case. Each is a design contract →
also recorded in [[invariants]]. e.g. "never emits a chunk that overlaps another chunk.">

## State

<If this component owns a stateful entity, link its state machine: [[state-machines/<entity>]].
If it is stateless, say so explicitly — that itself is a useful architectural fact.>

## Layer fingerprint

<The nine-layer lens projected onto THIS component, at component altitude. Whole-system
layers (User/personas, Business) live in [[project]]; Domain and Behavior are already
captured above (Responsibility/Source of truth, and State). Fill the five runtime-risk
layers below — write "n/a — <reason>" rather than leaving one blank, because a blank reads
as "not considered" while "n/a" reads as "considered and dismissed".>

- **Security** — <threat/abuse surface; which trust boundaries (granice zaufania) it sits on>
- **Data sensitivity** — <classification of data it handles: public / internal / PII / secret>
- **Errors** — <primary failure modes; does it fail-open or fail-closed on failure?>
- **Compliance / Audit** — <what evidence does this component leave behind — what records, are
  they tamper-evident, how long retained? The golden line's "what remains after the fact".>
- **Operations** — <the observable signal that answers "is this component healthy right now?">
