---
type: changelog
slug: changelog
updated: 2026-06-08
status: living
related: []
---

# Vault changelog

Append-only audit trail of writes into the vault. Newest entries at the top. History also lives
in `updated` fields (freshness) and git (diffs); this is the human-readable "what changed when".

## 2026-06-08 — M2.S3 register resolved + spec §6.5 amended (owner walkthrough)

The owner walked the `[[m2s3-extraction-agent]]` register; the proposal is now `status: accepted` and
rewritten to resolved state (§5b): **D4** per-paragraph (agent fragment-agnostic), **D5**
single-paragraph agent — resumable batch driver → M2.S4 (pause-and-ask propagates), **G5** soft-flag
`evidence_quote`, **D1/D2/D3/D6** accepted as proposed. Rejected options (per-scene, hard-reject,
agent-owns-batching, blanket `except`) marked history in the body, not build instructions.

**Spec amended (host source of truth, stop-and-amend flow) — G6/Codex #2:** `story-forge-poc-spec.md`
§6.5 router block `route(self, task) -> LLMProvider` → `complete(messages, *, weight, task_type,
json_schema=None) -> CompletionResult` (orchestrating API, ADR 0003); §6.5 + §11 "Failover" paragraphs
now split **envelope-malformed (→ failover via `ProviderResponseError`)** from **schema-invalid
(→ agent prompt-retry)**. Reconciled host homes: `README.md` failover line, `docs/PLAN_SHORT.md`
(cross-cutting item struck ✅, line-64 claim now true). Left intact as history: ADR 0001
(superseded-in-part), the M2.S2 Done/Decided log lines. Vault: OQ-11/OQ-12 struck, OQ-2/OQ-10 advanced,
this proposal's register + gaps brought to resolved. No code touched (ProviderResponseError is the
M2.S3 build).

## 2026-06-02 — `decompose-requirement` (M2.S3 ExtractionAgent — feature step 0)

