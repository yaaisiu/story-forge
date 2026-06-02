---
type: glossary-term
slug: failover
updated: 2026-06-02
status: living
related: ["[[model-tier-routing]]", "[[fail-closed]]"]
---

# failover (przełączanie awaryjne)

**Definition:** when one provider in a tier errors or rate-limits, transparently retrying the
*same call* against the **next configured provider in that same tier** — the caller never sees the
swap, only the eventual result (or a tier-exhausted error).

**Answers:** "what happens when the provider I wanted is unavailable — does the whole call fail, or
does it route around the failure?"

**First encountered in:** [[m2s2-llm-router-budget-cap]] (§6.5 "Failover within a tier").

The subtlety is *which* failures trigger it: a 429 rate-limit or a 5xx → fail over; a 401 bad key →
fail **fast** (the next attempt to the same provider can't help, and retrying wastes the failover
budget); a schema-parse failure → retry the *prompt*, not the *provider*. Failover stays **within**
a tier — it never silently escalates to a more expensive tier, because that would cross a cost /
consent boundary ([[trust-boundary]]). Contrast with [[fail-closed]]: failover keeps the call
*alive* across provider faults, while fail-closed *stops* the call on a policy breach (budget cap).
