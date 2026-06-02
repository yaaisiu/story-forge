---
type: review
slug: 2026-06-02-architecture-review
updated: 2026-06-02
status: accepted
related: ["[[overview]]", "[[invariants]]", "[[open-questions]]", "[[model-tier-routing]]"]
---

# Architecture review — 2026-06-02 (OQ-A validation/drift sweep, M0 → M2.S1 + ADRs 0001–0002)

> **✅ Point-in-time snapshot — its findings have since been resolved (same day, 2026-06-02).** This
> is the dated record of the sweep that *produced* the M2.S2 decisions; it is **not** a live risk
> board. The `risk`/`watch` items below — quota-exhaustion behaviour, provider priority / stale
> ADR 0001, the INV-2 egress-vs-consent gap, the INV-5 return-shape + cap-ordering seam — were all
> **settled the same day** by **`docs/decisions/0003`** + spec §6.5/§6.6 (see [[open-questions]],
> OQ-3/6/7/8 struck). Read the findings as the *diagnosis that drove the fix*, not as open risk.

This is the **OQ-A** sweep the operator queued in [[open-questions]]: does the code match the
decisions on record? Are there choices in code with no ADR? And — the explicit ask — **audit each
invariant's "Enforced at" guard against the actual build state**. Scope is everything built and
merged (M0 → M2.S1) plus the two product ADRs (`docs/decisions/0001`, `0002`). Altitude is
mostly **Component** (the LLM-adapter seam M2.S2 builds on) with one **System**-level source-of-truth
conflict.

**Report-only.** Every finding below is located and described; none is fixed here. Severity tags:
**blocker** (must resolve before the dependent work) · **risk** (will bite if unaddressed) ·
**watch** (track; not yet urgent).

**Headline:** the vault is honest — it was written days ago and already separates as-built from
planned (the INV-1/2 "not yet built" notes, the overview's "honest snapshot"). The drift is **not**
vault-vs-code; it is **ADR-0001-vs-reality** (a stale consequence) and a cluster of **invariant
guards that lag the risk they cover by 1–3 sessions**, which M2.S2 is the moment to close. No
blockers. Two risks worth resolving inside M2.S2 planning; the rest are watches.

---

## 1. Drift — vault vs reality

The vault's component/overview claims track the code well; the one genuine drift is in a **host
doc**, not the vault:

- **`watch` — ADR 0001's quota-exhaustion consequence is stale.** ADR 0001 (2026-05-19)
  Consequences: *"When Ollama Cloud quota is exhausted, the router degrades to local_small with a
  warning."* The later Session-3 decision (2026-05-22, recorded in `docs/PLAN_SHORT.md` Decided and
  amended into spec §6.5) established that **the dev host is GPU-less, so local_small is
  impractical** and `cloud_free` is the *default* tier, not a fallback. The vault already reflects
  the new reality ([[overview]] Layer 6; [[open-questions]] OQ-3 "on a GPU-less host, local_small is
  impractical — so the real choices narrow"). So the vault is *not* drifted — **ADR 0001 is.** A
  reader who trusts the ADR's Consequences would design the wrong failover. See §2 and §3 — this is
  the same fact wearing three hats (a conflict, a stale ADR, and a missing amendment).

Otherwise: [[overview]]'s as-built snapshot, the INV "Enforced at … *not yet built*" notes, and the
Data-layer ownership reading all match the code. No component note describes behaviour the code has
since lost (there are no `components/` notes yet — the seed pass deliberately deferred them to OQ-C).

---

## 2. Source-of-truth conflicts

- **`risk` — Quota-exhaustion behaviour: ADR 0001 vs spec §6.5 (amended) + OQ-3.** Two records give
  different answers. ADR 0001 says *degrade to local_small*; spec §6.5 (Session-3 amendment) + OQ-3
  say *local_small is off the table on this host; the real choice narrows to pause-and-ask or
  escalate-within-budget*. **The spec wins** (it is the project's source of truth, and it is the
  newer record). The conflict is load-bearing because M2.S2 designs exactly this failover path —
  building it from the ADR would contradict the spec. **Resolution belongs to the human**, and it is
  the same decision OQ-3 already frames; M2.S2's `decompose-requirement` pass (Part 2 of this
  session) is the right place to force it.

