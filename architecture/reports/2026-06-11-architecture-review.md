---
type: review
slug: 2026-06-11-architecture-review
updated: 2026-06-11
status: living
related: ["[[overview]]", "[[invariants]]", "[[open-questions]]", "[[2026-06-09-architecture-review]]", "[[trust-boundary]]", "[[fail-closed]]", "[[cascade-matching]]", "[[state-machine]]"]
---

# Architecture review — 2026-06-11 (M2→M3 roll catch-up + forward sweep)

> **Run at the M2→M3 milestone boundary** as gate 2 of the roll (the other gate, the cross-cutting
> curation, is a `docs/PLAN_SHORT.md` edit, not a vault one). Two jobs: (1) a **drift catch-up** — the
> vault's last sweep (`[[2026-06-09-architecture-review]]`) predates **M2.S5** (PR #51, graph viewer +
> agent-activity panel + `latency_ms`) **and** **M2.S6** (PR #53, real-provider smoke + the §6.7
> key-leak doc + the model-dropdown deferral), so the update-in-place notes lag **two** merged
> sessions; (2) a **forward lens** onto **M3 — the cascade dedupe** (§3.3), framing what the
> `decompose-requirement` step-0 (the next action this session) must settle before any M3 code.

**Scope.** As-built M2.S5/S6: `frontend/src/features/{graph-viewer,agent-activity}/`, the
`latency_ms` migration (`2026_06_11_0956…`) + its capture in `adapters/llm/{router,cost,postgres_cost_store}.py`,
`scripts/check_openrouter.py`, the `backend/AGENTS.md` smoke/key-leak doc, vs the vault's claims
(`overview.md`, `invariants.md`, `open-questions.md`, `INDEX.md`). Forward: `docs/PLAN_LONG.md` M3 +
spec §3.3/§9 vs INV-1/INV-8 and the still-empty `state-machines/` + `components/`.

Severity legend: **blocker** (resolve before dependent work) · **risk** (will bite if unaddressed) ·
**watch** (track; not yet urgent).

## Headline

**No blockers.** This is the expected milestone-boundary lag: the *regenerated* surface (`INDEX.md`)
and the source notes need a catch-up because two sessions merged since the last sweep. The substantive
finding is **one `risk` on a security invariant**: **INV-2's consent gate was deferred (ADR 0003 D5)
with M2.S5 named as its landing spot — and M2.S5 came and went without it**, so the gate is now
*unscheduled*, and the M2.S6 smoke **actually fired real paid egress** (Ollama Cloud + an OpenRouter
model) across the only real [[trust-boundary]] with no consent gate present — the OQ-6 "fail-open by
sequencing" window is no longer hypothetical, it occurred. The rest is freshness drift (`overview.md`
two sessions stale; INV-5/OQ-9 latency still future-tensed though built; INDEX "Next: M2.S5"). The
forward lens finds the M3 plan **aligned** with the invariants — M3 is where INV-1 finally gets its
enforcer and INV-8 is lifted — but it is **branchy**, and the candidate-lifecycle state machine it
needs is still undrawn. That is exactly the `decompose-requirement` step-0 queued next.

## 1. Drift — vault vs reality

- **`risk` — INV-2's consent gate lost its landing milestone.** `invariants.md` INV-2 reads: *"The
  consent UI the invariant demands ('sending fragment to Anthropic, OK?') is still M2.S5."* **M2.S5
  shipped** (PR #51) — a **read-only** graph viewer + agent-activity panel: *surfacing* (which
  tier/model/cost ran), **not** the egress *consent gate*. A grep of `frontend/src` finds no consent /
  egress-confirmation control. So INV-2's guard is still the honest-but-narrow "no-telemetry +
  router-selected-provider egress", and the consent UI is now **unscheduled** — the ADR-0003-D5
  deferral pointed at a milestone that passed. Worse, the **M2.S6 smoke fired real paid calls** through
  `OpenRouterProvider` (and Ollama Cloud) — text crossed the trust boundary with no gate, which is the
  precise scenario OQ-6 framed as fail-open-by-sequencing. At PoC scale on the author's own text this
  is *accepted* (no security-sensitive data, D5), but the **schedule** is now dishonest. **Recommend
  (owner):** re-point INV-2's "still M2.S5" to a real home — the natural one is the **M3 §3.3
  review-queue UI** (the first rich human-gate surface) or the deferred §6.5 model-override work, and
  add an as-built note that a real paid call has now occurred gate-less (so the deferral is read as a
  live, re-dated decision, not a forgotten one). *I did not edit it — report-only; see Hand-off.*

