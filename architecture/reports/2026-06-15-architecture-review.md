---
type: review
slug: 2026-06-15-architecture-review
updated: 2026-06-15
status: living
related: ["[[invariants]]", "[[open-questions]]", "[[overview]]", "[[m3-cascade-matching]]", "[[candidate-lifecycle]]"]
---

# Architecture review — 2026-06-15 (M3.S3 merged → entering M3.S4)

**Scope.** Milestone-boundary sweep entering **M3.S4** (the milestone-closing session). Two jobs:
(1) clear the drift the Session-22 wrap flagged — DM5 now resolved+implemented (PR #60), the
`task_type` label, the §3.3 Stage-3 merge-rule clarification; (2) refresh M3 context for the
upcoming **S4a** step-0 decompose, including the three governance decisions the owner resolved at
this session's open (re-slice S4a/S4b; INV-2 consent **deferred past M3**; DM-rej = **remember
rejections**).

**Method.** Read the vault (`invariants`, `open-questions`, `overview`, `proposals/m3-cascade-matching`,
`state-machines/candidate-lifecycle`, glossary, INDEX); diffed vault claims against the merged code
(`agents/judge_agent.py`, `adapters/neo4j_repo.py`) and git (`git log -20`, PRs #56/#58/#60).

**Disclosure tier:** balanced (G=20 glossary terms). New terms defined inline; known ones linked.

**Bottom line.** The vault is **honest where it matters most** — `invariants.md` correctly still
carries **INV-8 as live `[TEMPORARY]`** (the `CREATE`-on-extract path is untouched at
`neo4j_repo.py:75/124`) and INV-1 as *not-yet-enforced*. That as-built honesty is exactly right
**one session before the flip** and needs no change until S4a witnesses it test-first. The drift is
in the **register/snapshot** layer: a resolved decision still framed open, a stale label, and an
overview that predates three merged sessions. No blockers; the findings are `risk`/`watch`.

---

## Findings

### A · Drift — vault claims vs reality

- **A1 · `risk` · DM5 is resolved + shipped but framed OPEN in the register.** PR #60 routes the
  JudgeAgent via the router (`judge_agent.py:155/179/183`, `weight="medium"`, `task_type="judge"`),
  exactly DM5's proposal (a). Yet `open-questions.md` OQ-16 (header + the DM5 line) and
  `proposals/m3-cascade-matching.md` (status banner line 11, DM5 body 222–227, hand-off line 321) all
  still say *"DM5 open"*. A reader scoping S4a would think the judge tier is unsettled. **Folded this
  sweep** (the proposal's own banner invited a later sweep to fold the ✅ markers inline) — see
  *Actions taken*.
- **A2 · `watch` · Label drift: `task_type="judging"` vs the code's `"judge"`.** The vault names the
  judge task `"judging"` in two places (`open-questions.md:353`, `proposals/m3-cascade-matching.md:224`);
  the code and spec §6.5 mapping use **`"judge"`** (`judge_agent.py`). S4a wires this routing call, so a
  stale label is a real foot-gun. **Folded this sweep.**
- **A3 · `risk` · `overview.md` "honest snapshot" predates three merged sessions.** Its *"Planned, not
  yet built (M3+)"* block still lists the whole M3 cascade as unbuilt, but **M3.S1/S2/S3 are merged**
  (PRs #56/#58/#60): RapidFuzz Stage 1, embedding Stage 2 + the pgvector foundation, and the JudgeAgent
  Stage 3 — all **proposal-only / unwired** (nothing in the coordinator calls them; mentions written
  `embedding=None`; INV-8 still live). The snapshot's value is being *honest*, so this is the one drift
  that most undercuts the note. **Folded this sweep** (snapshot moved to reflect "Stages 1–3 built,
  proposal-only; S4a wires + flips").
- **A4 · `watch` · §3.3 Stage-3 merge-rule clarification not mirrored in the vault's shorthand.** The
  spec was amended at M3.S3 (confident-*yes* rule: merge iff `match=true AND confidence>0.8`; a confident
  *no* is never a merge). The vault still uses the bare shorthand *"conf >0.8 → merge"* in the proposal
  data-flow (`m3-cascade-matching.md:129`) and `candidate-lifecycle.md:31`/the `auto-merge-proposed` def.
  Spec is authoritative and already correct; the vault just needs a one-line pointer so the shorthand
  isn't read as "high-confidence *no* merges." **Pointer added to the proposal** (candidate-lifecycle
  left for its S4a `living` finalisation, which rewrites that section anyway).

### B · Decisions resolved this session — authoritative home pending (report-only)

These three were resolved by the owner at this session's open. Their **authoritative home is
`docs/PLAN_SHORT.md` Decided**, written at this session's `/wrap-session` — so the vault must **not**
get ahead of its source of truth. Recorded here as findings; the **S4a decompose** folds them into the
design and `/wrap-session` records them, after which a later sweep folds the vault markers.

- **B1 · `risk` · INV-2 consent gate — re-point again, now "deferred past M3."** `invariants.md` INV-2,
  `proposals/m3-cascade-matching.md` DM7 (lines 38, 79, 256–260, 310), and `open-questions.md` OQ-16's
  DM7 line all currently say the consent gate **lands in the M3 §3.3 review-queue UI**. The owner
  **deferred INV-2 past M3** (2026-06-15) — persona-justified (single local user, full trust). So those
  homes will be drift the moment PLAN_SHORT records the deferral. **Action (at wrap / S4a):** re-point
  INV-2's "Enforced at" schedule from "M3 review-queue UI (DM7)" to "deferred past M3, revisit when
  remote/multi-user matters," keeping the as-built guard ("no-telemetry + egress only to the
  router-selected provider") unchanged. *Teaching note:* this is the **third** re-point of INV-2's
  landing target (M2.S2 → M2.S5 → M3 → deferred). A guard that keeps chasing the next milestone is the
  classic **fail-open-by-sequencing** smell ([[fail-closed]]); deferring it *explicitly with a persona
  rationale* is the honest fix — far better than a fourth silent slip.
- **B2 · `watch` · DM-rej resolved → "remember rejections."** The `rejected` terminal edge writes an
  evidence row the matcher consults before re-queueing (ties OQ-4 retention). Currently OPEN in the
  proposal DM-rej + OQ-16. Fold the ✅ at wrap. **Consequence for S4a:** the matcher now does a Postgres
  read *per candidate* to check rejection memory — see C2.
- **B3 · `watch` · M3.S4 re-sliced → S4a (backend) + S4b (frontend).** S4a lands the `candidates`
  staging table, cascade wiring, embed-on-extract, the accept/reject write-path, the **INV-8→INV-1
  flip + possible INV-9 + ADR 0004**, and finalises `candidate-lifecycle` to `living` — test-first. S4b
  is the React review-queue UI. The invariant flip is witnessed at the **backend/API** boundary (a test
  asserts extraction writes zero Neo4j nodes; the accept endpoint writes one), so S4a is a coherent
  green slice with **no empty-graph window**. `PLAN_SHORT` feature-list + the candidate-lifecycle note
  carry this; recorded for the decompose.

### C · Missing decision records + fresh "but what if" (S4a-bound)

- **C1 · `watch` · ADR 0004 (DM6 intercept-before-write) not yet written — correctly pending.** Not
  drift; the convention is the ADR + invariant fold land **with the S4a code, test-first**. Flag so the
  decompose scopes it. The ADR crosses a data-ownership boundary (the graph write moves stores/time), so
  per the meta-architect ADR rule it warrants the **fuller MADR form** (decision drivers + per-option
  pros/cons) and must state its accepted cost (graph empty until the author reviews). It should also
  capture the INV-2 deferral (B1) as a consequence, since the same pipeline is where the Stage-3 egress
  now fires gate-less.
- **C2 · `watch` · The cascade fires the Stage-3 cloud call at *extraction* time — with INV-2 deferred,
  every ambiguous candidate egresses story text gate-less.** Because §7 runs the cascade in the pipeline,
  Stage 3 (the JudgeAgent, a provider crossing) happens **before** the human ever sees the queue. The
  OQ-6 "fail-open by sequencing" window is now *persona-accepted* (B1) — but name it precisely: a batch
  ingest fires one cloud judge call **per ambiguous candidate**, each carrying ±context story text. S4a's
  design should at least make that egress **observable** (it already lands an `llm_calls` row per call —
  INV-5) and the ADR should record it as an accepted cost.
- **C3 · `watch` · Staging accumulation (Expiry, OQ-4 again).** With intercept-before-write, a candidate
  staged but never reviewed lives in the new `candidates` table indefinitely. The empty **Expiry**
  station (OQ-4) now has a concrete second instance (after orphaned sandboxes + LLM logs). Not a blocker
  at single-user PoC, but the S4a migration is the moment to *decide* retention rather than inherit an
  unbounded table.
- **C4 · `watch` · DM-rej memory + the store-down→503 cross-cutting compound.** B2 adds a per-candidate
  Postgres read (rejection memory) on top of the per-candidate embedding read (Stage 2) and the staging
  writes — so the cascade is markedly more store-chatty than M2.S4's path. The existing cross-cutting
  *"store-down → 503 + Neo4j lifespan-close"* item now bites harder: a connectivity blip mid-cascade
  should surface as **503**, fail-closed toward the human, never a silent "new entity" (which would
  smuggle the duplicates INV-8's retirement is meant to kill back in). Natural to land **with** the S4a
  write-path refactor.

### D · Structural rot

- **`watch` · `candidate-lifecycle.md` is the lone `state-machine` note and still `status: draft`.** Not
  rot yet — it's correctly draft until S4a makes it real. Listed so the S4a checklist remembers to flip
  it to `living` *as the flip lands*, not before. No orphan/ghost-link issues found; INDEX is current as
  of 2026-06-11 and will want a regenerate after the S4a notes land.

---

## Actions taken this sweep (vault-only, as-built/already-authoritative drift)

Folded only drift with an **already-authoritative basis** (merged code / merged spec amendment / merged
PR). Everything whose authority lands at this session's wrap (section B) was **reported, not written**.

- `proposals/m3-cascade-matching.md` — DM5 folded to ✅ resolved (PR #60); `task_type` `"judging"`→`"judge"`
  (A1/A2); a §3.3 confident-yes pointer added to the data-flow (A4).
- `open-questions.md` — OQ-16: DM5 struck/✅; `"judging"`→`"judge"`; the three section-B owner resolutions
  noted as *resolved 2026-06-15, authoritative record pending PLAN_SHORT @ wrap*.
- `overview.md` — the as-built snapshot moved to reflect M3.S1–S3 merged (proposal-only/unwired), INV-8
  still live (A3).
- `CHANGELOG.md` / `learning-log.md` — appended.

---

## Concepts worth studying

- **Fail-open by sequencing** — a control that ships *after* the risk it governs is, in the window
  between, no control at all. INV-2 has now slipped its landing target three times; the architectural fix
  for an indefinitely-deferred guard is to *defer it explicitly with a stated rationale* (what we did),
  not to keep re-pointing it at the next milestone. Worth reading alongside *secure-by-default*.
- **Intercept-before-write vs write-then-dedupe** (the DM6 fork) — the general pattern is *validate at
  the gate vs clean up after the fact*. Gating keeps the store always-clean at the cost of a staging
  buffer + a commit path; write-then-dedupe keeps writes cheap at the cost of a dirty store and a
  reconciliation job. Story Forge chose gating because INV-1 makes a dirty graph unacceptable. The same
  tradeoff recurs as *schema-on-write vs schema-on-read*.
- **Witnessing an invariant flip with a test** — INV-8→INV-1 isn't a config toggle; the discipline is to
  *replace* the test that pinned the old contract ("two extractions → two nodes") with one that pins the
  new ("no node without a human action") in the same change, so `main` is never in a state where matching
  exists but the old guard still asserts. This is the as-built-honesty rule applied to a contract change.
