---
type: glossary-term
slug: toctou
updated: 2026-06-02
status: living
related: ["[[fail-closed]]", "[[idempotency]]"]
---

# TOCTOU — time-of-check to time-of-use

**Definition:** a race where the condition a piece of code *checked* is no longer true by the time
it *acts* on it, because a concurrent actor changed the state in between. The check and the use are
not atomic, so the guarantee the check seemed to give is an illusion under concurrency.

**Answers:** "is this guard actually safe if two things run at once, or only when they run one at a
time?"

**First encountered in:** [[m2s2-llm-router-budget-cap]] (the budget cap).

Classic example here: the budget guard reads `day_spend < cap`, then dispatches a paid call. Two
concurrent calls can *both* read a spend below the cap, *both* pass, and *both* land — overshooting
the cap. The cap is therefore **best-effort with bounded overshoot**, not exact. Fixes are
atomicity (a lock around check+dispatch) or reserve-then-reconcile (debit an estimate *before* the
call). At Story Forge's single-user, sequential-ingest scale the race is nearly unreachable, so the
chosen posture is *name it and bound it* (worst case: one in-flight call's overshoot) rather than
pay for locking — a deliberate, documented trade, not an oversight. Relates to [[idempotency]]:
both are about what happens when the simple single-threaded mental model meets concurrency or
retries.