Forward design pass on **M2.S3 (`ExtractionAgent`)**, run by hand as the feature's step 0 (ritual
integration still deferred, ADR 0002). Wrote `proposals/m2s3-extraction-agent.md` (`status: proposed`,
register **OPEN** — D1–D6 / G1–G6 await the owner). Nine layers + nine stations + Mermaid data flow +
"but what if" + gaps. Designs the three threads the post-M2.S2 sweep seeded: **OQ-10** (typed
`ProviderResponseError` — envelope-malformed→failover vs schema-invalid→retry-prompt), **OQ-2** (agent
stays single-paragraph; resumable batch driver → M2.S4), **OQ-5** (structural vs semantic injection).
Surfaced two new open items and one host-doc flag:
- **OQ-11** — `EntityCandidate.candidate_name` (surface form) vs the plan's "canonical_name" wording.
- **OQ-12** — `evidence_quote` verification posture, dangling relations, PreNER-hint deferral.
- **G6 / host flag** — spec §6.5's router comment lumps "malformed response schema → retry the prompt",
  conflating the envelope-vs-schema split; flagged for a one-line spec clarification (owner's call).

Also folded a **Codex review finding** (small-PR, no-PR-flow) into the vault directly: **INV-5's "writes
one row on *every* terminal edge"** over-claimed coverage given OQ-10 — narrowed to "every terminal edge
**the router currently handles**" + an explicit "known coverage gap (OQ-10)" clause, so a reader can't
mistake INV-5 as already total before the `ProviderResponseError` work lands. Glossary +2
(`prompt-injection`, `poison-message`; 16→18), learning-log +1, open-questions extended (OQ-2/5/10) +
OQ-11/OQ-12 added, INDEX regenerated. No code/config/host-plan touched by the architect (the two
host-side Codex findings are handed back to the main loop for `PLAN_SHORT.md`).

## 2026-06-02 — `review-architecture` (post-M2.S2 as-built sweep, Session 11 wrap)

Second `review-architecture` of the day, run at **session wrap** (after merging M2.S2 PR #36 + wrap
PR #37) — distinct subject from the morning's pre-build OQ-A sweep. Wrote
`reports/2026-06-02-architecture-review-post-m2s2.md` (separate filename so neither clobbers the
other). Headline: **no blockers, no risks** — the as-built faithfully implements ADR 0003; the two
pre-build risks are closed and the **INV-7 near-miss is closed** (ledger records system-derived
tier/provider/model). All findings are `watch`.

- **Drift (planned→as-built lag):** INV-2/5/7 still say "planned (M2.S2) … not yet built" — flip each
  guard to as-built (recommendation; the sweep doesn't edit invariants without confirmation). Noted
  `CompletionResult.model_tier` is still the caller-passed arg (cosmetic; ledger ignores it).
- **Source-of-truth conflict → OQ-9 (latency):** INV-5 + the proposal + the M2.S5 panel task all
  promise `latency`, but the as-built `llm_calls` records none and spec §6.6 doesn't list it. Decide
  before M2.S5: add a `latency_ms` column (proposed) or trim the over-claim.
- **Undrecorded decision:** the **independent-commit ledger** (own connection per write so failure
  rows survive a request rollback) is in code + `PLAN_SHORT` Decided but not the vault — proposed a
  one-line INV-5 enforcement clause (not a new ADR).
- **Fresh near-misses:** INV-6 — M2.S2 is the first paid-key code; it logs nothing today (clean), but
  the named redaction middleware still doesn't exist → build it before the first provider log
  (error bodies echo prompts). D3 cap-overshoot bound weakens if M2.S3 batches concurrently.
- **Forward lens (owner ask) — plan vs architecture:** **no contradiction** S3–S6 vs the
  invariants/decisions. Surfaced **OQ-10** (malformed-`200`-envelope → typed `ProviderResponseError`,
  M2.S3) and made **OQ-2 concrete** (the router now *raises* the pause but nothing *catches* it for a
  resumable batch — M2.S3/S4). The built-but-undrawn LLM-call **state machine** is the strong
  candidate for the next architect deep-dive (ties OQ-C).
- **Process evidence:** recorded that running the sweep at **wrap (end)** is the owner's preference and
  points ritual-integration at `/wrap-session` (ADR 0002 still deferred). open-questions priority-queue
  note + learning-log +3 (out-of-band audit logging, poison-message/dead-letter, state-machine totality).
  **No code or config touched.**

## 2026-06-02 — Review fold (PR #34): accepted-proposal honesty + stable refs

Folded the own-`/review-pr` should-fix + a Codex first-pass review (two P2s, same class) into the
M2.S2 proposal. The `accepted` briefing still carried *pre-decision* active-voice guidance that
contradicted the settled scope — and the handoff points the implementer at it before writing tests,
so it would have produced the wrong files/tests.
- **Codex P2 ×2 + the same class my pass under-rated:** rescoped every "build direct vendor adapters"
  spot (Requirement, §3, §4 `T3` node) to OpenRouter-only; struck/annotated the rejected default-deny
  egress gate + proposed INV-9 (§4 `EG` node noted, §5, §7 Layer 7, §8 G2) as superseded history. Added
  a **⚠ Reading note** to the proposal banner naming both superseded threads so nothing in the body
  reads as a build instruction.
- **Own should-fix:** 4 fragile "spec §6.5 line 412" references → stable "§6.5 GPU-less-host paragraph"
  (proposal ×2, this changelog, ADR 0003).
- Lesson (for `/review-pr`): an *accepted* design briefing that the handoff cites as orienting context
  must not contain active-voice guidance contradicting the decision — annotate rejected options as
  history, don't leave them in the imperative. My pass saw the INV-9 instance but rated it "banner
  covers it"; Codex correctly escalated because the doc is a pre-test reading target.
- **Codex second pass (4 P2s, all real — folded):** the spot-annotation approach was still a
  half-measure. Brought the proposal fully to *resolved* state (update-in-place is the proposals'
  mode anyway): §6 decision register header + each D now read **Decided** not "I propose" (D5 marked
  as the owner *overriding* my proposed gate); §7 quota "still open" → resolved; §8 G1/G3/G4 struck
  resolved; hand-off "no ADR authored" → "ADR 0003 authored"; the §2 Policy station, §4 Mermaid
  `EG` gate node, and §5 state-machine guard no longer show the dropped egress gate. **P2#3:**
  `INDEX.md` de-staled (ADR 0003 is authored in `docs/decisions/`; OQ-8 struck). **P2#4:** the
  usage-row wording in spec §6.6 + ADR 0003 + `PLAN_SHORT` corrected — input/output **tokens are kept
  whenever the provider returns them** (incl. Ollama's eval counts), `gpu_seconds` nullable for Ollama
  Cloud, `cost_estimate` nullable for paid (the old "tokens for paid only" reading contradicted INV-5).
  Stronger lesson: when a decompose proposal is *accepted*, resolve its whole body, don't patch
  cited spots — half-resolved reads as undecided.
- **Codex third pass (3 P2 + 1 P3, the long tail — folded):** the handoff `Verify on disk` still
  listed `{anthropic,openai,grok,router}.py` as what M2.S2 builds (→ `{openrouter,router}.py`); the §3
  `config.py` list still named a paid-egress flag (gate dropped); the §4 Mermaid still routed quota
  exhaustion to "pause / escalate / stop" (→ pause-and-ask, no escalate); the clock-skew edge case
  still called the day-origin a "D1 open item" (D1 resolved = local-midnight). After folding, ran an
  **exhaustive grep sweep** (open-framing / egress-flag / escalate / stale-adapter-list / provider-order)
  to stop the patch-and-recheck cycle — this is the lesson the wrap/retro will encode into `/review-pr`.
- **Codex fourth pass (2 P2 + 1 P3 — folded) — the source-of-truth lesson in the flesh.** I had
  amended spec **§6.5** but left the *same fact* stale in its **other homes**: spec §5 hardware-tier
  table, §9 M2 roadmap, the §1 + §M0 provider/key lists; the root `AGENTS.md` stack reminder; the
  vault `overview.md` M2 snapshot (M2.S2=anthropic/openai/grok, M2.S6=OpenRouter); and residual
  "open" framing inside the resolved OQ-8 body. Reconciled all, plus the ones Codex *didn't* flag
  that a repo-wide sweep caught: `docs/PLAN_LONG.md` M2 bullet, `backend/src/story_forge/AGENTS.md`
  adapter-layer doc (the M2.S2 implementer reads it), `README.md` routing blurb. Left ADR 0001's
  original text untouched (append-only history). **Lesson:** a decision touches a fact that lives in
  many homes; reconciling one (even the authoritative §6.5) is not reconciling the decision —
  enumerate every home and grep the *whole repo*, not just the PR's already-touched files.
- **Codex fifth pass (2 P2 + 1 P3 — folded) — the same class one layer deeper.** The remaining
  stale spots were in **tracking / registry / navigation notes that describe a resolved fact in
  *different words*** (so a keyword grep for the decision misses them): `overview.md` Layer 6 still
  called the quota-exhaustion UX "an open UX decision" (→ pause-and-ask resolved); `PROJECT.md`'s
  source-of-truth registry + existing-docs list omitted ADR 0003; `open-questions.md`'s priority
  queue still listed OQ-A/OQ-B as "the next thing to do" though this run completed both;
  `README.md` pointed only to ADR 0001 as "the LLM ADR". **Lesson (sharper):** resolving a decision
  ripples into the notes that *track* it — registries, priority queues, as-built/error analyses,
  doc-pointers — which don't contain the decision's keywords. The reconciliation checklist must
  include "update every note that *tracks status* (ADR registry, OQ priority queue, error-handling
  snapshot, doc indexes)", not just every note that *states the fact*.
- **Codex sixth pass (1 P2 + 1 P3 — folded) — the dated-artifact-as-live class.** The
  `reports/2026-06-02-architecture-review.md` carried `status: living` and INDEX bills it as the
  "current health snapshot," so its `risk`/`watch` findings (all resolved the same day by ADR 0003)
  read as *open* risk. Added a top resolution banner + changed status `living → accepted` — a dated
  review is a point-in-time record, not a live risk board. Also reframed `README.md`'s quickstart
  key list to foreground Ollama Cloud + OpenRouter (Google/Gemini "as the adapter lands"). **Lesson:**
  a *dated* artifact (review report, sweep, snapshot) whose findings get resolved must say so at the
  top, or it masquerades as current state — `status:` and any "latest/current" framing must match.

## 2026-06-02 — Reconciliation: M2.S2 decisions settled (owner) + vault navigability

Not an architect skill run — a host-repo update folding the owner's decisions back into the vault so
it doesn't drift from reality (the exact failure the same-day review warned about). The owner resolved
OQ-8 (D1–D6) + G1; recorded in `docs/decisions/0003` (new ADR, supersedes ADR 0001's provider-priority
+ quota-degradation consequences) + `docs/PLAN_SHORT.md` Decided; spec §6.5/§6.6 amended.

- **open-questions:** OQ-3, OQ-6, OQ-7, OQ-8 struck ✅ with dated resolution pointers (original framing
  kept for history, per the note's convention).
- **invariants:** INV-2 annotated (consent gate a *deliberate* M2.S5 deferral, not an oversight —
  proposed temporary INV-9 dropped); INV-5 annotated with the decided usage-shape + pause-and-ask +
  system-derived tier (closes the INV-7 near-miss).
- **proposal** `m2s2-llm-router-budget-cap` → `status: accepted`, resolution banner added.
- **Navigability (owner ask):** added `architecture/AGENTS.md` (+ `CLAUDE.md` symlink) — a directory
  guide stating the source-of-truth boundary + how to navigate; root `AGENTS.md` now points to the
  vault. This is *awareness*, not ritual-wiring (ADR 0002 §4 integration still deferred).
- **Dogfood verdict (for the record):** this run is the first where the architect's artefacts fed real
  product decisions (provider order, budget posture, the INV-5 seam). Evidence leans "wire
  `review-architecture` at milestone boundaries + `decompose-requirement` for branchy features," but
  the wiring decision stays deferred per ADR 0002.

## 2026-06-02 — `decompose-requirement` (M2.S2 router + budget cap, OQ-B forward pass)

First live `decompose-requirement` run; the OQ-B strategy pass. Wrote
`proposals/m2s2-llm-router-budget-cap.md` (type `proposal`, `status: proposed`) — a full nine-layer +
nine-station pass on M2.S2 (paid adapters + `LLMRouter` + per-call cost tracking + emergency daily
budget cap + status endpoint), grounded in spec §6.5/§6.6 (referenced, not restated), and carrying in
the two review risks (OQ-6 consent-vs-egress, OQ-7 return-shape + cap-ordering) + the stale ADR 0001.

- **Data flow** drawn as Mermaid (route → egress-gate → budget guard → provider → failover → record).
- **New state machine sketched:** the LLM-call lifecycle (`requested → guarded → {refused |
  dispatched} → {succeeded | retrying | exhausted | fatal}`), guard = egress-gate + cap, effect = a
  usage row on **every** terminal edge incl. refusals. Candidate for the vault's first
  `state-machines/` note.
- **Decision register D1–D6** (all open, mirrored to `open-questions.md` OQ-8): budget-knob grain;
  SDK-vs-httpx; cap atomicity (TOCTOU); one usage table / two billing units; paid-egress enablement
  gate; ADR-0001 reconciliation. **Proposed, not resolved; no ADR authored.**
- **Proposed temporary INV-9** (no paid egress without an enablement gate, M2-scoped like INV-8) and
  two invariant *clarifications* (INV-5 best-effort-with-bounded-overshoot; INV-7 tier must be
  system-derived) — folded into `invariants.md` only on acceptance, not yet.
- **Gaps for PO:** G1 quota-exhaustion decision (+ flagged a live **intra-spec** contradiction: §6.5
  step 5 "degrade to local_small" vs the §6.5 GPU-less-host paragraph "local_small impractical" — may
  need a one-line spec amendment via the stop-and-amend flow), G2 egress posture, G3–G6.
- **Glossary +2** → 16: [[failover]], [[toctou]]. Learning-log +3. INDEX regenerated (proposals/reports
  section added; next-steps 1–2 marked done). **No production code written** (design artefact only).

## 2026-06-02 — `review-architecture` (OQ-A drift sweep, M0→M2.S1 + ADRs 0001–0002)

First live `review-architecture` run; the OQ-A sweep the operator queued. Wrote
`reports/2026-06-02-architecture-review.md` (type `review`). Headline: the **vault** is honest
(as-built-vs-planned already separated) — the drift is **ADR-0001-vs-reality** plus **invariant
guards that lag their risk by 1–3 sessions**. No blockers; 2 risks for M2.S2 planning.

- **Drift / source-of-truth / stale-ADR (one fact, three hats):** ADR 0001's Consequences still say
  "quota exhausted → degrade to local_small", contradicted by the Session-3 GPU-less-host decision
  (spec §6.5 amended; OQ-3). Proposed (human decides): annotate ADR 0001 or mint a superseding ADR —
  not authored.
- **Invariant audit (the explicit ask):** INV-1/3/4/8 honest; INV-2 **risk** (paid egress in M2.S2,
  consent UI not until M2.S5 → OQ-6); INV-5 **risk** (`CompletionResult` discards Ollama token
  counts; cap-ordering unenforced → OQ-7); INV-6 **watch** (verify the named log-redaction
  middleware exists before paid adapters log); INV-7 **watch** (`model_tier` caller-asserted).
- **Structural:** slug/filename case mismatch (`PROJECT.md`/`CHANGELOG.md` vs lowercase slugs)
  corroborates Issue #31; `[[note]]` is a benign format-placeholder; no true orphans.
- **Trail:** OQ-6 + OQ-7 added to `open-questions.md`; 4 concepts appended to `learning-log.md`
  (outbox/saga, fail-closed sequencing, provenance, ADR lifecycle). **No code or config touched.**
  The two risks feed the same-session `decompose-requirement` pass on the M2.S2 router + budget cap.

## 2026-06-02 — `initialize-project-architecture` (first run, seed)

First live use of the meta-architect plugin on Story Forge. Created the vault at
`architecture/` (committed to git, per the init interview). Scaffolded:

- `PROJECT.md` — identity, personas/trust (single local user; the only trust boundary is machine ↔ LLM provider), business (personal tool + public portfolio, equal weight), source-of-truth registry, calibration (operator: novice → Scaffolded tier; both readers).
- `overview.md` — nine-layer system-altitude seed pass, grounded in the as-built present (M0→M2.S1 done; M2.S2+ planned); nine-station snapshot with empty boxes named (Monitoring not-yet-built, Expiry gap).
- `invariants.md` — 8 named invariants (INV-1 human-in-the-loop, INV-2 text-egress consent, INV-3 reversibility, INV-4 open-world types, INV-5 budget cap, INV-6 secrets/log redaction, INV-7 one-adapter-per-protocol, INV-8 temporary M2 no-dedupe).
- `open-questions.md` — operator priority queue (review-then-strategize), 5 vault-raised gaps (two-store consistency, ingest recovery, quota-exhausted UX, retention/Expiry, extraction injection pass), and a reference (not copy) to spec §10's ten questions.
- `glossary/` — 14 seed term notes + regenerated `glossary.md` index (trust-boundary, invariant, state-machine, fail-closed, human-in-the-loop, idempotency, open-world-ontology, source-of-truth, c4-model, agent, cascade-matching, model-tier-routing, compliance-audit-layer, prefer-deterministic).
- `learning-log.md` — 14 lines, one per concept taught this run.
- `INDEX.md` — regenerated vault map.
- Empty dirs (with `.gitkeep`): `decisions/`, `components/`, `state-machines/`, `proposals/`, `reports/`.

No production code touched. No ADR written (none confirmed). Sources of truth referenced, not
duplicated: `story-forge-poc-spec.md`, `docs/PLAN_*.md`, `docs/decisions/`, the seven
`AGENTS.md` files, the code.

**Review fold (same day, PR #30):** Codex flagged that `glossary/model-tier-routing.md` said
the router was "Built in M2.S2" while `overview.md` correctly lists M2.S2 as planned and the
repo has only `adapters/llm/{base,ollama}.py`. Reworded to "Planned for M2.S2 … not yet built".
Swept the whole vault for the same tense-overclaim class — this was the only instance.

**Review fold 2 (same day, PR #30, Codex second pass):** folded 5 findings — all valid.
- *No-duplication (2):* `overview.md` Layer 4 was restating the §6.4 schema (table names,
  `vector(768)`, node/relationship shape) → trimmed to the architectural *reading* of the
  two-store split, schema referenced to §6.4 + `infra/neo4j/init.cypher`. `cascade-matching.md`
  was restating the §3.3 staged algorithm → trimmed to the cheapest-first / fail-closed
  *force*, contract referenced to §3.3.
- *Tense/enforcement honesty (2):* `PROJECT.md` Identity present-tense described unbuilt
  extraction/graph features → reframed as target-V1 with an as-built note. INV-2 claimed
  router/consent-UI enforcement that isn't built → split into today's guard (no-telemetry + one
  Ollama adapter) vs planned (M2.S2/M2.S5), matching INV-1's honesty.
- *Registry accuracy (1):* the data-model source-of-truth row implied Alembic owns the graph
  schema; split into relational (Postgres → §6.4 + Alembic) and graph (Neo4j → §6.4 +
  `infra/neo4j/init.cypher`).
- *Class sweep:* the systematic per-invariant guard audit is routed to OQ-A (the queued
  `review-architecture` drift sweep) rather than half-done here. Operating boundary set: Codex
  is review-only (runs host-Windows over a UNC view; no edits, to avoid cross-env artifacts).
