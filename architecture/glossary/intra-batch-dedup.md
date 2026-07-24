---
type: glossary-term
slug: intra-batch-dedup
updated: 2026-06-15
status: living
related:
  - "[[cascade-matching]]"
  - "[[idempotency]]"
  - "[[human-in-the-loop]]"
---

# intra-batch deduplication

**Definition:** collapsing duplicate candidates produced *within a single extraction run* — or
against entities accepted *during the same review session* — as opposed to **cross-pass** dedup (a
later chapter's candidate matching an entity accepted in an earlier pass).

**Answers:** "if the same entity appears three times in one batch and the graph started empty, why
can't the review queue merge them — and how do we make it?"

**First encountered in:** [[m3s4c-intra-batch-rematch]]

The cascade as built (M3.S4a) matches each candidate against the **accepted** graph *as it stood at
extraction time*. On a first single-story pass that snapshot is empty, so recurring names stage as
independent NEW proposals and the author gets duplicate nodes — the gap the 2026-06-15 browser walk
made concrete (`Janek` ×3 → three nodes). M3.S4c closes it with **on-accept live re-match**
(re-running the *deterministic* Stage 1/2 matcher over still-pending candidates each time the human
accepts an entity, so duplicates flip `new → merge`) plus a **manual handpick** safety net for the
matcher's false negatives. Both change only *suggestions* in the Postgres staging store — never the
graph — so the human still commits every merge ([[human-in-the-loop]], INV-1/INV-9 intact). Made
[[idempotency|idempotent]] by a *monotone* re-proposal rule (only ever `new → merge`, never the
reverse), so re-running on an unchanged accepted set is a no-op.
