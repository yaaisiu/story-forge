---
type: changelog
slug: changelog
updated: 2026-06-15
status: living
related: []
---

# Vault changelog

Append-only audit trail of writes into the vault. Newest entries at the top. History also lives
in `updated` fields (freshness) and git (diffs); this is the human-readable "what changed when".

## 2026-06-15 — decompose-requirement: M3.S4c intra-batch dedup (live re-match + handpick, step-0)

Forward-design pass triggered by the **M3.S4b browser walk**: a single first-pass extraction of the
sample story staged `Janek` ×3 (and `Marta`/`Konrad`/`Order` ×2) as independent NEW proposals → after
accept, **duplicate Neo4j nodes** the review queue could not merge, undercutting §9 M3's "the graph is
clean". The cascade only dedupes *cross-pass* (against the accepted graph at stage time); this is the
*intra-batch* gap M3.S4a's own "but what if" had named and deferred.

- **New proposal:** `proposals/m3s4c-intra-batch-rematch.md` (`status: proposed`, register **OPEN**).
  Designs two additive mechanisms on top of S4a/S4b: **(a) on-accept live re-match** — re-run the
  *deterministic* matcher (Stage 1 RapidFuzz + Stage 2 cosine, reusing the stage-time `context_embedding`
  + the accepted entity's mention vector; **no LLM**) over still-pending candidates each accept, flipping
  duplicates `new → merge` (backend-only — the S4b card already renders merge proposals); **(b) manual
  handpick** — a `GET …/entities?q=` search + picker so the human can target *any* existing entity, the
  safety net for matcher false negatives. Both write **only the `candidates` staging table** — INV-1 +
  INV-9 **hold, not change** (re-match is the first automated *staging-proposal* writer; INV-9's line is
  graph-vs-staging). Nine-layer + nine-station pass; Mermaid data-flow; but-what-if (false-positive
  re-match, mid-review proposal flips, idempotency/thrash, rejected-not-resurfaced, handpick stale-target
  409, **handpick-merge inherits the deferred relation-write**, perf bound).
- **State machine:** proposes a `review-queued → review-queued` **re-proposal** self-loop (monotone:
  only `new → merge`; no graph write, no evidence row) — folded into `[[candidate-lifecycle]]` only on
  acceptance.
- **Open register OQ-18 / DM-S4c-1..6:** slice S4c (re-match) + S4d (handpick); trigger/scope
  (synchronous-in-accept + incremental); auto-flip strength (Stage-1-only, **no live judge**); monotone
  refinement (possible INV-10 — lean guard); handpick scope (project-scoped — **supersedes** the deferred
  "arbitrary-entity search" cross-cutting); handpick endpoint/source. Mirrored to `open-questions.md`.
- **Glossary +1** → 21: `[[intra-batch-dedup]]`. **learning-log +2** (intra-batch dedup; monotone
  refinement / suggestion-only automated writer). **INDEX** regenerated.
**Register resolved same session (owner, Session 25):** proposal flipped `proposed → accepted`,
every DM-S4c register entry `My proposal` → `Decision` (**DM-S4c-3 overridden** — owner chose auto-flip
on **Stage 1 `>85%` OR Stage 2 `cosine >0.85`** over my Stage-1-only; no live judge), the Stage-1-only
framing de-activated across the body (Policy station, but-what-if, hand-off), Gaps-for-PO + the INV-10
sub-question resolved (not minted — monotonicity stays the transition guard), OQ-18 struck. Decisions:
slice **S4c (re-match) + S4d (handpick)**; synchronous-in-accept + incremental; project-scoped handpick
(`GET /stories/{id}/entities?q=`); relation-write **kept deferred** but priority raised.

**Spec + plan reconciled (host source of truth, stop-and-amend flow):** `story-forge-poc-spec.md` §3.3
gained the **on-accept re-match** + **manual-handpick** clarifications + a deterministic-only cost-note
line. `docs/PLAN_SHORT.md`: M3.S4c + S4d added to the feature order, a Session-25 Decided entry + the
struck M3.S4c register (Blocked), the "arbitrary-entity search" cross-cutting **folded into S4d** (struck
✅), the relation-write cross-cutting **priority-raised** note. No production code; ADR 0005 (if warranted)
authors test-first with the S4c code. The `[[candidate-lifecycle]]` self-loop + INV-9 clarification fold
on that build, witnessed by the failing re-match flip test.

## 2026-06-09 — fold: drift-fixes applied + full doc audit (owner-approved)

The 2026-06-09 sweep's recommended drift-fixes were **approved by the owner and folded**, plus a
full audit of the remaining vault notes for staleness. Edits (all vault-only, no code): **`overview.md`**
— M2.S2 + M2.S3 moved to "built and merged" (was 3 sessions stale, still calling them "planned"), the
"does not yet extract" summary corrected to "extracts but does not yet write the graph", the
nine-station Monitoring row flipped `◻ planned → ✅ partial` (status endpoint + ledger built),
`updated` 06-02→06-09. **`invariants.md`** — INV-5's OQ-10 "coverage gap" clause flipped to
as-built-closed (PR #42), INV-4's "(M2.S3)" planned tense → as-built, `updated` 06-08→06-09.
**`PROJECT.md`** — Identity line "extraction is M2.S3–S4" → "extraction built (M2.S3); graph write
M2.S4", `updated` 06-02→06-09. **`m2s2-llm-router-budget-cap.md`** — the stale `router.route()`
station-table depiction → `router.complete()` (as-built / amended spec §6.5; the cross-cutting
doc-hygiene item), `updated` bumped. Audit confirmed clean: glossary index (20) matches INDEX; no
orphans / ghost refs / stale ADRs. INDEX already current (regenerated).

## 2026-06-09 — review: pre-M2.S4 drift + forward sweep

`review-architecture` run at the owner's request before building M2.S4 (Neo4j writes), diffing the
vault against the as-built after M2.S3 (PR #42) + the SCA gate (PR #44) merged. New
`reports/2026-06-09-architecture-review.md`. **No blockers.** Findings: (1) `risk` — `overview.md` is
three sessions stale, still listing M2.S2 *and* M2.S3 as "planned, not yet built"; (2) `watch` —
INV-5 still calls OQ-10 an open gap though `ProviderResponseError` landed in PR #42, and
`open-questions.md` OQ-10 isn't struck-closed though INDEX says it is; (3) `risk` (forward) — the data
model assumes an `entity_mentions` table that **does not exist in the migrations** (only spec §6.4) —
already fixed in `docs/PLAN_SHORT.md` this morning; (4) `risk` (forward) — INV-8's no-dedupe must be
held by `CREATE`-not-`MERGE` + a failing test; (5) `risk` (forward) — the new graph-write API path
must map router exceptions to HTTP or it 500s (chunking path catches only `ChunkingError`). Forward
lens: M2.S4 plan **aligned** with the invariants; OQ-1 (two-store consistency) + OQ-2 (resumable batch)
are the owner's calls as the session opens. Trail: `open-questions` +findings (deduped into OQ-1/OQ-2
notes); learning-log +3. **Report-only:** the `overview.md`/`invariants.md`/OQ-10 drift fixes are
*recommended* for owner approval, not folded unilaterally.

## 2026-06-08 — decompose: backend dependency-advisory scan (continuous SCA)

`decompose-requirement` on adding a backend Python SCA gate to CI, triggered by GHSA-86qp-5c8j-p5mr
(`starlette` 1.0.0, MEDIUM, via `fastapi`) — Dependabot caught it, CI did not (Trivy scans only
Docker images; no scan of `backend/uv.lock`). New `proposals/backend-dependency-advisory-scan.md`
(`status: proposed`, register D1–D7 open): owner leans **osv-scanner**, **selected fail-on-any +
waiver file** (D2); open G1–G7 (tool confirm, **spec §6.7 amendment** to document the gate, waiver
home/format/expiry reusing the Trivy `WAIVERS.md` split, `npm audit` symmetry, scanner-Action
SHA-pin, baseline-vs-INV-9, bundled `starlette` 1.0.0→1.0.1 bump). Glossary +2
(`software-composition-analysis`, `defense-in-depth` → 20). `open-questions` +OQ-13; learning-log +2.
This is **strengthening** the §6.7 baseline (not the stop-and-amend-to-relax flow). No production code
touched (architect is vault-only); the gate + bump are the implementer's build once the owner resolves.

**Register resolved same day (owner approved G1–G7 cluster):** proposal flipped `proposed → accepted`,
every register `My proposal` → `Decision`, §7 gaps marked resolved, §8 hand-off rewritten with the
next-session build steps. OQ-13 advanced (stays open until code lands, OQ-10 posture). Decisions:
osv-scanner, fail-on-any + scoped waivers (`infra/osv/`), SHA-pinned Action, `npm audit` left
HIGH/CRITICAL, §6.7 baseline control (no new INV), explicit `starlette==1.0.1` pin. **Build deferred to
next session; the spec §6.7 amendment lands *with* the build** (avoids claiming a gate CI doesn't run).

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

## 2026-06-11 — `review-architecture` (M2→M3 roll catch-up + forward sweep)

Run at the M2→M3 milestone boundary (gate 2 of the roll). The last sweep
(`2026-06-09-architecture-review`) predated **M2.S5** (PR #51) and **M2.S6** (PR #53), so the
update-in-place notes lagged two merged sessions.

- **New report:** `reports/2026-06-11-architecture-review.md`. No blockers. One `risk` on a security
  invariant: **INV-2's consent gate was deferred (ADR 0003 D5) with M2.S5 as its landing spot, and
  M2.S5 shipped without it** — the gate is now unscheduled and the M2.S6 smoke fired real paid egress
  gate-less (the OQ-6 window, now realised; accepted at PoC scale but the schedule is stale). Other
  drift is freshness: `overview.md` two sessions stale (header "M0 → M2.S3", M2.S5/S6 under "planned");
  INV-5/OQ-9 latency still future-tensed though `latency_ms` is built (M2.S5, migration
  `2026_06_11_0956…`); INDEX "Next: M2.S5".
- **`open-questions.md`:** added **OQ-14** (§6.5 model-override dropdown vs INV-7 — framed, likely
  future ADR) and **OQ-15** (operational logging absent ⇒ INV-6 vacuously true — framed). This
  discharges the `docs/PLAN_SHORT.md` cross-cutting "reflect the M2→M3 roll decisions in the vault"
  item. `updated` → 2026-06-11.
- **`learning-log.md`:** +3 lines — vacuous truth; accepted deferral vs silent drift; temporary-
  invariant hand-off (INV-8→INV-1).
- **`INDEX.md`:** regenerated — M2.S5/S6 done, M3 next, this report + OQ-14/OQ-15 registered.
- **Recommended (report-only, not applied this sweep) for the decompose step-0 to fold:** re-point
  INV-2's consent gate; flip INV-5/OQ-9 latency to as-built; refresh `overview.md` to M2.S6/M3. Source
  notes `overview.md` / `invariants.md` left unedited per report-only discipline.

## 2026-06-11 — `decompose-requirement` (M3 cascade, step-0)

M2→M3 roll gate 2, part 2: the forward-design pass on M3 — the §3.3 cascade dedupe — before any code.

- **New proposal:** `proposals/m3-cascade-matching.md` (`status: proposed`, register OPEN). Nine-layer +
  nine-station pass; Mermaid data-flow; the candidate-lifecycle state machine; an 8-entry decision
  register (DM1–DM7 + DM-rej); a but-what-if pass (intra-batch dupes, review-gate TOCTOU, fail-closed
  embedding/judge outages, relation re-pointing on merge, rejected-candidate re-surfacing); gaps for the
  PO. Central fork flagged: **DM6** — matching *gates* the write (intercept-before-write, my strong
  proposal) vs dedupe-after — which decides whether **INV-8 is replaced or layered**.
- **New state machine (the vault's first):** `state-machines/candidate-lifecycle.md` (`status: draft`) —
  `extracted → {auto-merge|ambiguous|new}-proposed → judged → review-queued → (human) →
  {merged|created|rejected}`; the commit guard *is* INV-1; every terminal edge writes `edit_history`
  (INV-3).
- **Freshness fixes folded** (the 2026-06-11 review's recommendations, applied because they're honest
  as-built corrections independent of the open M3 register): `invariants.md` INV-2 (consent gate
  re-pointed from the lapsed M2.S5 → M3 review-queue UI + the "real paid call fired gate-less" as-built
  note) and INV-5 (`latency_ms` → as-built M2.S5); `open-questions.md` OQ-9 → built; `overview.md`
  header → M0→M2.S6, M2.S5/S6 into built, planned → M3, Monitoring station → ✅.
- **`open-questions.md`:** added **OQ-16** (the M3 register pointer). **`learning-log.md`:** +2 lines
  (cheapest-first cascade; gate-the-write vs dedupe-after). **`INDEX.md`:** regenerated.
- **Nothing resolved.** Register stays OPEN; no invariant folded into `invariants.md` beyond the
  freshness fixes; no ADR drafted (awaits the owner's DM6/DM2 calls). First code: `MatchingAgent` Stage 1
  (RapidFuzz), failing test first with the App. B "Bronek/Bronisław" fixture.

## 2026-06-15 — review-architecture sweep (M3.S3 merged → entering M3.S4)
- **`reports/2026-06-15-architecture-review.md`:** new dated sweep. Findings: A1 DM5 resolved-but-framed-open
  (risk), A2 `task_type` label drift `"judging"`→`"judge"` (watch), A3 `overview.md` snapshot predates
  M3.S1–S3 (risk), A4 §3.3 confident-yes merge-rule shorthand (watch); B1–B3 the section-B owner
  resolutions (INV-2 deferred past M3, DM-rej remember, M3.S4 re-slice) reported pending PLAN_SHORT;
  C1–C4 S4a-bound (ADR 0004 fuller-MADR, gate-less Stage-3 egress, staging Expiry, store-chatty cascade).
- **Folded (as-built/already-authoritative drift only):** `proposals/m3-cascade-matching.md` — DM5 → ✅
  (PR #60), `"judging"`→`"judge"`, §3.3 confident-yes edge label; `open-questions.md` — OQ-16 DM5 struck,
  label fixed, DM7/DM-rej noted resolved-2026-06-15-pending-record; `overview.md` — snapshot moved to
  M3.S1–S3-built-proposal-only + S4a/S4b. `updated:` bumped on all three.
- **Reported, NOT written (authority lands at this session's wrap):** INV-2 re-point in `invariants.md`,
  DM7/DM-rej body strikes, the re-slice in PLAN_SHORT — the vault must not get ahead of its source of truth.
- **Nothing resolved unilaterally.** INV-8 correctly still live `[TEMPORARY]` (the flip is S4a's, test-first).

## 2026-06-15 — decompose-requirement: M3.S4a intercept-before-write (step-0)
- **`proposals/m3s4a-intercept-write-path.md`:** new step-0 decompose of the **backend** half of the
  milestone-closing session (UI is S4b). Designs the DM6 write-path refactor: a new Postgres `candidates`
  staging table, the cascade wired synchronously into the coordinator (embed-on-extract → Matching →
  Judge), Neo4j + `entity_mentions` writes moved to a human-accept endpoint; **INV-8 retired → INV-1
  enforcer** (+ proposed **INV-9**), test-first (the failing test replaces M2.S4's "two extractions → two
  nodes"). Nine-layer + nine-station pass; data-flow Mermaid; but-what-if (intra-batch dupes, review-gate
  TOCTOU, accept-path OQ-1 crash seam + status-flip-last idempotency, relation re-point on merge,
  rejected-as-default-suppression).
- **Open register OQ-17 / DM-S4a-1..5:** staging-table shape, INV-9 yes/no, resume marker under staging,
  **the evidence home** (focused `candidate_decisions` now vs full §4.2 `edit_history` — the main scoping
  call, may escalate to an ADR), retention. Mirrored to `open-questions.md`. ADR 0004 to author test-first.
- **Resolved inputs carried (not re-opened):** DM6 intercept-before-write, DM-rej remember rejections,
  INV-2 deferred past M3. `INDEX.md` regenerated. **Nothing resolved** — register stays open for the owner.

## 2026-06-15 — /review-pr §2 reconciliation folds (PR #62)
- The own-review §2 sweep found three decision-state homes lagging their now-recorded PLAN_SHORT
  decision. Folded: **`open-questions.md`** OQ-17 header `OPEN` → ✅ resolved (DM-S4a-1..5 struck);
  **`proposals/m3-cascade-matching.md`** → `status: accepted`, DM7/DM-rej register bodies + the Layer-1 /
  Layer-7 / Gaps-for-PO INV-2 mentions struck to Decision, register header `OPEN` → resolved;
  **`proposals/m3s4a-intercept-write-path.md`** → `status: accepted`, all five DM-S4a register entries +
  the Gaps-for-PO list struck to Decision, hand-off de-staled; **`invariants.md`** INV-2 schedule
  re-pointed from "M3 review-queue UI" to "deferred past M3" (the report B1 item, now due since PLAN_SHORT
  records it). Authoritative homes (PLAN_SHORT Decided S23) were already correct; this brings the vault
  framing-notes into agreement throughout their bodies, not just their banners.
