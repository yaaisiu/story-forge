---
type: open-questions
slug: open-questions
updated: 2026-06-23
status: living
related: ["[[overview]]", "[[project]]", "[[invariants]]", "[[2026-06-02-architecture-review]]", "[[m2s3-extraction-agent]]", "[[2026-06-09-architecture-review]]", "[[2026-06-11-architecture-review]]"]
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

The operator's stated order for the architect's deep work. **OQ-A and OQ-B are done** (2026-06-02);
OQ-C is the next architect deep-dive when one is wanted.

1. **~~OQ-A · Validation/drift sweep over what's already built.~~** ✅ **Done 2026-06-02** — the
   `review-architecture` sweep ran over M0→M2.S1 + ADRs 0001–0002, auditing each invariant's
   "Enforced at" guard against build state (`reports/2026-06-02-architecture-review.md`).
2. **~~OQ-B · Forward strategy pass.~~** ✅ **Done 2026-06-02** — `decompose-requirement` on the
   M2.S2 `LLMRouter` + budget cap (`proposals/m2s2-llm-router-budget-cap.md`); the decisions are
   settled in `docs/decisions/0003`.
3. **OQ-C · Next (when wanted):** decide where the first per-component note (`components/`) should
   land — candidates: the cascade (§3.3), the router (§6.5), the ingest job (§7).