- **`risk` — `overview.md` is two sessions stale (`updated: 2026-06-09`).** Its "Current as-built
  state" header says **"Built and merged (M0 → M2.S3)"** while its own body already lists M2.S4 — and
  **M2.S5 + M2.S6 are both merged** yet sit under **"Planned, not yet built (M2.S5 → M2.S6)"**. The
  nine-station table's **Monitoring** row still reads *"the agent-activity panel that surfaces them is
  M2.S5"* (future) — it is built. This is the system-altitude note a newcomer reads first; a stale
  snapshot here misorients. **Recommend:** header → "M0 → M2.S6"; move M2.S5 (viewer + panel +
  `latency_ms`) and M2.S6 (real-provider smoke, dropdown deferred) into "built and merged"; trim the
  planned list to **M3**; flip Monitoring to `✅` (panel built). *Note: the `decompose-requirement`
  step-0 that follows will itself rewrite overview/invariants for M3 — folding this freshness fix into
  that same pass is the low-churn path.*

- **`watch` — INV-5 + OQ-9 still future-tense `latency_ms` though it is built.** INV-5's latency clause
  and OQ-9's resolution both say the column + router capture *"land in M2.S5"*. They **landed**: Alembic
  `2026_06_11_0956-…_add_latency_ms_to_llm_calls.py`, captured around `provider.complete` in
  `router.py`, recorded by `postgres_cost_store.py`. **Recommend:** flip both clauses to as-built
  ("M2.S5, PR #51"), same as the 06-09 sweep flipped the OQ-10 gap clause.

## 2. Source-of-truth conflicts

- **`watch` — INDEX "Next: M2.S5" vs reality (M3 next).** `INDEX.md` "Next steps" item 10 still reads
  *"Next: M2.S5"* with M2.S5 framed as upcoming. M2.S5 **and** M2.S6 are merged; M3 is next. INDEX is
  **regenerated** mode, so this sweep regenerates it (advance the run-log to M2.S5/S6 done + M3-next,
  register this report and the two new OQs). No conflict survives the regenerate.
- **No host-doc conflicts.** `docs/PLAN_SHORT.md` (the authoritative roadmap) correctly has M2 done +
  M3 next; spec §3.3/§9 own the cascade. The vault is the side that drifted, as designed.

## 3. Missing / unrecorded decision records

