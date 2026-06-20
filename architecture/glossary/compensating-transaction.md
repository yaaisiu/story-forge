---
type: glossary-term
slug: compensating-transaction
updated: 2026-06-20
status: living
related:
  - "[[idempotency]]"
  - "[[referential-integrity]]"
  - "[[lost-update]]"
  - "[[m4-s3b-graph-mutations]]"
---

# compensating transaction (transakcja kompensująca)

**Definition:** when a single logical operation spans several writes that **cannot share one atomic
transaction** (e.g. a Neo4j change *and* a Postgres change, or N separate edge writes), you make it
reversible not by rolling back a database transaction but by recording, for each forward step, enough
information to emit its **inverse** later. Undo = apply the inverses in reverse order. This is the
**saga** pattern's undo half: a long-running, multi-step operation kept consistent by compensating
actions rather than by a single ACID transaction.

**Answers:** "a merge is one user action but many writes across two stores — how do I make 'undo this
merge' restore *exactly* the prior state when there's no one transaction to roll back?"

**First encountered in:** [[m4-s3b-graph-mutations]]

The discipline it imposes: the **reversibility unit is the command, not the individual write** — so the
audit log must *group* a command's writes (an `operation_id`) and each row must carry a complete enough
**before-image** that its inverse is unambiguous. Two failure modes to name: an **incomplete
before-image** (the merge re-pointed 20 edges but the log caught 19) is a non-reversible action
*masquerading* as reversible — worse than no undo; and undo over **drifted state** (the merged entity
was edited after the merge) is a [[lost-update]] in reverse — refuse rather than clobber the newer
change. Each forward step and each inverse must also be [[idempotent]], so a crash mid-operation leaves
a retryable state, never a half-applied one. (Story Forge M4.S3b: entity merge/delete consume the
append-only `graph_edits` log this way — the spec's own §10-q2 "append-only log of changes", *executed*
as undo, rather than full graph version snapshots.)