- **`watch` — Paid-provider priority: ADR 0001 ("Anthropic *and* OpenAI as primary") vs the M2.S2
  plan ("Anthropic-first").** Not yet a contradiction — the plan *refines* the ADR's "both primary"
  into an ordering for portfolio + structured-output reasons. It only becomes a conflict if M2.S2
  ships an ordering the ADR never records. Track: when the provider-priority decision is actually
  made this milestone, it should be written where ADR 0001 can be reconciled to it (an amendment
  note or a thin superseding ADR), not only in PLAN_SHORT.

---

## 3. Missing / stale decision records

- **`risk` — ADR 0001 carries no forward-link to its own amendment.** The Session-3 "cloud_free is
  the default tier because the host is GPU-less" + "chunking model → `gpt-oss:20b-cloud`" decisions
  (visible in code: `config.py` `chunking_model`, `chunking_local_max_words`) **materially revise**
  ADR 0001's tier-usage and quota-degradation Consequences, yet ADR 0001 is unannotated. The project
  convention (rightly) keeps lighter decisions in PLAN_SHORT *Decided* rather than minting an ADR for
  each — so the finding is **not** "write a new ADR for the chunking model." It is narrower and
  sharper: **an ADR that a reader will trust now contradicts the running system.** On a public
  portfolio repo that is the costlier failure. *Proposed* (human decides): add a short "Amended
  2026-05-22 — see spec §6.5 / PLAN_SHORT Decided" note to ADR 0001's Consequences (ADRs are
  append-only, so annotate, don't rewrite), **or** a thin superseding ADR 0003 if M2.S2's router
  decisions warrant one. I do not author either unprompted.

- **`watch` — No ADR yet for "where the budget knob lives" or "Anthropic SDK vs hand-rolled
  httpx."** These are the M2.S2 in-session decisions; they are correctly still *open*, not missing.
  Flagged only so they don't evaporate into code without a record — they cross a cost/spend boundary
  (INV-5) and at least the budget-knob choice likely earns an ADR. Handed to Part 2.

Everything else visible in code (split-env layout, per-request-no-pool, UUID PKs, sandboxed uploads)
is already recorded in PLAN_SHORT *Decided* and is below the project's ADR threshold — not flagged.

---

## 4. Invariant audit — each "Enforced at" guard vs actual build state

The operator's explicit ask. Verdict column: **honest** (note already states the as-built-vs-planned
split correctly) · **near-miss** (a guard exists but luck/ordering holds the line) · **seam** (a
forward design constraint the next session must honour).

| INV | Guard claimed | Built today? | Verdict |
|---|---|---|---|
| **INV-1** human-in-loop | Stage-4 review gate | No (M3) | honest — note says "not yet built" |
| **INV-2** consent egress | router + paid paths + consent UI | No (M2.S2/S5); today = 1 Ollama adapter + no-telemetry | **near-miss → risk**, see below |
| **INV-3** reversible | `edit_history` + review queue | No (M3) | honest |
| **INV-4** open-world types | Pydantic string `type`, no enum | No (M2.S3) | honest |
| **INV-5** every call recorded + cap | cost-write + pre-dispatch cap | No (M2.S2) | **seam → risk**, see below |
| **INV-6** secrets/keys never logged | gitignore + detect-secrets + deny-rule + **log-redaction middleware** | partial — verify the middleware | **watch**, see below |
| **INV-7** one adapter/protocol, tier=config | adapter layer + router | Adapter yes, router no | holds today; **near-miss → watch** |
| **INV-8** no dedupe (M2-temp) | M2.S4 round-trip test | No (M2.S4) | honest, correctly flagged temporary |

The three that need eyes:

- **`risk` — INV-2's guard lags its risk by ~3 sessions.** Today text *cannot* leave the machine
  except via the one Ollama adapter, and no telemetry libs exist — so the invariant holds
  by-construction. But M2.S2 adds the **paid-provider egress paths and cost-tracking** while the
  **explicit-consent UI** ("sending fragment to Anthropic, OK?") is not scheduled until **M2.S5**.
  That is a multi-session window in which story text can be transmitted to a paid third party with a
  cost record but **without** the consent crossing INV-2 demands. The invariant note is honest that
  the guard is "planned", but the *sequencing gap* (egress before consent) is the real hazard and is
  not yet tracked. *But what if* a developer wires an extraction smoke-test against a real Anthropic
  key in M2.S3 — text crosses the boundary with no consent gate and nothing fails closed. **Proposed
  mitigation to weigh in M2.S2:** a minimal pre-egress guard (a config flag / per-call confirmation
  default-deny) that lands *with* the paid adapters, so INV-2's guard ships when the risk does, not
  three sessions later. Human decides.

