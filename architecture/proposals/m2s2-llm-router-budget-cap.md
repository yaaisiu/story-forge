---
type: proposal
slug: m2s2-llm-router-budget-cap
updated: 2026-06-09
status: accepted
related: ["[[overview]]", "[[invariants]]", "[[open-questions]]", "[[model-tier-routing]]", "[[2026-06-02-architecture-review]]", "[[fail-closed]]", "[[idempotency]]"]
---

# Proposal — M2.S2: paid LLM adapters + `LLMRouter` + budget cap + status endpoint

> **✅ Resolved 2026-06-02.** The owner decided all six register items (D1–D6) + G1. Outcome recorded
> in **`docs/decisions/0003`** + `docs/PLAN_SHORT.md` Decided; spec §6.5/§6.6 amended. Headline:
> provider order Ollama → OpenRouter → Grok → Anthropic → Google → OpenAI; **OpenRouter the only paid
> route built in M2.S2** (hand-rolled `httpx`, no SDK); per-day USD cap with **pause-and-ask** on
> exhaustion/cap (no silent escalation); INV-5 usage-shape grows; egress consent deferred to M2.S5
> (documented, no INV-9). This note stays as the design briefing; the decisions below are now closed.
>
> **⚠ Reading note for the M2.S2 implementer.** The body below is the *pre-decision* exploration —
> it predates the resolution and is kept as design history (the rejected options are the point of a
> decompose). Two threads in it are **superseded** and must NOT be followed as build instructions:
> **(1) scope** — anywhere it says to build direct `Anthropic`/`OpenAI`/`Grok` adapters (Requirement,
> §3, the §4 `T3` node) is overruled by *OpenRouter-only in M2.S2; direct vendor adapters deferred*;
> **(2) the egress gate** — the default-deny enablement gate / proposed INV-9 (§4 `EG` node, §5, §7
> Layer 7, §8 G2, register D5) was **rejected**: egress consent is deferred to M2.S5 with a documented
> in-code marker, no gate ships in M2.S2. The settled scope is the banner + `docs/decisions/0003`.

**Requirement (operator, as decomposed):** the paid-cloud LLM tier — provider adapter(s), the
`LLMRouter` (tier decision order + within-tier failover), per-call cost tracking, an emergency daily
budget cap (hard-stop), and a status endpoint surfacing budget + Ollama Cloud GPU-quota. **Scope
settled after this pass (banner / ADR 0003):** M2.S2 builds only the extended Ollama seam +
`OpenRouterProvider`; the direct vendor adapters (`Anthropic`/`OpenAI`/`Grok`/`Google`) are deferred
to as-needed. Sources of truth: **spec §6.5** (provider abstraction, router, failover)
and **§6.6** (token budget & cost). This note **references** them; it does not restate the schema
or the decision order verbatim.

**Altitude:** **Component** (the `adapters/llm/` + router seam) with a **System**-level ripple
into Data (a new usage table) and a new HTTP surface (status endpoint).

**Carried in from today's review** (`reports/2026-06-02-architecture-review.md`): the two **risks** —
INV-2 consent-guard lagging paid egress (OQ-6) and INV-5's return-shape + cap-ordering seam
(OQ-7) — plus the **stale ADR-0001** quota-degradation consequence. This proposal is where they get
designed against. **I propose; the human decides** *(at decompose time — now **resolved**; the
decisions are in the banner + `docs/decisions/0003`, and ADR 0003 was authored).*

---

## 1. The nine layers

**1. User / personas.** One persona, full trust, local ([[project]] Layer 1). The architectural
payoff *and* the sharp edge: this is the feature that first lights up the **only real trust
boundary** — machine ↔ paid external provider ([[trust-boundary]]). Until now (M0→M2.S1) text
never left the machine except to one Ollama endpoint; M2.S2 is the moment the author's words can be
billed to and stored by Anthropic/OpenAI/xAI. The §6.5 UI control (a per-task provider dropdown +
global per-task-type preference) is the persona's lever; it is *consumed* by M2.S5's panel but the
**data** it shows is produced here.

**2. Business.** Both drivers pull hard ([[project]] Layer 2). *Portfolio:* the multi-provider,
one-Protocol, visible-cost design **is** the demonstration — this is "the most-demonstrated part of
the architecture" (§6.5 opening). *Personal tool:* the budget cap is a real guardrail against a
runaway batch quietly spending the author's money. The cap is therefore not ceremony — it is the
feature's business justification made enforceable.

