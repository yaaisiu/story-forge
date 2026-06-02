---
type: review
slug: 2026-06-02-architecture-review-post-m2s2
updated: 2026-06-02
status: living
related: ["[[overview]]", "[[invariants]]", "[[open-questions]]", "[[m2s2-llm-router-budget-cap]]", "[[2026-06-02-architecture-review]]", "[[model-tier-routing]]", "[[fail-closed]]", "[[toctou]]"]
---

# Architecture review — 2026-06-02 (post-M2.S2 as-built sweep)

> **Second sweep of the day, different subject.** The earlier
> `[[2026-06-02-architecture-review]]` was the *pre-build* OQ-A diagnosis that produced the M2.S2
> decisions (now resolved). **This one is the *post-build* drift check**, run at the end of
> Session 11 right after merging the router/budget/ledger feature (PR #36) + its wrap (PR #37).
> Distinct filename so neither clobbers the other; this is the current health snapshot.

**Scope.** As-built M2.S2 (`adapters/llm/{base,ollama,openrouter,router,cost,postgres_cost_store}.py`,
`api/llm.py`, the `llm_calls` migration, `config.DAILY_BUDGET_USD`) vs. the vault's claims —
`[[invariants]]` INV-2/5/6/7, the `[[m2s2-llm-router-budget-cap]]` proposal (data-flow, state
machine, edge-cases), and ADR 0003. **Plus a forward lens** (owner-requested): `docs/PLAN_SHORT.md`
next-steps (handoff + Sessions 3–6) against the invariants/decisions/state-machine.

Severity legend: **blocker** (resolve before dependent work) · **risk** (will bite if unaddressed) ·
**watch** (track; not yet urgent).

## Headline

**No blockers, no risks — the M2.S2 build is a faithful projection of ADR 0003 + the proposal.**
The two pre-build *risks* (INV-2 egress lag, INV-5 return-shape/cap-ordering seam) are **closed** as
designed, and the **INV-7 near-miss is closed** (the ledger records system-derived tier/provider/model,
never the caller's echoed label). What remains is all **watch**: (1) the invariant notes still read
"planned (M2.S2)" and need flipping to as-built; (2) three genuine *forward* gaps the plan should
track — **`latency` is recorded nowhere** though INV-5 and the S5 panel expect it; the
**malformed-`200`-envelope** path is uncaught; a **paused batch has no resumable catcher**; and (3)
one unrecorded design choice (the **independent-commit ledger**). The forward lens found **no
contradiction** between the plan and the vault — only things to add.

## 1. Drift — vault vs reality

- **`watch` — INV-2 / INV-5 / INV-7 "Enforced at" still say "planned (M2.S2) … not yet built."**
  They are built now. Each note needs its guard prose flipped from planned → as-built:
  - **INV-5** — the guard is now real: `LLMRouter.complete` checks `spend_today_usd() >= DAILY_BUDGET_USD`
    *before* dispatch (fail-closed), and `PostgresCostStore.record` writes one `llm_calls` row on
    **every** terminal edge including refusals/failures. Enforced at `adapters/llm/router.py` +
    `postgres_cost_store.py`.
  - **INV-7** — the **near-miss is closed**. The ledger records `tier` (the router's own chosen tier,
    not `result.model_tier`), `provider = type(provider).__name__`, and `model` from the *response* —
    all system-derived. A caller can no longer make the cost ledger lie.
  - **INV-2** — paid egress now exists (`OpenRouterProvider`); the guard is still the documented
    deferral (consent UI → M2.S5, in-code marker at the egress point), exactly per ADR 0003 D5. The
    note already records this; just drop the "not yet built" tense on the *egress* half.
- **`watch` — `CompletionResult.model_tier` is still the caller-passed argument (cosmetic).** It is
  echoed from the `model_tier` the router hands the adapter, so it is *not* an authoritative record of
  what served the call. Harmless today because the ledger ignores it (it records the router's own
  `tier`), but a future reader could mistake it for provenance. Worth a one-line note on the field, or
  deriving it in the adapter. Not a violation — INV-7's *ledger* guard already uses system-derived data.

## 2. Source-of-truth conflicts

- **`watch` — `latency` has three disagreeing homes → OQ-9.** `[[invariants]]` INV-5 says a usage row
  records "`model, input_tokens, output_tokens, cost_estimate` **(and latency)**"; the
  `[[m2s2-llm-router-budget-cap]]` proposal (§4/§5/§8) repeats "tokens/GPU-s, cost, **latency**"; the
  **M2.S5 panel task** in `docs/PLAN_SHORT.md` lists **latency** as a column it shows. But the as-built
  `llm_calls` table and `LlmCallRecord` record **no latency**, and spec §6.6's enumeration does **not**
  list latency either. So: the spec doesn't require it, but two vault notes *and* the S5 plan promise
  it. Decide before M2.S5: **add a `latency_ms` column now** (cheap, and the panel will want it), or
  **trim INV-5/the proposal** to match the spec + as-built. Don't leave three homes disagreeing.

## 3. Missing / undrecorded decision records

- **`watch` — the independent-commit ledger is an architectural choice with no vault home.**
  `PostgresCostStore` deliberately commits each write on **its own short-lived connection**, *not* the
  request transaction, so a failure row survives a request that rolls back on the very failure it
  records — this is the mechanism that makes INV-5's "record refusals/failures … explain why a batch
  stopped" actually hold. It's captured in `docs/PLAN_SHORT.md` **Decided** + the code docstring, but
  absent from the vault's decision framing and from ADR 0003. **Propose** (not author): fold a one-line
  *enforcement* clause into INV-5 ("the record is committed independently of the request txn so a
  rollback can't erase the trail") rather than a whole new ADR — the decision is already recorded; the
  vault just doesn't reflect the *why*.

## 4. Invariant near-misses (fresh "but what if")

- **`watch` — INV-6: first paid-key-holding code, and the redaction middleware it names still doesn't
  exist.** The new adapters log **nothing** (verified: no `log`/`logger` calls in `adapters/llm/`), so
  keys don't reach a log line today — INV-6 holds by construction. But the prior sweep already flagged
  that the "strip `Authorization`/`X-API-Key`" middleware INV-6 *names* is unbuilt, and M2.S2 is now the
  first code holding paid keys. The moment **any** provider request/response/**error body** is logged
  (M2.S5 observability, or a debugging session), redaction must exist first — provider `400`s routinely
  echo the offending payload, which here is the author's text crossing the only real trust boundary.
  This is "fail-open by sequencing" waiting to happen; build the redaction before the first provider log.
- **`watch` — the D3 cap-overshoot bound weakens the moment batching goes concurrent.** Today the
  TOCTOU overshoot is bounded to one in-flight call because ingest is sequential. **M2.S3 introduces
  per-paragraph dispatch**; if it ever runs paragraphs concurrently, "one-call overshoot" no longer
  holds and the reserve-then-reconcile path (proposal D3 option c) becomes the right answer. Track
  against M2.S3's dispatch shape — see [[toctou]].

## 5. Structural / forward lens (plan vs architecture)

The owner asked to check the next-steps plan against the architecture. **Result: no contradiction** —
S3 respects INV-4 (open-world `type` string, no enum) + INV-7 (one Protocol); S4 respects INV-1 +
INV-8 (no-dedupe) and lands OQ-1 (two-store consistency); S5 consumes the ledger; S6 matches ADR 0003's
"direct vendor adapters as-needed." The plan is well-aligned. The forward lens surfaces **things to
track, not conflicts**:

- **`watch` — the LLM-call lifecycle state machine is built but undrawn.** The proposal §5 nominated it
  as the vault's *first* `state-machines/` note (`requested → guarded → {refused | dispatched} → {succeeded
  | retrying → (dispatched | exhausted) | fatal}`). It now exists in code; drawing it would let the
  `fatal`-vs-`failover` edges (the malformed-envelope case below) be reasoned about precisely. Strong
  candidate for the next architect deep-dive (ties OQ-C).
- **`watch` — OQ-2 (resumable ingest) is now concrete → the router *raises* but nothing *catches*.**
  `LLMRouter.complete` now raises `BudgetExceededError` / `QuotaExhaustedError` mid-call (pause-and-ask),
  but no caller yet turns that into a *resumable* batch. The proposal §7 "cap hit on call N of a
  200-paragraph ingest → pause resumably" lands in **M2.S3/S4** when `ExtractionAgent` does batch
  dispatch — that's where the catcher + per-paragraph resume-from-last-done belongs. Extend OQ-2 with
  this now-live trigger.
- **`watch` — malformed-`200`-envelope is uncaught → OQ-10.** The proposal §7 predicted it exactly: a
  provider returning `200` with a broken body (missing `choices`/`message`, an error shaped as success,
  a proxy injecting JSON) raises a parse error *inside* `provider.complete()`. The router catches
  `HTTPStatusError` + `RequestError` but **not** this — so it neither records nor fails over, unlike the
  "envelope-malformed → failover" the proposal calls for. Already tracked as a `docs/PLAN_SHORT.md`
  **M2.S3 cross-cutting** item (typed `ProviderResponseError`); mirrored here as OQ-10 so the vault
  tracks it against the state machine's `fatal`/`failover` edges.
- **`watch` — OQ-5 (ExtractionAgent prompt-injection) is the must-verify gate for M2.S3** — unchanged,
  still open, and the handoff already names the injection-safety test. No action here beyond confirming
  it stays on the S3 checklist.

## 6. Process note — when to run this sweep (evidence for ADR 0002)

The owner ran this sweep **at session wrap (end), not resume (start)**, and stated that as a
preference. It is the better placement on the merits: at wrap there is a *fresh as-built* to diff
against the design briefing, and the findings seed the *next* session's step 0 instead of front-loading
it. This is concrete evidence for **where** the still-deferred ritual integration (ADR 0002 §4) would
attach if/when we wire it: `review-architecture` → `/wrap-session`, not `/resume-session`. Recorded in
`learning-log` + the open-questions priority queue; the integration itself stays deferred (run by hand).

## 7. Concepts worth studying (the teaching payoff)

- **Write-ahead / out-of-band audit logging** — *why an audit ledger commits outside the business
  transaction.* The independent-commit `PostgresCostStore` is a small instance of a general rule: if a
  record must survive the failure it describes, it cannot share the transaction that rolls back on that
  failure. Read on the **outbox pattern** and **append-only logs** for the grown-up versions.
- **Poison message / dead-letter handling** — the malformed-`200`-envelope is a "poison response": input
  that breaks the consumer every time it's retried. The discipline is to *quarantine and move on* (here:
  failover + record), never to retry the same dead provider forever. The terms are worth owning before
  M2.S3 designs the `ProviderResponseError` path.
- **Terminal states & total functions over a state machine** — the LLM-call lifecycle has four terminal
  states (succeeded/refused/exhausted/fatal); a robust router is *total* over them (every error class maps
  to exactly one). The two bugs Codex caught in PR #36 were both "a class that mapped to the wrong
  terminal" — the cure is enumerating the state machine, which is why drawing it (§5) earns its place.
- **Fail-open by sequencing** (revisited) — INV-6's "redaction must exist *before* the first provider
  log" is the same shape as the (now-resolved) INV-2 egress-lag: a guard that arrives after the risk it
  governs is effectively absent in the window between. A useful lens for ordering any guard-vs-feature.

## Hand-off

- **No blockers/risks**; all findings are `watch`. The as-built faithfully implements ADR 0003.
- **Vault edits this sweep makes** (trail only, never code): adds OQ-9 (latency), OQ-10 (malformed
  envelope), extends OQ-2 (resumable pause now has a raiser); appends `learning-log` + `CHANGELOG`.
- **Recommended (human decides):** ~~flip INV-2/5/7 guard prose to as-built + add the INV-5
  independent-commit clause~~ ✅ **applied in this same session fold** (owner-approved) — INV-2/5/7
  now read as-built, INV-5 carries the durability + OQ-9-latency clauses, INV-7 records the near-miss
  as closed. Still open for the human: decide the `latency` question (OQ-9) before M2.S5; keep the
  malformed-envelope (OQ-10) + INV-6 redaction items on the M2.S3 checklist. None of these block M2.S3.
- **Owner's call still pending:** whether to draw the LLM-call state machine now (the first
  `state-machines/` note, ties OQ-C) — a good next architect deep-dive, not required before S3.