- **`risk` — INV-5 has an active data-loss seam in the current adapter.** INV-5 requires every call
  to record `model, input_tokens, output_tokens, cost_estimate`. Today `CompletionResult`
  (`adapters/llm/base.py`) carries only `content` + `model_tier`, and `OllamaProvider.complete`
  returns `data["message"]["content"]` — **discarding** the `prompt_eval_count` / `eval_count`
  token-usage fields Ollama already returns in the same response. So M2.S2's cost-tracking cannot
  simply read what it needs; the provider return shape must **grow** to carry token counts + model
  name, and every adapter must populate them. The `base.py` docstring already anticipates this
  ("`cost_per_1k_tokens` … land with the router/budget work") — good — but the *return-shape* growth
  (not just Protocol fields) is the concrete seam. Second half of the invariant — "cap check
  **before** dispatch, refused not logged-after" ([[fail-closed]]) — is an **ordering constraint**
  with no enforcer yet; the router must check-then-dispatch, and a naive log-after-call
  implementation would silently violate it. Both belong in Part 2's decompose.

- **`watch` — INV-6 names a "log-redaction middleware" I could not confirm is built.** The other
  INV-6 guards are real and verifiable (`.gitignore`, `detect-secrets`, the harness `deny` rule on
  `.env`). The middleware that "strips `Authorization` / `X-API-Key` before any log line" is claimed
  as present-tense, but no provider call logs headers yet and I did not locate the middleware in this
  sweep. Harmless today (nothing logs keys), but M2.S2 is the first code that *holds* provider API
  keys and could log a request — so **confirm the redaction middleware exists (or reclassify it as a
  planned guard, like INV-1/2) before the paid adapters log anything.** Don't let M2.S2 be the moment
  a key reaches a log line.

- **`watch` — INV-7 near-miss: the tier label is caller-asserted, not provider-verified.**
  `CompletionResult.model_tier` is whatever the caller passed into `complete()`, echoed back —
  `OllamaProvider` does no check that the tier matches its configured host. Fine today (one adapter,
  hand-wired). But when the router wires tiers in M2.S2, a mis-mapped instance would **report the
  wrong tier**, silently corrupting INV-5's cost attribution (a `cloud_strong` call logged as
  `cloud_free`). Cheap guard to consider: derive/verify the tier from adapter identity rather than
  trusting the argument.

---

## 5. Structural rot

- **`watch` — Slug/filename case mismatch corroborates Issue #31.** `[[project]]` and `[[changelog]]`
  are referenced widely and their frontmatter slugs are correct (`slug: project`, `slug: changelog`),
  but the files are **`PROJECT.md` / `CHANGELOG.md`** (uppercase) — violating the meta-architect
  convention "slug = filename without `.md`, kebab-case." Obsidian resolves the links
  case-insensitively so the vault *works*, but any case-sensitive tool (a `comm` slug-diff here; git
  on a case-sensitive FS; a future link-checker) sees them as ghost references. This is exactly
  **[Issue #31](https://github.com/yaaisiu/story-forge/issues/31)** (the meta-architect
  slug/filename carve-out) seen from the review side — logging it here as evidence, not a new item.
  `INDEX.md` (`slug: index`) has the same shape but is not linked-to, so it surfaces only as a
  convention violation, not a ghost.
- **Not rot:** `[[note]]` flagged by the slug-diff is a **false positive** — it lives inside a
  fenced format-example line in `learning-log.md` (`term · appeared in [[note]] · …`), a template
  placeholder, not a real edge. No action.
- **No true orphans.** The vault is small and every glossary term is reachable from
  [[overview]]/[[invariants]]/[[open-questions]]. No dangling `related` edges.
