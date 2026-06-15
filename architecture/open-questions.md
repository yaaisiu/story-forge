---
type: open-questions
slug: open-questions
updated: 2026-06-15
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
