---
type: adr
slug: 0001-nine-layer-model
updated: 2026-06-01
status: accepted
related: []
---

# ADR 0001 — Nine-layer model: split Compliance/Audit out of Security

> This is one of the meta-architect's *own* design decisions, recorded in its own MADR
> format. It governs the layer lens the agent applies in every project. Escalated form
> (Decision drivers + per-option pros/cons) because the decision touches a
> security/compliance boundary and weighs three live options — exactly the escalation
> triggers defined in `templates/adr.md`.

## Context and problem statement

The agent passes every requirement through a fixed set of architectural layers — a lens
that asks the same questions in the same order so nothing important is skipped. The seed
set was eight: User/personas · Business · Domain · Data · Behavior · Errors · Security ·
Operations.

The question: should **compliance and audit** — regulatory/contractual obligations and the
durable evidence trail of what happened — be a layer of its own, or stay folded inside
Security and Operations?

A note on framing, because it is itself an architectural principle: the project this lens is
first used on (Story Forge) is a local, single-user app with little present risk. That does
**not** argue for a leaner lens. **Architecture models the durable shape of what we are
building, independent of today's risk appetite.** A layer is cheap to carry now and
expensive to retrofit once an obligation or a second user appears. We design the discipline
in; we do not wait for the incident.

## Decision drivers

- The operator is deliberately building intuition in **security, compliance, and audit**.
  Folding a concern away is how a learner never learns to see it; a first-class layer keeps
  it in view on every pass.
- Compliance/Audit answers a **different question** than Security. Security asks *"can an
  attacker break in or abuse this?"* Compliance/Audit asks *"can we prove what happened, and
  that we met our obligations?"* Threat-prevention and provable-adherence are distinct axes.
- It anchors the **golden line** — *"what evidence remains after the fact"* — to a layer that
  owns it, rather than leaving it homeless between Security and Operations.
- Counter-driver: **simplicity**. Every added layer is ceremony on every decomposition and
  dilutes the discipline if it earns its place weakly.

## Considered options

- **A — Keep eight layers.** Compliance/Audit stays folded into Security (controls) and
  Operations (logs/retention).
- **B — Nine layers: split Compliance/Audit into its own layer.** *(chosen)*
- **C — Ten layers: add Compliance/Audit *and* Cost** as separate layers.

### A — Keep eight
- **Pros:** Leanest; proven, widely-used set; least ceremony per feature.
- **Cons:** Audit/evidence is easy to forget when it lives inside two other layers; does not
  serve the operator's explicit learning focus; the golden line's "evidence" has no home.

### B — Nine (chosen)
- **Pros:** Evidence/audit gets first-class attention on every pass; teaches the
  Security-vs-Compliance distinction; gives the golden line a home layer.
- **Cons:** One more layer to fill each decomposition; risk of "n/a" fatigue on trivial
  features — mitigated by the **"n/a — reason" discipline** (a named non-applicability is a
  decision, not a blank).

### C — Ten (add Cost)
- **Pros:** Cost visibility would suit Story Forge's multi-tier LLM routing.
- **Cons:** Two new layers at once over-corrects and dilutes the lens; Cost lives acceptably
  inside Business (why) + Operations (run cost). Reconsider as a separate decision if needed.

## Decision

Adopt **Option B**. The canonical lens is **nine layers**, with Compliance/Audit inserted
immediately after Security:

1. User / personas
2. Business
3. Domain
4. Data
5. Behavior
6. Errors
7. Security
8. **Compliance / Audit**  *(new — provable adherence + the durable evidence trail)*
9. Operations

## Consequences

- **Good:** Evidence and audit get explicit attention everywhere the lens is used; the model
  aligns with the golden line; the operator's priority concern is always in view.
- **Cost we accept:** A ninth layer on every decomposition, and the chance of routine "n/a"
  entries on low-stakes features. We accept it because under-modelling is the more expensive
  error, and the n/a-with-reason convention keeps the cost honest rather than hollow.
- **Follow-ups:**
  - Clarify, in the agent system prompt, the relationship between the nine **layers**
    (dimensions of *analysis* — what aspects to examine) and the nine **stations**
    Identity→…→Review (a checklist for a feature's *enforcement lifecycle* — is each control
    present). They intersect at Evidence/Review but are different axes; the learner must not
    conflate them.
  - Carry the nine-layer list verbatim into the agent prompt and the `project.md` /
    `state-machine.md` templates so all artefacts share one definition.