> Deferred by design (ADR 0002): wiring these skills into `/resume-session`, `/wrap-session`,
> `/review-pr` happens *after* living with this vault once — not pre-emptively.
>
> **Evidence toward placement (2026-06-02, Session 11):** the owner ran `review-architecture` at
> **session wrap (end)**, not resume (start), and stated that as a preference. On the merits this is
> the better attach point — at wrap there is a fresh as-built to diff and the findings seed the next
> session's step 0. So if/when the ritual is wired, the evidence points at `review-architecture` →
> **`/wrap-session`** (and `decompose-requirement` → a feature's "step 0"). Integration itself stays
> deferred; this just records *where* it would go. See `[[2026-06-02-architecture-review-post-m2s2]]` §6.
>
> **Refinement (2026-06-15, Session 23):** that "wrap" placement holds for *routine* sessions, but a
> **milestone-boundary** session whose first act is a `decompose-requirement` benefits from running
> `review-architecture` at **resume** — Session 23 did, and clearing the drift (DM5/label/snapshot) *first*
> is what let the M3.S4a decompose build on an honest vault. So the wiring evidence sharpens to:
> `review-architecture` → **`/wrap-session`** by default, **but at `/resume-session` when the session
> opens with a decompose** (and `decompose-requirement` → the feature's "step 0"). See
> `[[2026-06-15-architecture-review]]`.

---

## Raised by this vault (gaps the seed pass found)

### ~~OQ-1 — Two-store write consistency (Neo4j entity ↔ Postgres mention)~~ ✅ Resolved 2026-06-10
**Resolution** (owner, M2.S4 / PR #48): option **(c)** — write **Neo4j-then-Postgres** and **accept
eventual inconsistency** at PoC scale (single user, low volume, reversible); no reconciliation/outbox.
Per paragraph the `ExtractionCoordinator` writes all Neo4j (entities → relations) *then* the Postgres
`entity_mentions` row, so the mention (the resume checkpoint) lands only after every graph write
succeeds — a crash before it leaves the paragraph un-checkpointed and a re-run re-extracts it
(re-writing nodes, accepted under no-dedupe INV-8; M3 resolves duplicates). The remaining gap (a
store-down surfacing as a 500 rather than a typed status; the Neo4j driver created at import without a
lifespan close) is tracked as a `docs/PLAN_SHORT.md` cross-cutting follow-up. Original framing kept
below for history.

An entity's identity lives in Neo4j; its `entity_mentions` live in Postgres. The two stores
**cannot share a transaction**. *But what if* the Neo4j write succeeds and the Postgres
mention write fails (or vice versa)?
- **Options:** (a) write-Neo4j-then-Postgres with a reconciliation/repair pass on startup;
  (b) outbox pattern (record intent in one store, replay); (c) accept eventual inconsistency at
  PoC scale and add a "verify graph↔mentions" maintenance check.
- **My proposal:** (c) for the PoC (single user, low volume, reversible), with a cheap
  consistency check surfaced in the UI — but flag it as a real seam to revisit if it bites.
- **Lands in:** M2.S4 (first time both writes coexist). Open.
- **Now live + a trap (pre-M2.S4 sweep, 2026-06-09 — `[[2026-06-09-architecture-review]]`):** this is
  M2.S4's first owner call (confirm write-order Neo4j-then-Postgres + posture (c) before wiring).
  **Trap:** the Postgres `entity_mentions` table this seam assumes **does not exist in the migrations**
  — only spec §6.4 defines it (the M1 schema has projects/stories/chapters/scenes/paragraphs +
  llm_calls). M2.S4 must **create it in a new Alembic migration** (+ extend `EXPECTED_TABLES`), not
  inherit it. The `docs/PLAN_SHORT.md` handoff's "already in M1's schema, verify before re-migrating"
  was wrong and is **fixed there** (2026-06-09). Spec §6.4 is the authority and is correct.

### ~~OQ-2 — Ingest job partial-failure recovery~~ ✅ Resolved 2026-06-10
**Resolution** (owner, M2.S4 / PR #48): option **(a)** — per-paragraph idempotent-ish writes +
resume-from-last-done. The **batch driver** (`ExtractionCoordinator`), *not* the agent, owns the
`except BudgetExceededError | QuotaExhaustedError` catcher; on a mid-batch pause it stops and the
route returns **HTTP 202 + partial progress**, and a re-POST resumes from the first paragraph without
a committed `entity_mentions` row (the durable checkpoint). The single-paragraph `ExtractionAgent`
keeps *propagating* the pause-and-ask untouched (M2.S3 D5). Resume granularity is the paragraph;
a zero-entity paragraph writes no mention and is cheaply re-run on resume (never a duplicate node).
Original framing kept below for history.

*But what if* extraction dies halfway through a 50k-word story? Is the job resumable, or does
the user re-run from scratch? Is there an ingest-job state record at all, or only per-paragraph
side effects?
- **Options:** (a) per-paragraph idempotent writes + resume-from-last-done; (b) whole-story
  transaction-ish redo; (c) no recovery at PoC (re-upload).
- **My proposal:** (a), leaning on idempotency (see [[idempotency]]) — paragraphs already have
  stable ids. Needs the candidate/job state machines drawn (see [[overview]] Layer 5). Open.
- **Now concrete (post-M2.S2 sweep, 2026-06-02):** the `LLMRouter` already *raises*
  `BudgetExceededError` / `QuotaExhaustedError` mid-call (pause-and-ask), but **no caller catches it
  to make the batch resumable**. The proposal §7 "cap hit on call N of a 200-paragraph ingest → pause
  resumably" lands in **M2.S3/S4** when `ExtractionAgent` does batch dispatch — that is where the
  catcher + resume-from-last-done belongs. See `[[2026-06-02-architecture-review-post-m2s2]]`.
- **Decided in part (M2.S3, owner 2026-06-08):** `[[m2s3-extraction-agent]]` D5 — the agent stays
  **single-paragraph** and *propagates* the router's pause-and-ask (never swallows it). The resumable
  **batch driver + catcher land in M2.S4**, where the graph write + `entity_mentions` give a durable
  "last-done" checkpoint. The agent-level decision is made; OQ-2 stays open only for the M2.S4 batch
  driver itself.
- **Now live (pre-M2.S4 sweep, 2026-06-09 — `[[2026-06-09-architecture-review]]`):** the catcher is
  M2.S4's to build. Confirm the **batch driver** (not the agent) owns the `except
  BudgetExceededError`/`QuotaExhaustedError` → pause-resumably, using the persisted graph write +
  `entity_mentions` as the durable "last-done" anchor (see [[idempotency]]). Related: the new
  graph-write **API path must map the router's exit exceptions to HTTP** (502/402-style) — today
  `api/stories.py` catches only `ChunkingError`, so an exhausted router on the new path would 500.

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
- **Partly resolved (2026-06-15, M3.S4a / DM-S4a-5):** the *staging/rejection* Expiry instance is
  decided — **(a) no retention at PoC** for the `candidates` / `candidate_decisions` tables (rejected
  memory is a feature, not expired — DM-rej; unreviewed backlog is the only growth risk, bounded by the
  single author's ingest; age-based cleanup is the obvious V1 refinement). The broader station (uploaded
  files, LLM-prompt-log retention) stays open.

### OQ-5 — `ExtractionAgent` prompt-injection-by-structure pass
Before M2.S3 ships, confirm the extraction prompt renders structure **only** from the trusted
Jinja2 template and never reparses model output mixed with story text — the same class of
hardening already applied to `ChunkingAgent` and encoded in `/review-pr` §4.
- **Status:** not a decision so much as a **must-verify** gate for M2.S3. Tracked here so it is
  not forgotten. See [[overview]] Layer 7 (Security) and `[[m2s3-extraction-agent]]` Layer 7, which
  splits the gate into **structural** injection (closed by construction — `list[Message]` from the
  trusted template) vs **semantic** injection (bounded by conservative prompt + schema + M3 human
  review); the failing test must prove the structural guarantee. See [[prompt-injection]].

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

### ~~OQ-9 — `latency` is promised in three homes but recorded in none~~ ✅ Resolved 2026-06-11 → option (a)
**Resolved 2026-06-11 (option a); built M2.S5 (PR #51):** spec §6.6's enumeration lists `latency_ms`
(elapsed time around the provider call; recorded for every dispatched call, null only for a pre-dispatch
budget refusal that never reached a provider); the `llm_calls` column (Alembic
`2026_06_11_0956-…_add_latency_ms_to_llm_calls.py`) + the router capture **landed in M2.S5** and the
§8.5 panel shows it. `[[invariants]]` INV-5's latency caveat matches. Original framing kept below for
history.
Raised by the post-M2.S2 sweep (`[[2026-06-02-architecture-review-post-m2s2]]`). INV-5 says a usage
row records "… **(and latency)**"; the `[[m2s2-llm-router-budget-cap]]` proposal repeats it; the
**M2.S5 panel task** (`docs/PLAN_SHORT.md`) lists **latency** as a shown column. But the as-built
`llm_calls` table / `LlmCallRecord` record **no latency**, and spec §6.6's enumeration doesn't list
it either.
- **Options:** (a) add a `latency_ms` column + capture it in the router now (cheap; the S5 panel will
  want it); (b) trim INV-5 + the proposal to match spec + as-built (latency not recorded at PoC).
- **My proposal:** (a) — it's a one-column migration and the panel already promises it; capturing
  wall-clock around `provider.complete` is trivial and system-derived. Decide **before M2.S5**. Open.

### ~~OQ-10 — Malformed-`200`-envelope: record + fail over, don't crash~~ ✅ Closed in code 2026-06-08 (PR #42)
**Closed in code 2026-06-08 (PR #42)** (confirmed by the 2026-06-09 sweep —
`[[2026-06-09-architecture-review]]`): the typed `ProviderResponseError(RuntimeError)` is defined in
`adapters/llm/base.py`, raised by **both** adapters at the envelope-unwrap point (incl. the
null-`content` case the PR-#42 `/code-review` caught — `ollama.py`, `openrouter.py`), and caught by the
router (`router.py`) which records a failure row + fails over, exactly like a 5xx. INV-5 is now total
over the edges the router handles; INV-5's note still carries the stale "open gap" prose (a
recommended drift-fix, see the sweep Hand-off). Original framing kept below for history.
Raised by the post-M2.S2 sweep; predicted by the proposal §7. A provider returning `200` with a
broken body (missing `choices`/`message`, an error shaped as success, a proxy injecting JSON) raises
a parse error *inside* `provider.complete()`; the router catches `HTTPStatusError` + `RequestError`
but **not** this, so it neither records a row nor fails over.
- **Options:** (a) a typed `ProviderResponseError` the adapters raise on an unparseable envelope and
  the router treats like a 5xx (record failure, fail over); (b) leave as an uncaught 500 (status quo).
- **My proposal:** (a). Already tracked as a `docs/PLAN_SHORT.md` **M2.S3 cross-cutting** item; lands
  when the router first meets a real Pydantic schema. Distinguish **envelope-malformed → failover the
  provider** from **schema-invalid → retry the prompt** (the latter stays in the agent). Open.
- **Designed (M2.S3 decompose, 2026-06-02):** `[[m2s3-extraction-agent]]` D2 specifies a typed
  `ProviderResponseError(RuntimeError)` in `base.py`, raised by each adapter at the envelope-unwrap
  point, with a router `except` arm treating it like a 5xx (record failure, mark non-quota, fail over).
  Rejected (c) blanket `except Exception` (too broad — swallows programming errors, the PR-#36
  wrong-terminal class). This is a [[poison-message]]: quarantine-and-move-on, never retry the same dead
  provider. Open sub-q: whether the error carries a **redacted, truncated** body (must not log the key —
  INV-6 — and may contain story text — OQ-4). It also exposes a **spec §6.5 imprecision** (the router
  comment lumps "malformed response schema → retry the prompt"); see `[[m2s3-extraction-agent]]` G6.
- **Accepted (owner, 2026-06-08):** build the `ProviderResponseError` path **in M2.S3** (the
  "envelope-malformed vs schema-invalid" router test lands with it). The **spec §6.5 imprecision is
  fixed** — §6.5's router block + §6.5/§11 "Failover" paragraphs now split envelope-malformed
  (→ failover via `ProviderResponseError`) from schema-invalid (→ agent prompt-retry). OQ-10 stays open
  only until the code lands; the redacted-body question is an implementation detail (D2).

### ~~OQ-11 — `EntityCandidate` field: `candidate_name` (surface form) vs `canonical_name`~~ ✅ Resolved 2026-06-08
**Resolution** (`[[m2s3-extraction-agent]]` D1, owner): option **(a)** — the field is
`candidate_name: str` (surface form) with a non-empty validator; `canonical_name` (bilingual PL+EN) is
reserved for the resolved entity at merge time (M3). The plan's "canonical_name" wording is reconciled
to `candidate_name` when M2.S3 lands. Original framing kept below for history.

Raised by the M2.S3 decompose (`[[m2s3-extraction-agent]]` D1). The plan task says "validators for …
non-empty **canonical_name**", but spec Appendix C.2's output field is `candidate_name` ("as named in
the text") and §3.2's `canonical_name` is the *resolved, bilingual PL+EN* name assigned at **merge**
time (M3). At extraction time we have a surface mention, not a canonical name.
- **Options:** (a) field is `candidate_name: str`, non-empty validator; canonical naming is downstream
  (M3). (b) name it `canonical_name` per the plan wording.

### ~~OQ-12 — `evidence_quote` verification, dangling relations, and PreNER-hint timing (M2.S3)~~ ✅ Resolved 2026-06-08
**Resolution** (`[[m2s3-extraction-agent]]` G5 + D3, owner):
- **`evidence_quote`:** **soft-flag** — substring check (whitespace-normalised); if absent, flag/drop
  the quote but keep the candidate. *Rejected:* hard-reject (punishes legitimate paraphrase).
- **Dangling relation:** **accept** (open-world; M3 + human review resolve), optional soft validator
  flag — don't hard-reject.
- **PreNER hints:** wire the parameter but **defer injecting hints into the prompt** until a real eval
  exists (deterministic-first / no speculative features).

### OQ-13 — Backend dependency-advisory scan (continuous SCA) in CI
Raised by `decompose-requirement` 2026-06-08 (`[[backend-dependency-advisory-scan]]`). CI gates
dependency *freshness* (14-day soak) + a *pin-time* OSV check (`/add-dependency`), but **nothing
re-scans `backend/uv.lock`** against the advisory DB on later runs — so a vuln disclosed *after*
pinning is caught only by **Dependabot** (post-merge on `main`), never pre-merge by CI. Proven by
GHSA-86qp-5c8j-p5mr (`starlette` 1.0.0, MEDIUM, via `fastapi`): Dependabot flagged it, CI did not
(Trivy scans only Docker images). Add a continuous backend [[software-composition-analysis]] gate —
[[defense-in-depth]] *with* Dependabot, not a replacement.
- **Options:** tool — `osv-scanner` (reads `uv.lock` natively, same OSV DB as `/add-dependency`) vs
  `pip-audit` (PyPA, synced-env); gate — fail-on-**any** + scoped waivers vs HIGH/CRITICAL parity
  with `npm audit`.
- **✅ Register approved (owner, 2026-06-08):** the **G1–G7 cluster** — osv-scanner, fail-on-any +
  scoped waivers, §6.7 amendment to document the gate, reuse the Trivy waiver split (sibling
  `infra/osv/`), leave `npm audit` HIGH/CRITICAL, SHA-pin the scanner Action, §6.7 baseline control
  (no new INV), explicit `starlette==1.0.1` pin. See `[[backend-dependency-advisory-scan]]` §7 hand-off.
- **✅ Closed in code 2026-06-08 (PR #44)** (same posture OQ-10 held — closed when the code landed):
  built one branch — `osv-scanner` step vs `backend/uv.lock` (fail-on-any, scanner **digest-pinned**;
  the `google/osv-scanner-action` is a no-`runs:` stub, so the container is the fail-on-any path —
  stronger than the planned SHA-pin), `infra/osv/` waiver scaffold (no active waivers), `starlette`
  1.0.0→1.0.1 (self-test red→green), and the **spec §6.7 amendment landed *with* the build**.

### OQ-14 — §6.5 model-override dropdown vs INV-7 (system-derived routing)
Raised by the M2→M3 roll (2026-06-11, `[[2026-06-11-architecture-review]]`); deferred as a *feature*
in `docs/PLAN_SHORT.md` Decided 2026-06-11. The §8.5 panel does the **surfacing** half ("which
tier/model ran, and why"); the remaining half is a real **user model-override control + persisted
per-task-type preferences**. That collides head-on with **INV-7** as currently stated — routing is
**system-derived, never caller-asserted** (the near-miss deliberately closed in M2.S2: the ledger
records the router's *own* chosen tier/provider/model, ignoring any caller echo). A dropdown makes the
caller an authority on routing, which the invariant currently forbids.
- **What it needs (not what to decide — that's the owner's):** an **INV-7 reconciliation** ("routing
  is system-derived *unless* the user explicitly overrides for this task"), router plumbing for the
  override + its interaction with weight-tiering and within-tier failover, and a preferences store.
- **Likely a future ADR** — it amends an invariant + crosses the routing boundary. Frame it in the
  `[[m2s3-extraction-agent]]`-style decompose register before building; the human owns the INV-7 call.
- **Lands:** its own scoped piece, alongside or after M3 (carried in `docs/PLAN_SHORT.md`
  cross-cutting). *Rejected:* surfacing-only (the panel already covers it — near-zero value);
  cram-into-a-thin-session (rushes an invariant-touching feature). Open.

### OQ-15 — Operational logging is absent, so INV-6 "keys never logged" is vacuously true
Raised by the M2→M3 roll (2026-06-11, `[[2026-06-11-architecture-review]]`); recorded as a later need
in `docs/PLAN_LONG.md` (M2.S6, PR #53). The backend emits **no** operational/stdout logs today — so
INV-6's "API keys never logged" and "logging middleware strips `Authorization`/`X-API-Key`" describe a
**redaction guard that does not exist yet**: the guarantee holds *vacuously* (nothing logs ⇒ nothing
leaks), which proves nothing about whether it would hold once logging lands. A common conflation worth
nailing down: the future-training-data trail is the **`llm_calls` ledger + planned `edit_history`** (a
data-layer record), **not** stdout logs — they are different concerns.
- **The seam:** the moment the first operational log line is added (M3's matching/judge agents are a
  likely first place — a paused/failed cascade wants diagnostics), redaction must **precede** it, or
  it's fail-open-by-sequencing. The M2.S6 key-leak grep (`scripts/check_openrouter.py` + the
  `backend/AGENTS.md` procedure) becomes the **redaction regression guard** at that point.
- **Ties:** OQ-4 (Expiry — log retention) and INV-6. *Options to frame when logging is actually
  scoped:* (a) structured logging with a redaction processor built **with** the first log line;
  (b) no operational logging at PoC, documented, ledger-only. Open.

### ~~OQ-16 — M3 cascade decision register (DM1–DM7, DM-rej)~~ ✅ FULLY RESOLVED — DM1–DM6 + DM7 + DM-rej (recorded in `docs/PLAN_SHORT.md` Decided S23)
Raised by the M3 `decompose-requirement` step-0 (2026-06-11, `[[m3-cascade-matching]]`). The full
Context/Options/Proposal for each lives in that proposal's Decision register; listed here so the vault's
reader knows they exist and that they gated M3 code. **Resolved (authoritative in `docs/PLAN_SHORT.md`
Decided): DM6 (S19) + DM1–DM4 (S20) + DM5 (S22, via PR #60) + DM7/DM-rej (S23) — each took its proposal
below.** **DM7/DM-rej (owner 2026-06-15, recorded PLAN_SHORT Decided S23):** **DM7 → INV-2 consent gate
DEFERRED past M3** (the review queue is *not* its landing target; keyboard scheme is an S4b-time pick);
**DM-rej → remember rejections**. **M3.S4 re-sliced → S4a (backend write-path/cascade/INV-flip/ADR 0004) + S4b (UI).**
- **DM1 — threshold home** (the §3.3 Policy values: Stage 1 85/60, Stage 2 cosine 0.85, Stage 3 conf 0.8
  have no home today). *Proposal:* a named `matching` config module, spec defaults, not user-facing yet.
- **DM2 — embedding model** (`paraphrase-multilingual-mpnet-base-v2`, 768-dim — matches the reserved
  `vector(768)`; `verify-at-build` the dim + host fit; pin via the §6.7 wheel/model channel).
- **DM3 — what an entity's vector *is*** (per-mention vectors + max-cosine vs a per-entity representative).
- **DM4 — embedding storage + the `NULL AS embedding` → `vector(768)` read-path switch** (`pgvector` +
  `register_vector_async`; *proposal:* on `entity_mentions`).
- **~~DM5 — JudgeAgent tier~~ ✅ Resolved (S22, PR #60):** cloud_free via the router,
  `task_type="judge"`, weight `medium` (the label is `"judge"`, not `"judging"`).
- **DM6 — THE central fork: matching *gates* the graph write (intercept-before-write) vs *dedupes after*
  it.** *Strong proposal:* (A) intercept-before-write — it's what INV-1 + §3.3 demand; cost = refactor
  M2.S4's write path. Determines whether **INV-8 is replaced or layered**. The owner's biggest M3 call.
- **~~DM7 — review-queue UX~~ ✅ Resolved (owner, 2026-06-15):** build the §3.3 Stage-4 elements +
  keyboard nav in S4b; **INV-2's consent gate is DEFERRED past M3** (not landed in the queue —
  persona-justified, single local user/full trust); keyboard scheme is an S4b-time pick. *(Recorded:
  `docs/PLAN_SHORT.md` Decided S23.)*
- **~~DM-rej — rejected-candidate memory~~ ✅ Resolved (owner, 2026-06-15):** **remember rejections** —
  the `rejected` terminal edge writes an evidence row the matcher consults before re-queueing (ties
  OQ-4 Expiry; adds a per-candidate store read — see `[[2026-06-15-architecture-review]]` §C). *(Recorded:
  `docs/PLAN_SHORT.md` Decided S23.)*
- **Also live:** spec §10 q8 (multilingual `canonical_name_pl/en`) becomes concrete at merge — stays the
  **spec's** to resolve. **Lands in:** M3.S1 = Stage 1 RapidFuzz ✅ (PR #56); M3.S2 = Stage 2 embeddings
  + the pgvector switch (DM2–DM4); M3.S3 = JudgeAgent (DM5); M3.S4 = review queue + the DM6 write-path
  refactor / INV-8 retirement (DM7/DM-rej).

### ~~OQ-17 — M3.S4a write-path build-detail register (DM-S4a-1..5)~~ ✅ RESOLVED 2026-06-15 (S23, owner — each as proposed)
Raised by the M3.S4a `decompose-requirement` step-0 (2026-06-15, `[[m3s4a-intercept-write-path]]`) and
**resolved the same session** (authoritative in `docs/PLAN_SHORT.md` Decided 2026-06-15 S23). The full
Context/Options for each lives in that proposal's register; listed here so the vault's reader knows they
gated the S4a build (the backend write-path refactor that retires INV-8 / lands INV-1's enforcer).
- ~~**DM-S4a-1 — staging store shape.**~~ ✅ a new Postgres **`candidates`** table (name/type/props/
  context/`vector(768)` + proposal/target/reasoning/alternatives/status). `verify-at-build` the vector
  index choice (ivfflat vs hnsw).
- ~~**DM-S4a-2 — add INV-9**~~ ✅ **yes** — add INV-9 ("no automated stage writes the graph"), the greppable
  structural rule the INV-1 human-commit guard doesn't itself state.
- ~~**DM-S4a-3 — resume checkpoint under staging**~~ ✅ "done = candidates staged" + a zero-candidate
  marker (mentions move to accept-time, so M2.S4's `entity_mentions` checkpoint no longer holds); idempotent re-stage.
- ~~**DM-S4a-4 — evidence/audit home for accept/reject**~~ ✅ a focused append-only **`candidate_decisions`**
  table now; **defer** the full §4.2 `edit_history` (text-edit dataset) to the editing milestone.
  `verify-at-build` §4.2's intended columns before naming, to avoid a future collision. (Touches the §4.2/§11
  training-dataset asset → ADR 0004 territory.)
- ~~**DM-S4a-5 — staging/rejection retention** (Expiry; ties **OQ-4**).~~ ✅ (a) no retention at PoC,
  documented — rejected memory is a feature (don't expire), unreviewed backlog is the only growth risk.
- **Plus:** **ADR 0004** (DM6 intercept-before-write, fuller MADR, test-first); the **§3.4 graph-endpoint
  scoping** (story-vs-project) the S4b viewer needs. **Lands in:** M3.S4a (backend), then M3.S4b (UI).

### ~~OQ-18 — M3.S4c intra-batch-dedup decision register (DM-S4c-1..6)~~ ✅ RESOLVED 2026-06-15 (Session 25, owner)
Raised by the M3.S4c `decompose-requirement` step-0 (2026-06-15, `[[m3s4c-intra-batch-rematch]]`),
triggered by the browser walk: a single first-pass extraction stages duplicates (`Janek` ×3) the
review queue can't merge → duplicate Neo4j nodes, undercutting §9 M3's "the graph is clean".
**Resolved same session (authoritative in `docs/PLAN_SHORT.md` Decided/Blocked S25):**
- ~~DM-S4c-1 — slice~~ ✅ **S4c** (on-accept live re-match, *backend-only*) + **S4d** (manual handpick).
- ~~DM-S4c-2 — trigger & scope~~ ✅ synchronous-in-accept + incremental (`O(pending)`).
- ~~DM-S4c-3 — auto-flip strength~~ ✅ **Stage 1 `>85%` OR Stage 2 `cosine >0.85`** (owner chose
  +Stage-2 over the proposed Stage-1-only); **no live Stage-3 judge** ([[prefer-deterministic]]).
- ~~DM-S4c-4 — monotone re-proposal~~ ✅ yes ([[idempotency|idempotent]]); kept as the transition
  **guard**, **INV-10 not minted**.
- ~~DM-S4c-5 — handpick scope~~ ✅ **project-scoped** (§6.4 key); **supersedes** the deferred
  "arbitrary-entity search merge target" cross-cutting (now M3.S4d).
- ~~DM-S4c-6 — handpick endpoint~~ ✅ `GET /stories/{id}/entities?q=` over Neo4j accepted entities via
  `accepted_entity_reader`.
- **Ripples:** `[[candidate-lifecycle]]` gains a `review-queued → review-queued` self-loop (monotone
  guard) — folded **on the S4c code, test-first**; **INV-1/INV-9 hold** (re-match writes the staging
  table, never the graph) + a one-line INV-9 graph-vs-staging clarification on build. **Spec §3.3
  amended** (on-accept re-match + handpick). **Relation-write stays deferred** but its priority rose
  (merges orphan relations). **ADR 0005 — declined at build (owner, S4c, 2026-06-15):** re-match is a
  contained change (staging-only, INV-9 holds) already fully recorded in the proposal + spec §3.3, so
  the rationale lives in `docs/PLAN_SHORT.md` Decided + the INV-9 graph-vs-staging clarification rather
  than a separate decision file.

### ~~OQ-19 — M3 relation-write decision register (DM-Rel-1..7) + the empty relation stations~~ ✅ Resolved 2026-06-16 (Session 29)
**Resolved — built in M3.S4e; recorded in `docs/decisions/0005` + `[[m3-relation-write]]` (now `accepted`)
+ `[[invariants]]` INV-1/INV-9.** DM-Rel-1 = the **explicit human gate** (owner); DM-Rel-2/4/5/6/7
confirmed at build as the architect proposed (the S4a pattern); INV-1 **broadened** (not INV-10 minted) to
cover edges; the create-id derivation promoted to `domain.candidates.committed_entity_id` (the DM-Rel-2
drift fix). The Evidence station is filled by `staged_relations`; the **Expiry** station (a held relation
never expires) is an accepted none-at-PoC gap (ADR 0005). Carried follow-up: **per-mention provenance for
triple-deduped edges** (post-PoC). Original register below, struck, for history.

Raised by the M3 relation-write `decompose-requirement` step-0 (2026-06-16, `[[m3-relation-write]]`).
Entity dedupe (S4a–S4d) is done, but **no code writes graph edges** — a merge orphans a candidate's
staged relations, so §9 M3's "the graph is clean" is not yet met for relations. The owner framed this as
an **M3 slice** (2026-06-16), not an M3→M4 roll. Full Context/Options for each entry live in the proposal's register.
- ~~**DM-Rel-1 — the human gate for relations (the central call):**~~ ✅ **Resolved (owner, 2026-06-16):
  an EXPLICIT human gate** — the §3.3 5th action ("decide on relations"), *not* auto-write and *not* the
  hybrid; **slice split backend-now (S4e) / UI-next (S4f)**. *Considered & rejected:* auto-write-on-both-
  endpoints-accepted (commits a hallucinated predicate/direction even when both nodes are right); hybrid
  bulk-confirm (kept as a fallback). Remaining: broaden INV-1 vs mint **INV-10** — build-time, test-first.
- **DM-Rel-2 — endpoint resolution:** surface string → same-paragraph candidate → its *committed* entity
  id (`created` → deterministic create-id; `merged` → `target_entity_id`). Match rule (exact / normalised /
  fuzzy) + where the id is read. `verify-at-build`: the create-id derivation couples to
  `CandidateReviewService._ACCEPT_NS` — promote to a shared helper?
- **DM-Rel-3 — when the edge-write fires:** on-accept sweep (mirrors `_maybe_rematch`) vs an explicit
  finalize endpoint vs end-of-review batch. Down to DM-Rel-1.
- **DM-Rel-4 — staged-relation persistence + evidence:** a `staged_relations` table (status lifecycle +
  idempotency + audit) vs the current inert JSONB blob on `paragraph_processed`; and the **relation
  evidence home** (`candidate_decisions` is entity-keyed → INV-3 reversibility for edges has no row). The
  **Evidence** and **Expiry** stations are empty/weak for relations — mirrored here.
- **DM-Rel-5 — re-point boundary:** confirm **M3 writes, M4 re-points** (an accepted-entity↔entity merge,
  which doesn't exist in M3, is the only true re-point case). Records a deferred edge, not a build task.
- **DM-Rel-6 — idempotent edge write (must-fix regardless):** `create_relation` uses `CREATE`, so a
  retried accept **doubles** the edge; needs a deterministic edge id + `MERGE`-on-id (the entity-path
  pattern). Only the id-derivation is open.
- **DM-Rel-7 — dangling-to-known endpoints:** a relation endpoint naming a known accepted entity not
  re-extracted this paragraph — resolve against the accepted graph, hold, or surface for manual binding?
- **Vault hygiene flagged:** the **INDEX priority queue is stale** — "Next steps" framed S4c as next
  though S4c/S4d shipped; a fuller **`review-architecture` re-sync** (a dated post-S4d/S4e as-built
  snapshot) is **overdue** at this milestone boundary. **S4e backend shipped 2026-06-16** (this register
  resolved); **S4f UI** remains the next relation slice.

### ~~OQ-20 — The relation lifecycle has no state-machine note (the node/edge model asymmetry)~~ ✅ Resolved 2026-06-18
**Resolved 2026-06-18 (vault maintenance pass):** the edge twin is drawn —
**`[[relation-lifecycle]]`** models the `staged → held|committable → written|rejected` machine as built
in `RelationReviewService` (the re-resolve-at-commit [[toctou]] guard, the idempotent-by-edge-id effect,
the held/committable derived-view asymmetry vs the persisted `staged` status, INV-1/INV-9 broadened to
edges). The node/edge model asymmetry is closed; INDEX now names the note (no longer an "Awaiting
content" gap). **The two sub-gaps stay tracked, not vanished — carried as watch-items in
`[[relation-lifecycle]]` "Open points":** **(a) held-relation visibility** — a never-committable relation
rests in `held` *silently* (the decide-relations surface lists only committable rows), so it is an
invisible non-decision with no Evidence row (INV-3 for edges has no home); **(b) edge Expiry** — held
rows never expire, the accepted none-at-PoC posture (ADR 0005, the edge twin of OQ-4 / DM-S4a-5).
Original framing kept below for history.

Raised by the M3→M4 roll sweep (2026-06-17, `[[2026-06-17-architecture-review]]`). S4e/S4f shipped a
genuine relation lifecycle in code — a `staged_relations` row rests in **held** (an endpoint never
accepted, or a post-merge self-loop → never committable, no fuzzy fallback), **committable** (both
endpoints resolve to committed ids), or the terminals **written** / **rejected**, with a re-resolve-at-
commit [[toctou]] guard and an idempotent-by-edge-id effect. That is a [[state-machine]], and its entity
twin [[candidate-lifecycle]] has had a drawn note since S4a — the edge twin has none, and INDEX's
"Awaiting content" doesn't even name it as a gap.
- **What it needs (not a decision — a drawing task):** a `state-machines/relation-lifecycle.md` modelling
  the states/transitions/guards/effects above, so the symmetric edge gate is projected the way the node
  gate is. A `decompose`/drawing pass owns it (a `review` is report-only). Two sub-gaps to fold while
  drawing: (a) **held-relation visibility** — does the author ever learn *why* an extracted relation never
  became an edge, or is a held row an invisible non-decision? (ties INV-3 Evidence for edges); (b) confirm
  the **edge Expiry** posture (held rows never expire — accepted none-at-PoC, ADR 0005, same as OQ-4).
- **Lands:** naturally at the M4 step-0 decompose, or as a standalone drawing pass. Open.

### OQ-21 — M4 inline-highlights decision register (DM-IH-1..8) — ⚠ mostly resolved 2026-06-18
**Mostly resolved 2026-06-18 (owner, Session 32; resolved home = `[[m4-inline-highlights]]` now
`accepted`).** **DM-IH-1/2/3/4/7/8 resolved-as-built** (backend, PR #81): DM-IH-1 = render-time string
search over `canonical_name` + aliases (*verify-first* found persist-spans illusory — null offsets, spaCy
span gone at accept); DM-IH-2 = a new story-scoped `GET /stories/{id}/reader` (the §3.4 per-story filter's
first home); DM-IH-3 = plain `<mark>` renderer, NOT Tiptap (Tiptap with manual annotation); DM-IH-4 =
longest-match; DM-IH-7 = accepted-only (read-side echo of INV-1); DM-IH-8 = tooltip name+type+aliases.
**DM-IH-5 (colour palette) + DM-IH-6 (perf/virtualise) remain confirm-at-build in the M4.S1 FRONTEND
slice** (open-but-narrowed). Read the per-entry resolutions in `[[m4-inline-highlights]]`. Original
framing kept below for history.

Raised by the M4 first-slice `decompose-requirement` step-0 (2026-06-17, `[[m4-inline-highlights]]`).
Full Context/Options/Proposal for each live in that proposal's register; listed here so the vault's
reader knows they gate the M4.S1 build. **The central one is DM-IH-1** (span resolution): accepted
`entity_mentions` carry **null char offsets** (the LLM path stores an evidence quote, not offsets; the
spaCy `CandidateSpan` that has offsets is discarded at accept), so highlighting is first a
*where-does-this-entity-sit* problem, not a render of known spans. Register, all **OPEN**:
- **DM-IH-1 — span resolution** (render-time string search vs persist real spans + backfill vs hybrid).
  My proposal: hybrid as two sub-slices — ship render-time search first (no backend change), measure
  its hit-rate on the real corpus, add span persistence only if needed. **`verify-at-build`:** does the
  stored `evidence_quote` reliably substring-match `raw_text` (it's a soft-flag), and is the spaCy span
  still available at accept time to persist? Inflection (PL) is the headline gap.
- **DM-IH-2 — backend read shape** (a new `GET /stories/{id}/reader` doing the cross-store join +
  resolution, story-scoped — may be the first home of the §3.4 per-story filter).
- **DM-IH-3 — render surface** (a plain read-only `<mark>` renderer now vs adopting Tiptap/ProseMirror
  decorations now so the next slices inherit it).
- **DM-IH-4 — overlap/nesting arbitration** (longest-match wins, proposed).
- **DM-IH-5 — colour-by-type under the open-world type set** (fixed palette for common types +
  deterministic hash fallback — honours INV-4; *rejected:* a fixed enum map).
- **DM-IH-6 — whole-story render vs virtualise** (measure on a real 50k draft first).
- **DM-IH-7 — highlight accepted-only** (the read-side echo of INV-1; *rejected:* preview staged).
- **DM-IH-8 — tooltip "brief description"** (name+type+aliases now; richer description is the
  side-panel slice's job; *rejected:* an LLM-generated summary in a read-only slice).
- **Latent coupling surfaced (not this slice's fix):** a future M4 entity↔entity merge must re-point
  `entity_mentions.entity_id` (and written edges — DM-Rel-5) onto the survivor, or the reader silently
  drops those highlights. Ties the cross-cutting re-point item. **Lands in:** M4.S1 (the first M4 slice).

### OQ-22 — M4.S2 entity-side-panel decision register (DM-SP-1..8) — ✅ FULLY RESOLVED (DM-SP-1..3/5..8 Session 34; DM-SP-4 = cytoscape, Session 35 build)
**Resolved 2026-06-18 (owner, Session 34; resolved home = `[[m4-side-panel]]` now `accepted` +
`docs/PLAN_SHORT.md` Decided S34).** **DM-SP-1 = a focused per-entity endpoint** `GET …/entities/{eid}`
(BFF) → **DM-SP-7 = split** S2a backend / S2b frontend; **DM-SP-2 = strict 1-hop ego-graph**;
**DM-SP-3 = occurrences from rendered highlights** (+ scroll/flash, doubles as the timeline); **DM-SP-5
= `properties` from the endpoint** (read-only key→value); **DM-SP-6 = a new reader panel** (not unified
with `NodeDetailsPanel`); **DM-SP-8 = confirm** (occurrences story-scoped, neighbourhood project-scoped).
**DM-SP-4 (mini-graph render: cytoscape-reuse vs static) ✅ resolved at S2b build (Session 35, PR #91)
= reuse cytoscape** (`EgoGraphCanvas`), browser-verified in the narrow panel; static fallback unneeded.
Read the per-entry resolutions in `[[m4-side-panel]]`. Original framing kept below for history.

Raised by the M4.S2 first-slice `decompose-requirement` step-0 (2026-06-18, `[[m4-side-panel]]`).
Owner picked **side panel** as M4.S2 (over manual-correction-in-reader) — the read-only inspection
surface that the *next* slice's corrections build on. Full Context/Options/Proposal for each entry
live in that proposal's register; listed here so the vault's reader knows they gate the M4.S2 build.
Still a **read-only projection** (INV-1/3/9 untouched, no LLM/INV-5; the read-side echo of INV-1
applies as in `[[m4-inline-highlights]]`). Register, all **OPEN**:
- **DM-SP-1 — where the panel's data comes from** (the central call): a focused per-entity endpoint
  `GET /stories/{id}/entities/{eid}` (BFF — server-side join + neighbourhood, fetch-per-click; needs a
  new 1-hop `Neo4jRepo` query) vs composing client-side (`useStoryGraph` whole-graph + reader
  highlights + add `properties` to `GraphNode`). `properties` is the **one** §3.4 field surfaced by no
  endpoint today. My lean: the focused endpoint (mirrors DM-IH-2).
- **DM-SP-2 — ego-graph radius** ("local graph around that entity", §3.5): strict 1-hop entity-incident
  (proposed, legible) vs 1-hop+inter-neighbour edges vs configurable depth. See [[ego-graph]].
- **DM-SP-3 — occurrence drill-down + granularity**: occurrences driven off the *rendered highlights*
  (panel agrees with the prose; doubles as §3.4's timeline) vs raw paragraph-level mentions; click →
  scroll-to-paragraph + flash. The DM-IH-1 granularity mismatch (more highlights than mentions) recurs.
- **DM-SP-4 — mini-graph render**: reuse `GraphCanvas`/cytoscape with the ego subset vs a lightweight
  static view in a narrow panel (`verify-at-build` the embedded-cytoscape layout).
- **DM-SP-5 — `properties` display** (read-only key→value, open-world; editing is the next slice).
- **DM-SP-6 — panel component**: a new `ReaderEntityPanel` (proposed; the two panels diverge) vs
  extending the graph viewer's `NodeDetailsPanel` into one shared panel.
- **DM-SP-7 — slice size**: split M4.S2a backend (endpoint + 1-hop query) / M4.S2b frontend (panel +
  mini-graph + drill-down) — *downstream of DM-SP-1* (1a→split, 1b→likely one slice).
- **DM-SP-8 — story-vs-project scoping** (confirm, not fork): occurrences story-scoped, neighbourhood
  project-scoped — inherits the §3.4 debt the reader endpoint first carried.
- **Latent coupling re-surfaced (not this slice's fix):** a future M4 entity↔entity merge must
  re-point written **edges** (DM-Rel-5 — [[relation-lifecycle]]) and `entity_mentions.entity_id`
  (M4.S1), or the ego-graph draws an edge to a ghost node / the panel drops an occurrence. This slice
  fail-closes (omit the dangling neighbour); it makes the re-point debt concrete from the relations
  direction. **Lands in:** M4.S2 (the second M4 slice).

### OQ-23 — M4.S3a entity-&-relation editing decision register (DM-S3a-1..8) — ✅ RESOLVED 2026-06-19
**Resolved 2026-06-19 (owner; resolved home = `[[m4-entity-editing]]` now `accepted` + `docs/PLAN_SHORT.md`
Decided).** DM-S3a-1 = **new named edit handlers + reword INV-9** "exactly two writers" → "only
human-reached handlers" (ADR-0005 precedent; ADR drafted at build); DM-S3a-2 = **a before→after edit-evidence
log** (INV-3 undo + flywheel); DM-S3a-3 = manual adds *intended* through the decide path but
**resolved-at-build to a direct edge-writer** (M4.S3a-be, ADR 0006 — the decide path is
surface-name/paragraph-keyed, which a hand-picked edge lacks; INV-9 broadens for edges too),
re-predicate = delete+re-add, duplicate-add surfaces a collision flag, allow self-loops; DM-S3a-4 = invalidate-on-edit
(rename re-highlights free); DM-S3a-5 = **typed `properties` values** (keys free, INV-4); DM-S3a-6 =
**last-write-wins** at PoC ([[lost-update]] named); DM-S3a-7 = **split** S3a-be/S3a-fe; DM-S3a-8 = reuse
`search_entities_route`. Read the per-entry resolutions in `[[m4-entity-editing]]`. Original framing kept
below for history.

Raised by the M4.S3a first-write-slice `decompose-requirement` step-0 (2026-06-19, `[[m4-entity-editing]]`).
Owner-confirmed scope (this session): from the read-only side panel ([[m4-side-panel]], shipped), make
the inspected entity **editable** — its scalar fields (`canonical_name`, `aliases`, `type`) + `properties`,
and **add / re-predicate / remove** relations between two already-accepted entities. This is the **first
M4 slice that *writes* the graph**, so most stations flip from the read view's `n/a` to live, and the
weight is on the write path + reversibility, not the UI. Full Context/Options/Proposal per entry live in
the proposal's register; listed here so the vault's reader knows they gate the M4.S3a build. Register, all
**OPEN**:
- **DM-S3a-1 — the write path + the INV-9 rewording** (the central call): new, explicitly-named edit
  handlers (`PATCH …/entities/{eid}` + relation edit ops, a [[backend-for-frontend]] *write* endpoint;
  my lean) vs overloading the existing review services. Either way **INV-9's "exactly two writers" is
  *reworded* to "only human-reached handlers — accept, decide, edit"** (the property unchanged; the
  enumeration grows — the relation-write/ADR-0005 broadening precedent, not a new INV-10).
- **DM-S3a-2 — reversibility & the edit-evidence record (INV-3)** (the load-bearing call): a minimal
  append-only before→after graph-edit log (the graph-edit twin of `candidate_decisions`; my lean, also
  flywheel substrate) vs an explicit "no undo / no before-image at PoC" INV-3-narrowing. The biggest
  slice-size lever.
- **DM-S3a-3 — relation add/re-predicate/remove mechanics**: route a manual add through the existing
  decide path to keep `RelationReviewService` the **sole edge-writer** (my lean) vs direct
  `create_relation`/`delete_relation`. Re-predicate is **delete+re-add** (edge id =
  `uuid5(subject_id, predicate, object_id)`); a re-add colliding with an existing predicate **silently
  MERGE-dedups** (warn?); manual **self-loop** allow-vs-reject.
- **DM-S3a-4 — field edits ripple into the read views**: invalidate reader catalog + entity-detail +
  graph on edit (confirm). Teachable payoff — DM-IH-1 render-time search means a corrected name
  **re-highlights for free**, no span migration; flip side — a name not in the prose stops highlighting.
- **DM-S3a-5 — open-world `properties` editing**: typed key/value (my lean, true to §3.2) vs string-only,
  backend-validated, keys free (INV-4 — never a fixed schema).
- **DM-S3a-6 — concurrency**: last-write-wins at PoC (my lean; the [[lost-update]] anomaly *named and
  accepted* for one local author) vs optimistic concurrency (version/etag → 409).
- **DM-S3a-7 — slice size**: split **M4.S3a-be** (mutators + edit service + evidence + endpoints) /
  **M4.S3a-fe** (panel edit affordances + picker + hooks), mirroring S2a/S2b (my lean) vs one slice.
- **DM-S3a-8 — entity-picker for add-relation**: reuse the project-scoped `search_entities_route`
  (`GET …/entities?q=`, built for M3.S4d handpick) — confirm-only.
- **Seam to later slices (not this slice's to fix):** entity↔entity **merge** + the **DM-Rel-5**
  written-edge & `entity_mentions.entity_id` re-point + **whole-entity delete** + **undo-merge** are
  **S3b**; manual **tag** from selection / **un-tag** / **change boundaries** (reopening DM-IH-1 span
  storage) are **S3c**; general **split** + relation temporal/source qualifiers are post-PoC
  (`docs/BACKLOG.md`).

### OQ-24 — M4.S3b forward "what if" (inputs to the coming decompose, not yet a register)
Raised by the 2026-06-20 pre-S3b re-sync sweep (`[[2026-06-20-architecture-review]]` §6). M4.S3b
(entity↔entity **merge** + DM-Rel-5 written-edge re-point + `entity_mentions.entity_id` re-point +
DM-Rel-6 idempotency + whole-entity **delete** + **undo**) is **unscoped** — its first task is the
step-0 `decompose-requirement`, which will mint the **DM-S3b register**. These are not framed
decisions to resolve here; they are the edge cases the decompose must take as input (tracked here so
`/resume-session` step 3c finds the report's forward findings homed):
- **Compound-undo before-image granularity (the centre of gravity).** The S3a `graph_edits` log is
  *per-edit*; a merge is **one action, N writes** (re-point every edge incident to B — each a
  delete+recreate, since `relation_edge_id = uuid5(subject,predicate,object)` changes when an endpoint
  id changes — re-point `entity_mentions`, fold aliases/properties, delete B). Undo-merge must reverse
  all of it atomically → the before-image needs **grouping** (a merge id over child rows / a
  compensating-transaction shape), not a flat per-row log. The decompose must decide the schema/contract.
- **MERGE-collision on edge re-point** silently folds two edges into one (the `uuid5` hazard DM-S3a-3
  surfaced for re-predicate, now on a *merge*) — surface or accept, and record enough to undo.
- **`entity_mentions.entity_id` re-point** is the cross-store (Neo4j + Postgres) half (OQ-1 on the write
  side) — order it retryable so a crash is never a half-merge; or the reader drops B's highlights.
- **Whole-entity delete vs dangling references** ([[referential-integrity]], fail-closed) — refuse-or-
  cascade against incident edges + mentions; the S3a "no ghost write (404/409)" posture is the read of it.
- **Carry, don't reopen:** held-relation visibility + edge Expiry ([[relation-lifecycle]] Open points
  a/b) — a merge/delete touches both; the "reject/merge prunes now-impossible held relations" rule
  (ADR 0005) is the natural home. **Lands:** the M4.S3b step-0 decompose. **→ Now framed as the
  DM-S3b register (OQ-25 below); this OQ-24 was the pre-decompose forward note, superseded by it.**

### ~~OQ-25 — M4.S3b merge/delete/undo decision register (DM-S3b-1..8)~~ ✅ RESOLVED 2026-06-20
**Resolved 2026-06-20 (owner; resolved home = `[[m4-s3b-graph-mutations]]` now `accepted` +
`docs/PLAN_SHORT.md` Decided).** DM-S3b-1 = **general undo** via a grouped append-only `graph_edits`
log (a [[compensating-transaction]]; resolves §10 q2 as "append-only log of changes, executed") **+ the
owner's added requirement that undo *show what it will reverse*** (each operation carries a
human-readable description; the affordance previews + confirms); DM-S3b-2 = **author picks survivor +
resolves property conflicts by hand** (owner chose this over my survivor-wins lean — enlarges the merge
surface); DM-S3b-3 = re-point all incident edges, **report** MERGE-collisions, drop post-merge
self-loops; DM-S3b-4 = Neo4j-then-Postgres-then-evidence, idempotent re-run; DM-S3b-5 = **real
`DETACH DELETE` + full-snapshot undo** (not soft); DM-S3b-6 = **split be/fe**, be1/be2 fallback now
likely; DM-S3b-7 = INV-9 enumeration unchanged, INV-3 now *executed*, none-at-PoC Expiry + a noted undo
depth-cap, **ADR 0007** at build; DM-S3b-8 = `POST …/entities/{eid}/merge` / `DELETE …/entities/{eid}` /
`POST …/graph-edits/undo`. **Spec amended 2026-06-20 (owner-approved wording): §3.4 (merge + delete in
the detail panel) + §10 q2 (undo = append-only log of graph changes).** §3.5 left untouched — its
right-click is *mention*-level un-tagging (S3c), not whole-entity delete (the decompose's "delete →
§3.5" was corrected to §3.4 at sign-off). Read the per-entry
resolutions in `[[m4-s3b-graph-mutations]]`. Original framing kept below for history.

Raised by the M4.S3b step-0 `decompose-requirement` (2026-06-20, `[[m4-s3b-graph-mutations]]`).
The first slice that **re-points already-written graph state** (entity↔entity merge + DM-Rel-5/6 edge
re-point + `entity_mentions` re-point) and the first to **execute** INV-3 reversibility (undo, not just
its S3a substrate). Full Context/Options/Proposal per entry live in the proposal's register; listed
here so the vault's reader knows they gate the M4.S3b build. **The central one is DM-S3b-1** (undo scope
+ the `graph_edits` grouping — a merge is one action, N writes; the per-row S3a log can't group it).
Register, all **OPEN**:
- **DM-S3b-1 — undo scope + `graph_edits` grouping** (the central call; ties §10 q2): undo-merge-only vs
  **general undo via a grouped append-only log** (my lean — add `operation_id`, a read path, a uniform
  inverse-replay; the [[compensating-transaction]] pattern) vs full versioning. `verify-at-build` each
  op's inverse round-trips.
- **DM-S3b-2 — merge consolidation semantics** (spec-silent → likely a **§3.4 amendment**): survivor
  selection (author-picks, my lean), alias union, property reconciliation (survivor-wins + record
  discarded, my lean).
- **DM-S3b-3 — edge re-point on merge** (DM-Rel-5/6 executed): re-point each incident edge
  (delete-old+create-new, id is `uuid5`-derived); MERGE-collision **fold + report count** (my lean);
  drop post-merge self-loops.
- **DM-S3b-4 — mention re-point** (cross-store, OQ-1 write side): `UPDATE entity_mentions SET entity_id`;
  Neo4j-then-Postgres-then-evidence, idempotent re-run (my lean). `verify-at-build` the crash-retryable order.
- **DM-S3b-5 — whole-entity delete** (spec-silent): hard `DETACH DELETE` + full-snapshot undo (my lean)
  vs soft/tombstone.
- **DM-S3b-6 — slice split**: be/fe (my lean), with a pre-authorised be1(merge)/be2(delete+undo) fallback.
- **DM-S3b-7 — invariants/Expiry/ADR**: INV-9 enumeration likely unchanged (ops live in
  `EntityEditService`); INV-3 now *executed*; `graph_edits` unbounded = none-at-PoC + a noted depth cap;
  **ADR 0007** (merge/delete/undo contract + §10-q2 resolution) at build on confirmation.
- **DM-S3b-8 — endpoint shapes**: `POST …/entities/{eid}/merge`, `DELETE …/entities/{eid}`,
  `POST …/graph-edits/undo`.
- **Spec-silence to resolve first (stop-and-amend):** §3.4/§3.5 (merge + delete semantics), §10 q2
  (undo = append-only log). **Lands:** M4.S3b, after the owner resolves the register. Open.

### OQ-26 — M4.S3c manual-tagging decision register (DM-S3c-1..9) — ✅ RESOLVED 2026-06-22 (Session 44, owner)
**Resolved 2026-06-22 (owner; resolved home = `[[m4-s3c-manual-tagging]]` now `accepted` +
`docs/PLAN_SHORT.md` Decided S44).** DM-S3c-1 = **(B) overlay / "save only what you touch"** (keep
render-time search; manual tags = stored spans that overlay+win; rejected highlight = a suppression the
resolver subtracts; change-boundaries materializes one occurrence — incremental [[materialization]], no
backfill); DM-S3c-2 = **both attach-existing + create-new-entity** (new human-reached writer, INV-9 grows);
DM-S3c-3 = occurrence-level (not-an-entity suppresses; not-this-entity suppresses + optional atomic
re-tag); DM-S3c-4 = materialize-then-edit; DM-S3c-5 = **tag/un-tag/boundary ride the S3b `graph_edits`
undo** (new op-kinds + inverters, contract-tested from writer output); DM-S3c-6 = add
`source`+`mention_id` to `ReaderHighlight`; **DM-S3c-7 = ADOPT TIPTAP NOW (owner override of my native-
selection lean** — pay the editor setup so V2 editing inherits it; `/add-dependency` at fe build);
DM-S3c-8 = split be/fe; DM-S3c-9 = **no §3.5 capability amendment** (S3a precedent), storage model +
INV-9 reword in **ADR 0008** at build, a small §6.4 data-model note via stop-and-amend if the migration
needs it. **Next: build M4.S3c-be test-first from the pure reconciling-resolver function.** Original
framing kept below for history.

Raised by the M4.S3c step-0 `decompose-requirement` (2026-06-22, `[[m4-s3c-manual-tagging]]`). The
**final slice** of "manual correction in the reader" (S3a edit-fields+relations · S3b merge/delete/undo ·
**S3c tag/un-tag/boundaries**; spec §3.5). The completeness sweep over the **mention** CRUD surface +
entity-create-from-tag **closes** (no slicing gap; general entity split + relation qualifiers stay
post-PoC). Full Context/Options/Proposal per entry live in the proposal's register; listed here so the
vault's reader knows they gate the M4.S3c build. **The central one is DM-S3c-1** — the span-storage model:
today a rendered highlight is a render-time **search hit with no identity** (DM-IH-1; `entity_mentions`
spans are NULL/unused), so a manual span (an inflected form, a pronoun, a new entity) can't be re-found by
search and un-tagging acts on a highlight with no row to delete. Register, all **OPEN**:
- **DM-S3c-1 — span-storage model** (the central call): (A) **materialize all** — backfill stored spans,
  drop render-time search (clean per-occurrence corrections, but a migration + loses DM-IH-1's rename-free/
  edit-robust properties); (B) **overlay** — keep search + stored *manual* spans + a *suppression* record
  the resolver subtracts; **materialize incrementally** only what the author touches (my lean — no
  backfill, preserves DM-IH-1); (C) **alias-only** — tag = add an alias (cheapest, but *cannot* express
  change-boundaries or single-occurrence un-tag — fails the requirement). Introduces [[materialization]].
- **DM-S3c-2 — tag-as-new-entity vs existing**: support both (picker for existing + create-new-entity, a
  new human-reached graph writer — INV-9 enumeration grows; my lean) vs existing-only this slice.
- **DM-S3c-3 — un-tag semantics**: "not an entity" (remove/suppress) vs "not this entity" (re-assign/
  detach, optionally atomic re-tag); shaped by DM-S3c-1.
- **DM-S3c-4 — change-boundaries**: materialize-then-edit (under B) vs update-row (under A); downstream of
  DM-S3c-1.
- **DM-S3c-5 — undo integration**: record tag/un-tag/boundary as new `graph_edits` op-kinds + inverters
  (my lean — at minimum the node-creating tag must be reversible) vs outside undo at PoC. `verify-at-build`
  each inverse round-trips, contract-tested from the writer's real output (the PR-#108 producer↔consumer
  lesson).
- **DM-S3c-6 — reader response identity**: add `source: search|manual` + nullable `mention_id` to
  `ReaderHighlight` (my lean) vs address by `(paragraph,start,end,entity)` tuple.
- **DM-S3c-7 — selection surface**: native `window.getSelection()` + context menu (my lean — reader still
  doesn't edit prose) vs adopt **Tiptap now** (the call DM-IH-3 deferred *to this slice* — owner blesses
  the re-deferral or pays the editor setup for V2 to inherit).
- **DM-S3c-8 — slice split**: be (mutators + reconciling resolver + suppression + endpoints + undo
  op-kinds) / fe (selection + menu + picker + hooks); my lean split.
- **DM-S3c-9 — spec amendment**: amend §3.5/§6.4 (manual spans persist offsets; human-authored mentions) +
  reword INV-9 before code (the S3b stop-and-amend precedent); likely **ADR 0008**. Read §3.5/§6.4 at
  amend time — don't inherit the section number (the S3b "delete → §3.5 vs §3.4" lesson).
- **Partially closes** DM-IH-1's granularity mismatch (per-occurrence correction becomes possible).
  **Carries** (not this slice's fix): a suppression/manual span dangles if its entity is later merged/
  deleted (S3b) — same re-point/cleanup the merge undo already does for mentions. **Lands:** M4.S3c, after
  the owner resolves the register. Open.

### OQ-27 — M4 narrowed-multi-story decision register (DM-MS-1..7) — ✅ RESOLVED 2026-06-23 (Session 50, owner)
**Resolved 2026-06-23 (owner; resolved home = `[[m4-multi-story]]` now `accepted` + `docs/PLAN_SHORT.md`
Decided S50).** DM-MS-1 = **DERIVE membership** from `entity_mentions` (no new storage); DM-MS-2 =
**`scope=story|project` param on the existing graph route, DEFAULT `story`** (owner refined my `project`
default → `story`; edge rule (i) — both endpoints story-members ∧ source paragraph ∈ story); DM-MS-3 =
**optional `project_id` on `POST /stories/upload`**; DM-MS-4 = **add `GET /projects` + `GET
/projects/{id}/stories`** (implicit project creation kept); DM-MS-5 = **`world_id` cleanup rides this
slice** + **amend §8.4/§3.3 "whole world" → "whole project"** (host-loop stop-and-amend); DM-MS-6 =
**verified already covered by S3b**; DM-MS-7 = **split be/fe, backend one slice, `world_id` cleanup the
opener**. **No ADR.** **Next: the §8.4/§3.3 spec amendment, then build test-first from the pure
membership-rollup property.** Original framing kept below for history.

Raised by the M4 multi-story step-0 `decompose-requirement` (2026-06-23, `[[m4-multi-story]]`). The
narrowed slice (spec §3.6, amended S44): *"add a new story that reuses the existing project graph +
per-story entity membership"* — the cross-story **world graph** is OUT of PoC (`docs/BACKLOG.md`). The
decompose's defining finding is **how little is new**: per-story membership is already **derivable** from
the `entity_mentions → … → stories` FK chain (rollup query exists), and the matcher seed is already
project-scoped — so a new story in an existing project auto-matches the project's known entities with no
cascade change. The completeness sweep over {project, story} CRUD + graph-scope **closes** (rename +
delete-project/story explicitly deferred — post-PoC / the orphaned-sandbox cross-cutting item). Full
Context/Options/Proposal per entry live in the proposal's register; listed here so the vault's reader
knows they gate the build.
- **DM-MS-1 — per-story membership storage model** (the central call): ✅ **RESOLVED 2026-06-23 (owner)
  = (a) DERIVE from `entity_mentions`** (no new storage; single [[source-of-truth]]; edge membership
  derives from `source_paragraph_id`'s story). *Rejected:* (b) a Neo4j property/`:APPEARS_IN` edge (a
  second home to sync — [[materialization]] not worth it here); (c) a membership table (heaviest).
- **DM-MS-2 — story-scoped graph read shape** (OPEN, spec-silent mechanism): (a) `?scope=story|project`
  query param on the existing `GET /stories/{id}/graph`, default `project` (my lean — additive, back-compat)
  vs (b) make the story route story-scoped + add `GET /projects/{id}/graph` (cleaner, but a behaviour
  change to an existing route). **Sub-question — edge-membership rule** in `scope=story`: (i) both
  endpoints story-members *and* source paragraph ∈ story (my lean — clean subgraph, no dangling edges)
  vs (ii) edges asserted in the story with endpoints pulled in.
- **DM-MS-3 — how create-story-into-existing-project is exposed** (OPEN): (a) optional `project_id` on
  `POST /stories/upload`, omitted ⇒ new project as today (my lean — one code path) vs (b) a nested
  `POST /projects/{id}/stories/upload`.
- **DM-MS-4 — listing surface** (OPEN, completeness gap — no endpoints today): add `GET /projects` +
  `GET /projects/{id}/stories` (read-only [[backend-for-frontend]]); keep project creation implicit-on-
  upload (explicit `POST /projects` deferred — no UX demand). My lean.
- **DM-MS-5 — `world_id` vestigial cleanup** (folded input, confirm-at-build): drop-column migration +
  5-file/8-edit deletion; re-sweep semantically before removal (grep-derived list). **Carries a tiny
  stop-and-amend:** the S49 world-graph-out reconcile keyed on *"world graph"* and missed two *"whole
  world"* phrasings of the §3.4 toggle — **§8.4 line 734** + **§3.3 line 188** — that should read "whole
  project". Owner sign-off on wording (spec edit, not a quiet fix).
- **DM-MS-6 — DM-Rel-5 written-edge re-point**: ✅ **VERIFIED already covered** by M4.S3b (merge re-points
  incident edges, DM-S3b-3). Multi-story adds no new merge trigger → nothing to build; close the carry-forward.
- **DM-MS-7 — slice split**: be (project_id-on-upload + 2 list endpoints + story-scoped read + world_id
  cleanup) / fe (picker + §3.4 toggle); backend provisionally one slice (no compound writes, no undo);
  world_id cleanup optionally a tiny opener PR. My lean.
- **No ADR anticipated** (resolves no open spec question, crosses no new data boundary — DM-MS-1 *removes*
  a would-be boundary by deriving); revisit only if DM-MS-2 (b) is chosen. **Lands:** the M4 multi-story
  build, after the owner resolves DM-MS-2/3/4/7 + the DM-MS-5 amendment wording. Open.

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