**3. Domain — ubiquitous language.** New/sharpened nouns: **Provider** (an adapter implementing
`LLMProvider`), **Tier** (`local_small | cloud_free | cloud_strong` — already a `ModelTier`
literal), **Route** (the router's per-task tier+provider choice), **Failover** (transparent retry
against the next provider *in the same tier*), **Budget cap** (a USD/day hard ceiling), **Usage
record** (one persisted row per LLM call). Verb: *route, fail over, record, cap*. These must be the
same tokens in code, the table columns, and the status JSON (the project's no-mapping-layer
discipline — [[overview]] Layer 3).

**4. Data — entities, ownership, keys.** A **new Postgres table** is the heart of INV-5 (the
spec calls it "every LLM operation records: model, input_tokens, output_tokens, cost_estimate" —
§6.6). Postgres owns it (it already owns metadata + the edit history; the graph stays Neo4j's). The
*architectural reading* (not a schema dump — the schema, once accepted, lives in an Alembic
migration per the source-of-truth registry):
- One row per call: when, which **agent/task-type**, **tier**, **provider**, **model**, the
  **usage** — **tokens whenever the provider returns them** (incl. Ollama's `prompt_eval_count`/
  `eval_count`, kept per INV-5/OQ-7), nullable **GPU-seconds** for Ollama Cloud (its billing unit,
  §6.6), nullable **cost_estimate** for paid — **latency**,
  and the **outcome** (succeeded / refused-by-cap / failed). The dual unit (tokens vs GPU-seconds) is
  a modelling decision — see register D4.
- **Aggregation** (daily / per-project / per-task-type — §6.6) is a *read* over this table, not a
  second source. The status endpoint and M2.S5's panel both read the aggregate; neither caches a
  parallel counter (that would be a second source of truth — [[source-of-truth]]).

**5. Behavior — state machines, not statuses.** The LLM call gains a real lifecycle, worth drawing
(§ State & invariants below): `requested → (budget guard) → {refused | dispatched} → … →
{succeeded | failed-retryable → failover | failed-fatal}`. The **guard** is the cap check (an
invariant enforced here); the **effect** on *every* terminal transition is a usage row (evidence
born — the Compliance layer in real time). A naive "call the provider, then maybe log" implementation
has no guard and a lossy effect; that is exactly the INV-5 seam (OQ-7).

**6. Errors — fail-open vs fail-closed.** This layer is unusually loud here; it is most of the
"but what if" surface (§ below). The governing stance is [[fail-closed]] (**domyślnie zamknięty** —
on doubt, deny/stop): budget exceeded ⇒ **refuse**, never "allow and warn" (INV-5). But failover
is the *opposite* pull — a single provider erroring must **not** fail the whole call; it fails *over*
within the tier. The skill is discriminating *which* error is which: a 429 rate-limit → fail over;
a 401 bad-key → fail fast (failover won't help, retrying wastes time); a 5xx → fail over; a
schema-parse failure → retry the *prompt* N times then give up (the `ChunkingAgent` pattern). Today
`OllamaProvider` collapses all of these into one `raise_for_status` — the router must re-introduce
the distinction (review §6).

**7. Security — threat model, abuse paths.** Two surfaces:
- **Egress consent (OQ-6, INV-2).** This is the load-bearing security finding. M2.S2 opens paid
  egress paths; the explicit per-fragment consent UI is M2.S5. **A guard that ships three sessions
  after the risk it governs is fail-open by sequencing.** → **Resolved (D5, ADR 0003): the gate
  below was *proposed and NOT adopted*** — the owner deferred consent to M2.S5 (no security-sensitive
  data), with a documented in-code marker at the egress point rather than a config gate. *(Superseded
  proposal, kept as history:* a default-deny enablement gate lands with the paid adapters so INV-2 has
  some enforced guard from the moment egress is possible.*)*
- **Key handling (INV-6).** M2.S2 is the first code holding paid API keys. Keys come only from
  `.env` (agent never touches it). The redaction guard INV-6 *names* (strip `Authorization` /
  `X-API-Key` from logs) must be **confirmed to exist** before any provider request is logged — the
  review flagged it as unverified (INV-6 watch). If it doesn't exist yet, it ships here, fail-closed.

**8. Compliance / Audit — provable adherence.** The usage table *is* the evidence trail for §6.6 +
§11 observability. Every paid call is provable after the fact: what model, what it cost, which agent
asked, whether the cap refused it. This is the station the feature most strengthens (Evidence). The
caveat from the review: the recorded **provider/tier/model must be system-derived, not
caller-asserted** — INV-7's `model_tier` near-miss means an echoed label can lie, and a lying cost
ledger is worse than none.

**9. Operations — observability, runbooks.** The **status endpoint** is the new ops surface:
daily/project/task-type spend, remaining Ollama Cloud GPU quota, paid spend so far, and *which tier
served the last call* (§6.5 "quota status visible at all times"). It is built here and consumed by
M2.S5's panel. No alerting/on-call (**n/a — single-user local**, named not blank). One runbook line
worth capturing when it lands: "cap hit ⇒ ingest pauses; raise `DAILY_BUDGET_USD` or wait for the
day to roll."

---

## 2. The nine stations (enforcement-lifecycle checklist)

| Station | Present? | Where / note |
|---|---|---|
| **Identity** | n/a — single local user | but *provider* identity (which model served) is recorded — that's Evidence, not Identity |
| **Intent** | ✅ | the agent's task-type + the user's §6.5 provider-dropdown choice express intent per call |
| **Policy** | ✅ | budget cap (§6.6), tier decision order (§6.5); paid-egress consent **deferred to M2.S5** (D5 — documented marker, no gate) |
| **Decision** | ✅ | `router.complete()` selects tier+provider (+ within-tier failover); the budget guard allows/refuses. *(As-built / amended spec §6.5: the orchestrating `complete()`, not the originally-sketched `route()→provider`.)* |
| **Access** | n/a inter-user | a provider's API-key *presence* is the only "access" gate; absent key ⇒ that provider is unconfigured, skipped in failover |
| **Monitoring** | ◻ partial | status endpoint built **here**; the visible panel is M2.S5 |
| **Evidence** | ✅ strong | the usage table — one row per call, the INV-5 trail |
| **Expiry** | ◻ **gap** | no retention policy for usage rows / prompt-response logs → ties to OQ-4. Flag, don't solve here |
| **Review** | ✅ partial | the human reads the dashboard and owns the cap value; the cap *enforcement* is automatic (correctly — money) |

**Empty/weak stations → open questions:** **Expiry** (usage/log retention) folds into existing OQ-4;
**Monitoring** is split-built (endpoint now, panel M2.S5) — tracked, not a gap.

---

## 3. Affected components & ripple

No `components/` notes exist yet (deferred to OQ-C), so this names the *code* surfaces and the
invariant pressure:

- `adapters/llm/base.py` — **`CompletionResult` and the Protocol grow** (add `cost_per_1k_tokens` +
  `rate_limit_kind` per §6.5; add usage fields to the result per OQ-7). Every existing caller
  (`ChunkingAgent` via `OllamaProvider`) must keep compiling — the growth is additive.
- `adapters/llm/ollama.py` — **must stop discarding** `prompt_eval_count`/`eval_count` (OQ-7) and
  start reporting GPU-seconds if the cloud response carries them.
- `adapters/llm/openrouter.py` — **new** (the only paid adapter built in M2.S2), mirroring the
  mocked-transport test shape (`tests/unit/adapters/llm/test_ollama.py` is the pattern). *(The
  `{anthropic,openai,grok,google}.py` direct adapters this section originally listed are deferred —
  see the banner reading-note.)*
- `adapters/llm/router.py` — **new**; the decision order + failover + the budget guard call.
- A **new repo + migration** for the usage table (`adapters/…_repo.py` + Alembic).
- `api/` — **new status route** (declares its non-2xx outcomes per `backend/CLAUDE.md` "API routes").
- `config.py` — new settings: `DAILY_BUDGET_USD`, provider priority. (No egress flag — D5 dropped the
  gate; keys already present.)
- **Invariants under pressure:** INV-5 (this feature *is* its guard), INV-2 (egress opens), INV-7
  (router must not let tier labels lie), INV-6 (first key-holding code).

---

## 4. Data flow

A medium task routes to `cloud_free`; a heavy task to `cloud_strong` with the budget guard and
within-tier failover. The guard runs **before** dispatch (fail-closed ordering, OQ-7); the usage row
is the effect on **every** terminal edge (evidence, INV-5).

```mermaid
flowchart TD
    A[Agent: complete task] --> R[LLMRouter.route task]
    R -->|light| T1[local_small]
    R -->|medium| T2[cloud_free / Ollama Cloud]
    R -->|heavy| T3[cloud_strong: OpenRouter preferred; direct adapters deferred]

    T3 --> G{budget guard:<br/>day spend + est < cap?}
    G -->|no| REF2[REFUSE · hard-stop · record outcome]
    G -->|yes| P1[provider.complete]

    T2 --> Q{Ollama Cloud<br/>GPU quota left?}
    Q -->|no| OQ3[free quota gone:<br/>pause-and-ask · no auto-escalate]
    Q -->|yes| P1

    P1 -->|2xx + valid schema| OK[record usage row:<br/>model, tokens/GPU-s, cost, latency]
    P1 -->|429 / 5xx| FO[failover: next provider in tier]
    P1 -->|401 bad key| FF[fail fast · skip provider · record]
    P1 -->|envelope malformed| FO
    P1 -->|schema invalid| RT[retry prompt ≤N, then give up]
    FO --> P1
    FO -->|tier exhausted| EX[ERROR: all providers failed · record]

    OK --> RET[CompletionResult + usage] --> A
    REF2 --> A
    EX --> A

    OK -. read aggregate .-> ST[GET /status: spend + GPU quota]
    ST -. M2.S5 .-> PANEL[agent-activity panel]
```

---

## 5. State & invariants

### New state machine — the LLM call lifecycle
States: `requested → guarded → {refused | dispatched} → {succeeded | retrying → (dispatched|exhausted) | fatal}`.
Terminal: **succeeded**, **refused** (cap), **exhausted** (all in-tier providers
failed), **fatal** (non-retryable, e.g. malformed request).
- **Guard** (where invariants are enforced): the cap check (INV-5), *before* dispatch. *(The egress
  gate this section originally also named was dropped — D5; consent is the M2.S5 deferral, not a
  guard here.)*
- **Effect** (where evidence is born): a usage row on **every** terminal edge — *including refusals
  and failures*, not just successes. A refusal that leaves no trace can't be audited ("why did the
  batch stop?"). This is the Compliance layer happening in real time.
- Worth drawing as a real `state-machines/` note when accepted (candidate for the vault's first one).

### Invariant pressure & proposed changes (folded into [[invariants]] only on acceptance)
- **INV-5 — clarify, don't weaken.** The cap is **best-effort with bounded overshoot**: spend is
  only *known* after the call returns (you can't count output tokens before generating them), so the
  guard checks `day_spend_so_far + estimate < cap`. Under concurrency two calls can both pass the
  check then both land — a **TOCTOU** race (*time-of-check-to-time-of-use*: the check and the use are
  split by a concurrent change). At PoC (single user, sequential ingest) the worst case is **one
  in-flight call's overshoot**; name it and accept it, or serialize paid calls (D3).
- **INV-7 — strengthen.** The recorded tier/provider/model must be **system-derived** (from the
  adapter that actually served the call), never the caller's echoed `model_tier`. Otherwise the cost
  ledger and the audit trail can be quietly wrong.
- **~~Proposed INV-9 [TEMPORARY · M2-scoped, like INV-8]~~ — NOT ADOPTED (D5, ADR 0003).** The
  proposal was *No paid egress without an explicit enablement gate* — every `cloud_strong` provider
  fails closed unless an enablement flag is set. The owner **rejected** it: egress consent is deferred
  to M2.S5 (no security-sensitive data) with a documented in-code marker, and no gate ships in M2.S2.
  Kept here as design history; INV-9 was never folded into [[invariants]].

---

## 6. Decision register — ✅ all resolved 2026-06-02 (`docs/decisions/0003`)

_Each entry keeps its Context/Options as the reasoning record; the **Decision** line is what the
owner accepted. D1–D4 + D6 were accepted as proposed; **D5 the owner overrode** (chose to defer the
gate, not build it). Authoritative record: ADR 0003 + `docs/PLAN_SHORT.md` Decided._

**D1 — Where the budget knob lives (per-call / per-session / per-day).**
- *Context:* §6.6 literally says "emergency cap: stop after exceeding **X USD per day**," and asks
  for daily/project/per-task-type *reporting*.
- *Options:* (a) per-day USD hard-stop only (spec-faithful) + per-project/task-type as read-only
  aggregates; (b) add a per-session soft ceiling; (c) per-call max-cost guard too.
- *Decision (accepted, ADR 0003):* **(a)** — one hard knob `DAILY_BUDGET_USD`, the rest are reports. Smallest honest
  surface, matches the spec word-for-word; add (b)/(c) only if a real overrun shows the day-grain is
  too coarse. *Resolved:* "day" = **local-midnight** (simpler to reason about and to display).

**D2 — Anthropic SDK vs hand-rolled `httpx`.** *(crosses the dependency baseline — §6.7 / `/add-dependency`)*
- *Context:* the paid adapters need an HTTP client. `OllamaProvider` is hand-rolled `httpx` with an
  injectable transport for tests.
- *Options:* (a) official `anthropic` + `openai` SDKs; (b) hand-rolled `httpx` mirroring
  `OllamaProvider`.
- *Decision (accepted, ADR 0003):* **(b)** for INV-7 uniformity (one adapter shape, one mocked-transport test
  pattern), minimal dependency surface, and portfolio legibility (the swappability is *visible*, not
  buried in an SDK). *Cost I accept (stated, per doctrine):* I hand-write each provider's
  token-usage parsing and retry semantics that the SDK would give free — and SDKs track breaking API
  changes for me. If a provider's auth/streaming proves fiddly, revisit per-provider (the Protocol
  lets one adapter use an SDK while others don't). Either way → `/add-dependency` (pin + 14-day soak).

**D3 — Cap atomicity under concurrency.**
- *Context:* the TOCTOU race in INV-5 above.
- *Options:* (a) accept one-call overshoot at PoC, documented; (b) serialize paid calls (a Postgres
  advisory lock around check+dispatch); (c) reserve-then-reconcile (debit the estimate before the
  call, true-up after).
- *Decision (accepted, ADR 0003):* **(a)** — single-user sequential ingest makes the race nearly unreachable; (c) is
  the right answer *if* batched concurrent extraction ever lands (M2.S3+). Document the bound.

**D4 — One usage table, two billing units (tokens vs GPU-seconds).**
- *Context:* §6.6 — paid tiers bill per token; Ollama Cloud bills in GPU-seconds.
- *Options:* (a) one `llm_calls` table with nullable `input_tokens`/`output_tokens`/`cost_estimate`
  (paid) **and** nullable `gpu_seconds` (cloud-free), discriminated by `tier`; (b) two tables.
- *Decision (accepted, ADR 0003):* **(a)** — one evidence trail is easier to aggregate and to show; the null pattern
  honestly reflects "this metric doesn't apply to this tier" (naming the empty box, at the data
  level). *Resolved:* keep them **separate units** — GPU-seconds shown as quota, **no fabricated
  dollar value** for free-tier GPU time (spec §6.6).

**D5 — Paid-egress enablement gate (INV-2 / OQ-6).** *(crosses the trust boundary)*
- *Context:* egress opens in M2.S2; consent UI is M2.S5.
- *Options:* (a) accept the ungated window at PoC, documented; (b) a default-deny config flag
  (`paid providers refuse unless enabled`); (c) a per-call CLI/log confirmation now.
- *Decision (owner overrode my proposal):* **(a)** — accept the ungated window, **documented**, until
  M2.S5. The PoC handles no security-sensitive data, so control/simplicity won over the gate; the
  proposed default-deny flag (b) and INV-9 are **dropped**. *(My pass had proposed (b); the owner
  chose (a) — recorded honestly.)*

**D6 — ADR-0001 reconciliation.** *(carried from the review)*
- *Context:* ADR 0001's "quota exhausted → degrade to local_small" is contradicted by the GPU-less
  reality (spec §6.5 GPU-less-host paragraph). M2.S2 codifies the router's actual quota-exhaustion behaviour, so the
  decision must be recorded *somewhere authoritative*.
- *Options:* (a) append a dated amendment note to ADR 0001; (b) a thin superseding **ADR 0003**
  capturing the M2.S2 router/quota/budget decisions as a set; (c) leave it in PLAN_SHORT only.
- *Decision:* **(b)** — **ADR 0003** authored (the decisions are a coherent cluster worth one record),
  superseding ADR 0001's provider-priority + quota-degradation consequences; ADR 0001 annotated.

> ✅ Resolved 2026-06-02 — recorded in `docs/decisions/0003` + `docs/PLAN_SHORT.md` Decided; mirrored
> (struck) in [[open-questions]] OQ-8. D1–D4 + D6 accepted as proposed; **D5 the owner overrode** to
> (a) (defer the gate).

---

## 7. But what if (edge cases, races, partial failures, hostile inputs)

- **…the budget guard and the spend it reads race?** The **TOCTOU** above (D3). Bounded overshoot at
  PoC; name it so no one mistakes the cap for exact.
- **…a provider returns 200 with a malformed *envelope*** (missing `message`/`content`, an error
  object shaped as success, a proxy injecting JSON)? Today that's a raw `KeyError`. The router must
  treat **envelope-malformed ≠ schema-invalid**: the former → failover the *provider*; the latter →
  retry the *prompt*. Conflating them either retries a dead provider or fails over a fixable prompt.
- **…the only configured provider in a tier is down?** Failover has nowhere to go → the call reaches
  **exhausted**, records the failure, and surfaces a clear error — it must not silently fall to a
  *different* tier (that would cross a cost boundary without consent). Cross-tier escalation is a
  *separate, consent-gated* decision (OQ-3), not a failover default.
- **…cloud_free GPU quota runs out mid-batch?** ✅ Resolved (OQ-3 / ADR 0003): **pause-and-ask** — and it was also intra-spec-contradictory
  (§6.5 step 5 "degrade to local_small" vs the §6.5 GPU-less-host paragraph "local_small impractical").
  The router cannot honour step 5 on this host. **Decided (G1):** **pause-and-ask** — the owner chose
  control over unattended spend; no auto-escalate-to-paid. Spec §6.5 step 5 amended to match.
- **…a 401 bad key?** Fail *fast*, skip that provider, never retry (retrying a bad key wastes the
  failover budget and can trip the provider's abuse throttles). Distinct from 429.
- **…the cap is hit on call N of a 200-paragraph ingest?** Fail-closed: the in-flight call (if any)
  finishes and is recorded, subsequent calls are **refused with a recorded outcome**, the ingest job
  pauses resumably (leans on [[idempotency]] + per-paragraph stable ids — ties to OQ-2). It must not
  half-write the graph and forget where it stopped.
- **…a provider's error message echoes the prompt (which contains the author's text) into a log?**
  INV-6 redaction must cover provider *error bodies*, not just request headers — a 400 from a
  provider often quotes the offending payload. Hostile-input-adjacent even though the author is
  trusted: the *provider* is across the trust boundary.
- **…two adapters are accidentally wired to the same tier with one mislabelled?** INV-7 near-miss —
  the system-derived tier (D-strengthen) is the guard; without it the ledger lies.
- **…clock skew / day boundary mid-call?** The "per-day" cap's day-origin is **local-midnight** (D1,
  resolved). A call straddling midnight bills to its *start* day, by convention.

---

## 8. Gaps for the product owner

- **~~G1 — Quota-exhaustion behaviour~~** ✅ **Resolved:** **pause-and-ask** (no auto-escalate). The
  spec self-contradiction (step 5 vs the GPU-less-host paragraph) was the trigger; **spec §6.5 step 5
  amended** via the stop-and-amend flow to resolve it.
- **~~G2 — Is a default-deny paid-egress gate (D5/INV-9) acceptable for M2.S2~~** ✅ **Resolved:**
  the ungated window is documented-and-accepted until M2.S5 (no security-sensitive data) — no gate
  in M2.S2. This was the single biggest security-posture call in the milestone.
- **~~G3 — ADR-0001 reconciliation (D6)~~** ✅ **Resolved:** superseded via **ADR 0003** (ADR 0001
  annotated superseded-in-part).
- **~~G4 — SDK vs httpx (D2)~~** ✅ **Resolved:** hand-rolled `httpx` (no SDK). Direct vendor adapters
  deferred, so no `/add-dependency` run is needed in M2.S2.
- **G5 — Retention (OQ-4 / Expiry station):** usage rows are cheap, but if §11's full prompt+response
  logs are also written, they accumulate the author's text indefinitely. Decide a posture (document
  "no retention at PoC" *or* a simple cap) — not blocking M2.S2, but the Expiry box is empty.

---

## Hand-off

- D1–D6 resolved 2026-06-02 (banner / §6); mirrored (struck) in [[open-questions]] OQ-8.
- New concept notes added to the glossary where they'll recur; `learning-log` + `CHANGELOG` appended.
- **ADR 0003 authored** (`docs/decisions/0003`), superseding ADR 0001's provider-priority +
  quota-degradation consequences. **No production code written** — this is a design artefact.
- The first failing test the operator writes for M2.S2 (`OpenRouterProvider` against a mocked
  transport, per the handoff) should encode the **system-derived usage fields** (OQ-7) and a
  **cap-refusal path** (INV-5) from the start — the two are the load-bearing contracts, not afterthoughts.