- **None requiring a new ADR yet — but two M2→M3 roll decisions are absent from the vault** (recorded
  only in `docs/PLAN_SHORT.md` Decided + `docs/PLAN_LONG.md`):
  1. **The §6.5 model-override dropdown deferral** — a *feature*, deferred because it collides with
     **INV-7** (routing is system-derived, never caller-asserted; that near-miss was deliberately
     closed in M2.S2). Building it needs an INV-7/spec reconciliation ("system-derived *unless* the
     user explicitly overrides") + router plumbing + a preferences store. This is a **likely future
     ADR** (it amends an invariant). This sweep folds it as a **framed open question** (OQ-14), not a
     resolution — the human owns the INV-7 reconciliation. The `decompose-requirement` step-0 may
     deepen it into its own register entry.
  2. **The observability / operational-logging gap** — the backend emits **no** operational logs today,
     so INV-6's "API keys never logged" is currently *vacuously true* (see Concepts). Recorded as a
     later need in `docs/PLAN_LONG.md`. Folded here as OQ-15 (framed). The M2.S6 key-leak grep becomes
     the redaction regression guard the moment logging lands.

## 4. Invariant violations & near-misses (fresh "but what if")

- **`watch` — INV-8 (no-dedupe) still correctly enforced, and M3 is its scheduled end.** `Neo4jRepo`
  still `CREATE`-not-`MERGE`; the coordinator does no matching. INV-8 is a *temporary* invariant
  superseded by **INV-1** when M3 begins. The "but what if" for the roll: the moment MatchingAgent
  lands, **INV-8 must be lifted in the same change that introduces the first matching write** — a
  half-state where matching exists but INV-8's no-dedupe test still guards `CREATE` would be
  contradictory. The decompose step-0 should make the INV-8→INV-1 hand-off an explicit, tested
  transition, not a silent deletion.
- **`risk` (forward) — INV-1 (human-in-the-loop) finally gets an enforcer in M3, and it is the
  product's crux.** INV-1 has been "the contract M3 must honour" with *no code holding it* since the
  vault was seeded. M3's §3.3 Stage 4 review queue is that enforcer. The "but what if" the decompose
  must answer: a candidate must be **unable** to reach `merged`/`created` except via a human action —
  the guard belongs on the state transition, [[fail-closed]] (on any uncertainty, fall to the human,
  never auto-merge). This is the first time a missing-guard invariant becomes live code; it deserves
  the candidate-lifecycle state machine drawn *before* the write path.
- **`watch` — INV-6 redaction-before-logging, still vacuous, carried forward.** Unchanged from prior
  sweeps and now explicit (OQ-15): the redaction middleware INV-6 names doesn't exist because nothing
  logs. The guarantee is real only once logging lands. M3 adds more agents (matching/judge) — a likely
  place for the first diagnostic log line, which is the moment redaction must precede it.

## 5. Structural rot

- **`watch` — `state-machines/` and `components/` are still empty, and M3 is the trigger for both.**
  The candidate lifecycle (`extracted → matched | ambiguous → judged → {merge-proposed | new-proposed}
  → (human) → {merged | created | rejected}`) is sketched in `overview.md` Layer 5 but **undrawn**; M3
  is the first time it becomes code, so it is the natural **first `state-machines/` note** (drawn by the
  decompose step-0). OQ-C (first `components/` note — cascade / router / ingest-job) is still open; the
  cascade is now the obvious candidate. Neither is rot yet — but the roll is the moment they earn
  drawing.
- **No orphans / ghost references / stale ADRs.** Glossary count (20) matches the on-disk
  glossary-term notes; proposals and reports all reachable; no dangling wikilinks found in the notes
  read this sweep. The `cascade-matching` glossary term + the m2s3 proposal are the live forward
  anchors for M3.

## 6. Forward lens — M3 plan vs architecture

The owner's roll plan (this session) is **two gates then M3 first feature (MatchingAgent)**. Checked
against the vault: **aligned, no contradiction.** M3 is where INV-1 lands, INV-8 lifts, the candidate
state machine is drawn, and the embedding read path switches on (`postgres_repo.py`'s `NULL AS
embedding` → real `vector(768)` + `pgvector` + `register_vector_async`). The forward lens surfaces
**what the `decompose-requirement` step-0 must settle**, not conflicts:

- **The candidate-lifecycle state machine** (the first `state-machines/` note) — terminal states, the
  human gate as INV-1's guard, and where the **effect** (an `edit_history`/audit row — INV-3) is born
  on each transition.
- **The INV-8 → INV-1 hand-off** as a tested transition (see §4), not a deletion.
- **Match thresholds are Policy with no home** — the §3.3 Stage 1 RapidFuzz cutoff + Stage 2 embedding
  cosine are nine-station *Policy* values the vault doesn't record anywhere yet; the decompose should
  frame them (and whether they're config or constants).
- **The embedding model + `pgvector` wiring** — a Data-layer change carrying a migration (start writing
  the column) and a dependency add (`pgvector`, ≥14-day soak via `/add-dependency`); spec §6.4/§9 place
  embeddings under MatchingAgent Stage 2, not ExtractionAgent.
- **The JudgeAgent model tier** (§3.3 Stage 3) — a [[model-tier-routing]] decision (heavy → cloud_strong?)
  with INV-5 cost implications.
- **The §3.3 review-queue UX** (Stage 4) — the first rich human-gate surface, and the natural home to
  finally land INV-2's consent gate (§1).

## 7. Concepts worth studying (the teaching payoff)

- **Vacuous truth (prawda pusta) as a hidden-gap smell.** INV-6 "API keys never logged" is *true* right
  now — but only because **nothing logs at all**. A guarantee that holds because its precondition never
  occurs is *vacuously* satisfied; it tells you nothing about whether the system would hold the line
  once the precondition arrives. The architectural move is to **name the vacuity** (OQ-15) so the
  guarantee is re-examined the moment logging lands, rather than mistaking "the grep is clean" for "the
  redaction works". This is why the M2.S6 key-leak check is framed as a *future regression guard*, not
  a present proof.
- **Accepted deferral vs silent drift.** A deferral is legitimate when it is *dated and re-pointable*
  (ADR 0003 D5 deferred INV-2's consent gate to M2.S5 — a decision a reader can audit). It becomes
  **silent drift** the moment its landing milestone passes unmet and nobody re-dates it: the gate is
  still "coming in M2.S5" in the note, but M2.S5 is gone. The discipline is to treat a deferral's
  target like any other commitment — when it slips, re-point it on the record (§1), don't let it
  decay into a perpetual "later". The `review-architecture` sweep firing at a milestone boundary is
  exactly the mechanism that catches a slipped deferral before it rots.
- **The temporary invariant and its hand-off (INV-8 → INV-1).** A *deliberately temporary* invariant
  (INV-8, no-dedupe) is unusual — most invariants are forever. Its value is in making the eventual
  removal a **planned, tested transition** rather than a quiet `MERGE`-creep. Worth studying how a
  state-machine models the *replacement* of one contract by another at a milestone edge: the guard that
  enforced "always CREATE" is swapped for the guard that enforces "never merge without a human"
  ([[state-machine]]), and the test suite should witness the swap, not just the new state.

## Hand-off

- **No blockers.** One `risk` is a security-invariant **schedule** that slipped (INV-2 consent gate;
  the egress window is now real, but accepted at PoC scale per ADR 0003 D5) — needs the owner to
  **re-point it**, not to build it now. The other `risk` (overview staleness) and all `watch` items are
  freshness, best folded into the `decompose-requirement` step-0 that rewrites overview/invariants for
  M3 anyway.
- **Vault edits this sweep makes** (trail + regenerated only, never source-note content, never code):
  regenerates `INDEX.md` (M2.S5/S6 done, M3 next, this report + OQ-14/OQ-15 registered); adds **OQ-14**
  (model-override dropdown, INV-7-touching, framed) and **OQ-15** (observability/operational-logging,
  INV-6-vacuity, framed) to `open-questions.md` — which also discharges the `docs/PLAN_SHORT.md`
  cross-cutting "reflect the M2→M3 roll decisions in the vault" item; appends `learning-log.md` +
  `CHANGELOG.md`. It does **not** edit `overview.md` / `invariants.md` — those are recommended below for
  owner approval (report-only discipline, matching the 06-09 sweep).
- **Recommended for the owner (the source-note drift fixes; fold into the decompose step-0 pass):**
  1. `invariants.md` INV-2: re-point the consent gate from "still M2.S5" to a real home (M3 §3.3
     review-queue UI / the §6.5 dropdown work) + an as-built note that a real paid call has now occurred
     gate-less (M2.S6 smoke).
  2. `invariants.md` INV-5 + `open-questions.md` OQ-9: flip the `latency_ms` clauses from "lands in
     M2.S5" to as-built (PR #51).
  3. `overview.md`: header → "M0 → M2.S6"; M2.S5 + M2.S6 into "built and merged"; planned list → M3;
     Monitoring station → `✅` (panel built); refresh `updated`.
- **Decisions still the owner's (framed, not resolved):** OQ-14 (the INV-7 "system-derived unless
  overridden" reconciliation the dropdown needs); OQ-15 (log retention/redaction posture once logging
  lands — ties OQ-4 Expiry). And all the M3 design calls in §6, which are the `decompose-requirement`
  step-0's to frame.
- **Next action this session:** `meta-architect:decompose-requirement` step-0 on the M3 cascade — it
  draws the candidate-lifecycle state machine, frames the §6 decisions, and folds the §1 freshness
  fixes into overview/invariants as it goes.
