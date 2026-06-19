---
type: glossary-term
slug: lost-update
updated: 2026-06-19
status: living
related:
  - "[[toctou]]"
  - "[[idempotency]]"
  - "[[m4-entity-editing]]"
---

# lost update (zgubiona aktualizacja)

**Definition:** a concurrency anomaly where two writers each read a value, then each write back based
on what they read — and the second write **silently overwrites** the first, which it never saw. The
first writer's change is *lost* with no error. It is the **write-side cousin** of a [[toctou]] race
(time-of-check to time-of-use): TOCTOU is a *read* invalidated by a concurrent change between check and
use; a lost update is a *write* clobbering a concurrent write between read and write-back.

**Answers:** "two browser tabs (or a tab and a background refetch) both edit the same entity — what
stops one edit from quietly erasing the other?"

**First encountered in:** [[m4-entity-editing]]

The two classic defences: **last-write-wins** (accept the clobber — simplest, and defensible when true
concurrency is rare) or **optimistic concurrency control** (the writer carries a version/etag it read;
the write is refused — typically HTTP 409 — if the stored version has moved on, so the loser re-reads
and retries). Story Forge's first graph-editing slice (M4.S3a) proposes **last-write-wins at PoC**: one
local author makes a genuine simultaneous edit unlikely, so the anomaly is *named and accepted*, not
guarded — optimistic concurrency is the clean V1 refinement if multi-tab editing ever bites. (Contrast
the relation-commit path, which *does* guard its TOCTOU read with a re-resolve-at-commit — see
[[relation-lifecycle]] — because there the cost of a stale write is a wrong graph edge.)