- **ADR 0002 is not stale.** Its sequencing ("run `initialize` next session") is now *satisfied*
  (PR #30) — but ADRs are append-only historical records, so a fulfilled "next step" is history, not
  drift. Its §4 "integrate the skills only after living with the vault" is precisely what *this
  session* is gathering evidence for.

---

## 6. Fresh "but what if" — the LLM-adapter seam (the recently-changed code M2.S2 extends)

A new edge-case pass over `adapters/llm/`, since that is both the most recently-built code and the
foundation M2.S2 sits on. (The budget/failover/quota "but what ifs" are the heart of Part 2's
`decompose-requirement` and are handed there rather than duplicated.)

- **Malformed *envelope* vs malformed *content*.** `OllamaProvider.complete` does
  `data["message"]["content"]`. If a provider returns HTTP 200 with a body missing `message` or
  `content` (truncation, an error object shaped as 200, a proxy injecting JSON), this raises a raw
  `KeyError`, **not** the clean schema-violation the `ChunkingAgent` retry loop knows how to catch.
  M2.S2's failover must distinguish *transport/envelope* errors from *JSON-schema* errors — they
  want different handling (envelope error → retry/failover the provider; schema error → retry the
  prompt then give up).
- **`raise_for_status` maps every non-2xx the same.** A 429 (rate-limit → failover *within* tier), a
  401 (bad key → fail fast, never retry), and a 503 (provider down → failover) are all just
  `HTTPStatusError` today. The router's failover policy needs to branch on status, or it will retry
  an auth failure forever and fail over a rate-limit too slowly. (This is the "status-discriminated
  UX" lesson PLAN_SHORT already records from Session 6's frontend hooks — same shape, backend side.)
- **Timeout is per-instance (120s) with no overall budget.** A heavy `cloud_strong` call plus
  per-tier failover could stack several 120s waits. INV-5's budget is about *money*; there is no
  *time* budget. Probably fine at PoC — name the empty box rather than leave it: **n/a for now,
  revisit if a stalled provider makes ingest feel hung.**

---

## 7. Concepts worth studying (the teaching payoff)

- **Saga / outbox patterns for cross-store consistency.** OQ-1 (Neo4j entity ↔ Postgres mention,
  no shared transaction) is a textbook *dual-write* problem. The **outbox pattern** (write intent to
  one store transactionally, replay to the other) and **sagas** (compensating actions instead of a
  distributed transaction) are the canonical answers. Worth reading even to *consciously reject* them
  for the PoC — see [[idempotency]]. Pointer: Chris Richardson, *Microservices Patterns*, ch. 4–5.
- **Fail-closed sequencing, not just fail-closed state.** INV-5's "cap check *before* dispatch" is a
  reminder that [[fail-closed]] is about *ordering* (check → act), not only the default value. A
  budget that is checked *after* the paid call already fired is fail-open no matter what the config
  says. The general lesson: a guard placed after the irreversible effect is decorative.
- **Caller-asserted vs system-derived provenance.** INV-7's `model_tier` near-miss is an instance of
  a broad class — metadata a caller *claims* vs metadata the system *proves*. Cost attribution,
  audit logs, and the [[compliance-audit-layer]] are only trustworthy when the label is derived from
  the actor, not supplied by it. Keyword to read on: *provenance / attestation*.
- **ADR lifecycle: amend vs supersede vs annotate.** The ADR-0001 staleness is a chance to learn the
  MADR discipline — an accepted ADR is *append-only*; you don't edit its Consequences, you either add
  a dated amendment note or mint a `superseded`-linked successor. Pointer: the MADR project
  (`adr.github.io`) and this vault's own `meta-architect/decisions/0003-vault-update-model.md`.

---

## Hand-off

- New/confirmed open questions are written into [[open-questions]] (OQ-6, OQ-7; OQ-3 cross-linked to
  this report).
- Concepts above are appended to [[learning-log]].
- This review is logged in the vault [[changelog]].
- **Nothing in code or config was touched.** The two **risk**-tagged items (INV-2 consent-vs-egress
  sequencing; INV-5 return-shape + cap-ordering seam) and the **stale ADR 0001** are the load-bearing
  inputs to Part 2's `decompose-requirement` on the M2.S2 router + budget cap — that pass is where
  they get designed against, not here.
