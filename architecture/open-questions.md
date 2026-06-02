---
type: open-questions
slug: open-questions
updated: 2026-06-02
status: living
related: ["[[overview]]", "[[project]]", "[[invariants]]", "[[2026-06-02-architecture-review]]"]
---

# Open questions — Story Forge

Decision points and gaps the architect has **framed but not resolved**. The architect's job is
to surface the consequence and lay out options; the human decides. Resolved items are struck
through with a dated note (history is never deleted), mirroring the plan files' convention.

Two homes, kept distinct:
- **Owned by the spec** — the spec's own §10 has ten "decide as we go" questions. Those stay
  the spec's; this note **references** them (below) rather than copying, so there is one home.
- **Raised by this vault** — architectural gaps the nine-layer/nine-station seed pass surfaced
  that the spec does not yet track. Those are the numbered items here.

---

## Priority queue (from the init interview — "check what's built, then strategize")

The operator's stated order for the architect's *next* deep work, after this seed run:

1. **OQ-A · Validation/drift sweep over what's already built.** Run the meta-architect
   `review-architecture` skill over M0→M2.S1 + the existing ADRs (`docs/decisions/0001–0002`):
   does the code match the decisions on record? Are there choices visible in code with no ADR?
   Any invariant near-misses already present? **Specifically, audit each invariant's "Enforced
   at" guard against actual build state** — INV-2/3/4/5/7 currently describe guards that are
   partly *planned* (router, paid providers, consent UI, candidate schemas, review queue land in
   M2.S2+/M3); keep each invariant's as-built-vs-planned split honest as that code lands. —
   *This is the literal first thing to do next; it is what the operator asked for.*
2. **OQ-B · Forward strategy pass.** Once the present is validated, a strategy pass on the
   upcoming work (M2.S2 router+budget, then M2.S3–S6) and its alignment with `docs/PLAN_LONG.md`
   — likely via `decompose-requirement` on the next concrete feature (the `LLMRouter`).
3. **OQ-C · Then, and only then,** decide where the first per-component note (`components/`)
   should land — candidates: the cascade (§3.3), the router (§6.5), the ingest job (§7).

> Deferred by design (ADR 0002): wiring these skills into `/resume-session`, `/wrap-session`,
> `/review-pr` happens *after* living with this vault once — not pre-emptively.

---

## Raised by this vault (gaps the seed pass found)

### OQ-1 — Two-store write consistency (Neo4j entity ↔ Postgres mention)
An entity's identity lives in Neo4j; its `entity_mentions` live in Postgres. The two stores
**cannot share a transaction**. *But what if* the Neo4j write succeeds and the Postgres
mention write fails (or vice versa)?
- **Options:** (a) write-Neo4j-then-Postgres with a reconciliation/repair pass on startup;
  (b) outbox pattern (record intent in one store, replay); (c) accept eventual inconsistency at
  PoC scale and add a "verify graph↔mentions" maintenance check.
- **My proposal:** (c) for the PoC (single user, low volume, reversible), with a cheap
  consistency check surfaced in the UI — but flag it as a real seam to revisit if it bites.
- **Lands in:** M2.S4 (first time both writes coexist). Open.

### OQ-2 — Ingest job partial-failure recovery
*But what if* extraction dies halfway through a 50k-word story? Is the job resumable, or does
the user re-run from scratch? Is there an ingest-job state record at all, or only per-paragraph
side effects?
- **Options:** (a) per-paragraph idempotent writes + resume-from-last-done; (b) whole-story
  transaction-ish redo; (c) no recovery at PoC (re-upload).
- **My proposal:** (a), leaning on idempotency (see [[idempotency]]) — paragraphs already have
  stable ids. Needs the candidate/job state machines drawn (see [[overview]] Layer 5). Open.

### ~~OQ-3 — `cloud_free` quota-exhausted behaviour~~ ✅ Resolved 2026-06-02
**Resolution** (ADR 0003; spec §6.5 amended): on a GPU-less host the `local_small` degrade target
becomes the **cheapest cloud_free model**; on genuine cloud_free-quota-exhaustion **or** the daily
budget cap, the router **pauses and asks the user** — never a silent paid escalation (control-first).
This also fixed the live intra-spec contradiction (step 5 vs the hardware para). Original framing kept
below for history.

§6.5 step 5 says "degrade to local_small with warning OR pause for user." On a GPU-less host,
local_small is impractical — so the real choices narrow. *But what if* the Ollama Cloud weekly
GPU quota runs out mid-ingest?
- **Options:** (a) pause and ask the user to switch to a paid tier; (b) auto-escalate to
  cloud_strong within a budget ceiling; (c) hard-stop.
- **My proposal:** (a) by default, (b) only if the user pre-authorised a budget — ties to
  INV-5. Lands around M2.S2. Open.

### OQ-4 — Retention / Expiry policy (the empty station)
The nine-station pass found **Expiry** empty: no stated retention for uploaded source files,
per-call LLM logs, or orphaned upload sandboxes (the latter is already a known cross-cutting
cleanup item in `PLAN_SHORT.md`). *But what if* logs of full prompts (which contain the
author's text) accumulate indefinitely?
- **Options:** (a) no retention policy at PoC, documented as accepted; (b) a simple
  age-based cleanup for sandboxes + a cap on log volume.
- **My proposal:** (b) for sandboxes (already tracked), (a) documented for logs at PoC. Open.

### OQ-5 — `ExtractionAgent` prompt-injection-by-structure pass
Before M2.S3 ships, confirm the extraction prompt renders structure **only** from the trusted
Jinja2 template and never reparses model output mixed with story text — the same class of
hardening already applied to `ChunkingAgent` and encoded in `/review-pr` §4.
- **Status:** not a decision so much as a **must-verify** gate for M2.S3. Tracked here so it is
  not forgotten. See [[overview]] Layer 7 (Security).

### ~~OQ-6 — INV-2 consent guard lags the paid-egress risk by ~3 sessions~~ ✅ Resolved 2026-06-02
**Resolution** (ADR 0003 / D5): option (a) — the per-fragment consent UI stays at M2.S5; M2.S2 ships
**no** egress gate (the PoC handles no security-sensitive data), with a clear in-code marker at the
egress point documenting the deferral. The proposed temporary INV-9 is **dropped**. INV-2's full
guard lands with the M2.S5 panel; until then its enforced guard remains "no-telemetry + chosen-provider
egress", honestly narrower than the rule. Original framing kept below.

Surfaced by the 2026-06-02 review (`reports/2026-06-02-architecture-review.md`). M2.S2 adds the
**paid-provider egress paths** (text can leave to Anthropic/OpenAI/etc.) and cost-tracking, but the
**explicit-consent UI** INV-2 demands ("sending fragment to Anthropic, OK?") is not scheduled until
**M2.S5**. *But what if* an M2.S3 smoke-test fires a real paid call — text crosses the only real
[[trust-boundary]] with no consent gate and nothing fails closed.
- **Options:** (a) accept the window at PoC, documented; (b) land a minimal pre-egress guard *with*
  the paid adapters in M2.S2 — a default-deny config flag or per-call confirmation — so INV-2's
  guard ships when the risk does, the consent UI (M2.S5) being the richer version later.
- **My proposal:** (b). A guard that arrives three sessions after the egress it governs is
  fail-open by sequencing (see [[fail-closed]]). Decide in M2.S2 planning. Open.

### ~~OQ-7 — INV-5 needs the provider return-shape to grow, and cap-check ordering enforced~~ ✅ Resolved 2026-06-02
**Resolution** (ADR 0003 / D4 / spec §6.6 amended): option (a) — `CompletionResult` + the Protocol
grow to carry `model`, `input_tokens`, `output_tokens`, nullable `gpu_seconds`, `cost_estimate`;
`OllamaProvider` stops discarding the eval counts. One `llm_calls` table, nullable per tier; the
cap is checked **before** dispatch (fail-closed) with a documented bounded one-call overshoot; tier/
provider/model are system-derived (INV-7). Lands in M2.S2. Original framing kept below.

Surfaced by the 2026-06-02 review. Today `CompletionResult` (`adapters/llm/base.py`) carries only
`content` + `model_tier`; `OllamaProvider.complete` **discards** the `prompt_eval_count` /
`eval_count` token counts Ollama already returns. INV-5 ("record `model, input_tokens,
output_tokens, cost_estimate`") therefore cannot be satisfied without **growing the return shape**
(and every adapter populating it), not just adding Protocol fields. Separately, INV-5's "cap check
**before** dispatch, refused not logged-after" is an **ordering** constraint ([[fail-closed]]) with
no enforcer yet.
- **Options:** (a) extend `CompletionResult` with `model_name` + `usage` (input/output tokens) +
  optional `cost_estimate`, populated per-adapter; (b) a separate post-call usage record keyed off
  the call. (a) keeps provenance with the call that owns it (see the review's
  caller-vs-system-derived note — also INV-7's `model_tier` near-miss).
- **My proposal:** (a) + the router checks-then-dispatches (cap guard before the paid call fires).
  This is the core of the M2.S2 `decompose-requirement` pass. Open.

---

### ~~OQ-8 — M2.S2 router + budget decision register (D1–D6)~~ ✅ Resolved 2026-06-02
**All six resolved** by the owner and recorded in **`docs/decisions/0003`** + `docs/PLAN_SHORT.md`
Decided (spec §6.5/§6.6 amended): **D1** per-day USD cap + reports; **D2** hand-rolled `httpx` (no
SDK); **D3** accept bounded one-call overshoot; **D4** one `llm_calls` table; **D5** defer egress
gate, documented (no INV-9); **D6** → ADR 0003 supersedes ADR 0001's provider strategy. Provider
order: Ollama → OpenRouter → Grok → Anthropic → Google → OpenAI; build OpenRouter only now. Original
register kept below for history.

_The original framing, preserved as history (all six were since **resolved** — see the struck header
above and `docs/decisions/0003`)._ The `decompose-requirement` pass on M2.S2
(`proposals/m2s2-llm-router-budget-cap.md`) framed six decisions that were open **at that time**; the
full Context/Options/Proposal for each lives in the proposal's Decision register:
- **D1 — budget-knob grain.** Per-call / session / day. *Proposal:* per-day USD hard-stop only
  (spec-faithful) + per-project/task-type as read-only aggregates. (Day-grain → local-midnight,
  resolved.)
- **D2 — Anthropic SDK vs hand-rolled `httpx`.** *(dependency-baseline boundary)* *Proposal:*
  hand-rolled httpx for INV-7 uniformity + minimal deps; cost accepted = hand-written usage parsing.
- **D3 — cap atomicity under concurrency** (the [[toctou]] race). *Proposal:* accept one-call
  overshoot at PoC, documented; reserve-then-reconcile if batched concurrency lands.
- **D4 — one usage table, two billing units** (tokens vs GPU-seconds). *Proposal:* one `llm_calls`
  table, nullable per-tier; don't fabricate a USD value for free-tier GPU time.
- **D5 — paid-egress enablement gate** *(trust-boundary; ties INV-2/OQ-6)*. *Proposal:* default-deny
  config flag now, rich consent UI in M2.S5 (proposed temporary INV-9).
- **D6 — ADR-0001 reconciliation.** Amend vs supersede (ADR 0003) vs leave-in-plan. *Proposal:*
  supersede if D1–D5 accepted as a cluster, else amend. (Outcome: **ADR 0003 authored**, supersedes.)
- **Gaps for the PO (proposal §8):** G1 quota-exhaustion decision (+ possible spec §6.5 amendment for
  the step-5-vs-hardware contradiction), G2 egress-gate posture, G5 log retention (Expiry/OQ-4).
- **Lands in:** M2.S2 (next product session). See [[m2s2-llm-router-budget-cap]].

## Referenced — owned by spec §10 (not duplicated)

The spec carries ten "decide as we go" questions; they remain the spec's to own. Listed here by
title only so the vault's reader knows they exist and where to read them
(`story-forge-poc-spec.md` §10):

1. LLM extraction granularity (per-paragraph / scene / chapter). · 2. Graph versioning /
rollback strategy. · 3. Shared-world conflicting-property resolution. · 4. Export format for
the "world bible". · 5. **Agent framework — roll-our-own vs adopt** (Pydantic AI / LangGraph /
smolagents …) — *architecturally the heaviest; a likely future ADR.* · 6. Backup strategy. ·
7. `edit_history` export format (JSONL/SFT/DPO). · 8. Multilingual entity naming (PL/EN peers
vs main). · 9. Keyboard shortcuts. · 10. V1 "world summary" export to Obsidian.

When any of these is actually decided, it becomes an **ADR** (in `docs/decisions/` if it is a
product decision, or framed here first) — the spec then references the ADR. The architect never
resolves one of these unilaterally.
