---
type: review
slug: 2026-06-25-architecture-review
updated: 2026-06-25
status: living
related: ["[[overview]]", "[[project]]", "[[invariants]]", "[[open-questions]]", "[[m4-multi-story]]", "[[m4-s3b-graph-mutations]]", "[[m4-s3c-manual-tagging]]", "[[2026-06-20-architecture-review]]"]
---

# Architecture review — 2026-06-25 (V1-complete → Public-readiness re-sync)

**Scope.** Full vault sweep, run at the **V1 → Public-readiness milestone roll** so the vault — part
of what a stranger reads — is honest before the README/doc-polish sessions draw on it. Since the last
snapshot ([[2026-06-20-architecture-review]], the pre-S3b re-sync) the rest of M4 shipped: **M4.S3b**
merge/delete/undo (#102/#105/#107, ADR 0007), **M4.S3c** manual tagging (#111/#115/#117, ADR 0008),
and the **narrowed multi-story** slice (#128/#130) — and the **multi-story live smoke PASSED**
(Session 54, #133), so **V1 is feature-complete**. A spec amendment also landed in between: **§7 Step 3
PreNER marked deferred/dormant** (Session 57, PR #138). This sweep is the overdue as-built diff plus the
reconcile of the vault to that spec amendment.

**Headline.** No **blockers**. Two `risk`s, both **drift the vault was carrying and both fixed on sight
in this sweep**: (1) the vault framed the spaCy **PreNER baseline as a live pipeline stage**
(`PROJECT.md`, `overview.md`) where the spec was just amended to *deferred/dormant* — I verified against
the code that it is genuinely dormant and reconciled the vault; (2) `overview.md`'s as-built snapshot
**stopped at M4.S3a** and framed M4 as "in progress" though three more slices shipped and V1 is done —
the **fourth recurrence** of the doc-freshness-as-a-state-machine drift. `watch`-class follow-ons
(stale frontmatter date, a build-pending proposal banner, the regenerated INDEX) folded in the same
pass. The invariant/state-machine layer is **honest and code-verified** — INV-9's six witnessed
writer-paths and INV-3's executed undo match what the code actually does.

---

## 1. Drift — vault vs reality

- **The vault framed PreNER as a live pipeline stage — `risk` (fixed).** `PROJECT.md` classification
  read *"the §7 ingest pipeline (chunking → PreNER → extraction → …)"* and `overview.md`'s "So today"
  paragraph listed *"produces deterministic candidate spans"* as a live step before LLM extraction.
  Spec **§7 Step 3 was amended to deferred/dormant** (2026-06-25, PR #138). **Verified against code**
  (not just the spec): `agents/extraction_agent.py` passes the `known_entities`/PreNER-hint param
  **empty** ("M2.S4 wiring … deferred until a real eval exists"), and the `ExtractionCoordinator`
  constructs no PreNER call — the live `/extract` is **LLM-only on raw paragraph text**. **Fixed:**
  `PROJECT.md` classification + as-built parenthetical and `overview.md`'s M2.S1 bullet + "So today"
  paragraph now state PreNER is *built but dormant — §7 Step 3*, pointing at the `docs/BACKLOG.md` eval
  and the `docs/PLAN_LONG.md` flywheel. This is the vault home the host-repo stop-and-amend (Session 57)
  deliberately *routed here* because the vault is writer-restricted to the `meta-architect:*` skills
  (ADR 0002) — this sweep is the sanctioned reconcile.

- **`overview.md` as-built stops at M4.S3a; frames M4 "in progress" — `risk` (fixed).** `updated:
  2026-06-20`. Its M4 block ended at S3a and its closing **"Next — M4.S3b"** named S3b/S3c/multi-story
  *and the world graph* as upcoming PoC work. **Since then:** S3b (#102/#105/#107), S3c
  (#111/#115/#117), and narrowed multi-story (#128/#130) **all shipped**, the V1 smoke **passed**
  (#133), and the **world graph was moved OUT of PoC** to `docs/BACKLOG.md` (Sessions 44/49). This is
  the **fourth** time `overview.md` has drifted in exactly this way — an update-in-place note that
  nobody re-reads between milestone rolls (the 2026-06-17 and 2026-06-20 sweeps each fixed the prior
  two). **Fixed:** a complete M4 *built* block (S3b/S3c/multi-story, each with PRs + the invariant/ADR
  consequence), the "Next" rewritten to *V1 feature-complete → Public-readiness → Graph-quality → V2
  Editing* with the world graph correctly reframed as post-PoC, and the date bumped. Decision-independent
  honesty, folded on sight.

- **`invariants.md` frontmatter date lags its body — `watch` (fixed).** `updated: 2026-06-20`, but the
  body carries S3b-be2 (5th INV-9 instance, the undo executor), S3c (6th instance, tag-as-new-entity),
  and the INV-3 *executed* section — content from builds dated 2026-06-20…06-22 (ADR 0007/0008). The
  body is **honest** — I verified the INV-9 grep guard against the code (`grep` for
  `create_entity / add_alias / create_relation / update_entity / delete_relation / delete_entity` →
  all defined in `adapters/neo4j_repo.py`, reachable only from `CandidateReviewService` /
  `RelationReviewService` / `EntityEditService`, and the coordinator constructs with **no** graph
  writer). Only the freshness stamp drifted (the same `watch` the last sweep flagged for three notes).
  **Bumped to 2026-06-25, body unchanged.**

- **`m4-multi-story.md` reads build-pending though multi-story shipped — `watch` (fixed).** Status is
  correctly `accepted` (a proposal's terminal), but its hand-off — and the INDEX row — read *"Next:
  §8.4/§3.3 amendment → build."* Backend #128 + frontend #130 shipped, the §8.4/§3.3 amend landed
  (#119), and the V1 smoke passed (#133). Same build-pending drift the 2026-06-20 sweep fixed for
  `m4-entity-editing`. **Fixed:** a BUILT banner (be #128 / fe #130 / smoke #133), pointing forward to
  the Public-readiness milestone.

- **INDEX priority-queue + proposal rows stale — `watch` (self-healing).** "Next steps" item 16 said
  *"Next: M4"*; the m4-multi-story row said *"Next: …amendment → build"*; the 2026-06-20 review was
  tagged *"current health snapshot."* INDEX is a **regenerated** note — this sweep regenerates it (the
  multi-story row → BUILT/V1-complete, the 2026-06-20 row → superseded, a new 2026-06-25 snapshot row,
  new Next-steps items 26–27, glossary still 28), so no manual debt is owed; flagged only so the reader
  knows the pre-regen INDEX lagged by a milestone.

## 2. Source-of-truth conflicts

- **None found.** The vault references the spec/PLAN/code throughout; the product ADRs 0004–0008 live in
  `docs/decisions/` (their authoritative home), the vault `decisions/` folder stays empty by design.
  The multi-story resolution names `docs/PLAN_SHORT.md` Decided + `[[m4-multi-story]]` as the homes and
  references them. No note claims authority over a fact another owns. The one fact that *moved* — PreNER's
  pipeline status — has a single authority (spec §7 Step 3); the vault now references it rather than
  asserting a contradicting "live stage" reading.

## 3. Missing decision records

- **None.** The major code-visible calls since the last sweep all have homes: **S3b** merge/delete/undo
  (the compound-undo contract + the §10-q2 resolution) → **ADR 0007**; **S3c** manual-tagging storage
  model + INV-9 reword → **ADR 0008**; **narrowed multi-story** was *deliberately ADR-free* — DM-MS-1
  *removes* a would-be data boundary by deriving membership rather than storing it, so it minted no new
  invariant or trust-boundary crossing (recorded in `[[m4-multi-story]]` + `docs/PLAN_SHORT.md` Decided
  S50). The PreNER amendment is a spec change (§7 Step 3), not a code decision — no ADR owed. Decision
  coverage is clean.

## 4. Invariant violations & near-misses

- **INV-9 holds — code-verified.** All six graph-writing symbols
  (`create_entity / add_alias / update_entity / create_relation / delete_relation / delete_entity`)
  live in `adapters/neo4j_repo.py` and are reachable only from the three human-reached services
  (`CandidateReviewService`, `RelationReviewService`, `EntityEditService` — the last home to merge,
  delete, tag-new-entity, and undo). The `ExtractionCoordinator` constructs with **no** graph writer
  (grep clean). No automated stage touches Neo4j. No violation.
- **The "find every graph writer" grep now spans two services — `watch`, not a violation.** The
  writer set is six symbols across `RelationReviewService` (edges) and `EntityEditService` (nodes +
  edges + the undo executor that *re-uses* the writers in reverse). INV-9's body documents this and the
  guard is correct; the standing cost is that a future reviewer's "where is the graph written" sweep
  must check **both** services, not one. Documented, accepted.
- **INV-3 is now *executed*, not just substrate — verified.** S3b-be2 shipped the undo executor
  (`EntityEditService.undo_last` → `POST …/graph-edits/undo`), so a merge/delete's grouped before-image
  is genuinely reversible, with a drift check that refuses an undo over since-changed state (a
  [[lost-update]] in reverse → 409). The honest residual risk INV-3 now guards — *before-image
  completeness* (a partial snapshot is a non-reversible op masquerading as reversible) — is named in the
  invariant body. No near-miss beyond that documented one.

## 5. Structural rot

- **Orphans / ghost links — none.** The notes re-synced this sweep (`overview`, `project`, `invariants`,
  `m4-multi-story`, INDEX) carry resolving `related` edges and `[[wikilinks]]`; the new report links the
  notes it touched and the prior snapshot. No dangling refs introduced.
- **Stale ADRs — none in-vault.** The product ADRs 0004–0008 live in `docs/decisions/`; INV-8 stays
  correctly `RETIRED` with its history preserved. The only "staleness" found was the freshness-date lag
  (§1) and the build-pending proposal banner (§1), both folded — neither is structural rot, both are the
  update-in-place freshness gap.

## 6. Fresh "but what if" — the Graph-quality milestone boundary

V1 is feature-complete, so the forward edge cases are inputs to the **Graph-quality** milestone (the
next *build* milestone, which opens with a triage over the 10 Session-54 findings in `docs/BACKLOG.md`).
Recorded so they have a tracked home (→ [[open-questions]] OQ-28); the milestone owns *resolving* them:

- **Auto-chunker silent content-loss (the most serious — already in `docs/BACKLOG.md`).** A structuring
  pass that drops input text **without a signal** is the worst failure class — *silent* data loss. The
  Session-54 smoke surfaced it and had **no clean recovery path** because neither **delete-and-replace**
  nor **delete-story** exists (the graduated-urgency cross-cutting item). The fail-closed shape worth
  designing: structure must *account for every input paragraph* (a conservation check — chars/paragraphs
  in == represented out, or an explicit, surfaced diff), so a drop is loud, not invisible.
- **Membership-derivation under *delete* — the cross-store read seam.** Narrowed multi-story **derives**
  per-story membership from `entity_mentions`. A *merge* re-points those mentions (S3b covers it), but a
  whole-entity **delete** removes them (`delete_entity_mentions`) — confirm a deleted entity vanishes
  cleanly from *every* story's `scope=story` membership view with no ghost node/edge in the §3.4 toggle.
  Likely already correct (mentions cascade on delete), but it is the OQ-1 two-store seam on the
  *membership-read* side and worth an explicit check when delete-story lands.

## Concepts worth studying

- **Doc-freshness as a state machine (fourth occurrence — the pattern is now proven).** `overview.md`
  has drifted in the *identical* way at four milestone boundaries, each time because an update-in-place
  note has no forcing function between rolls. The lesson is structural, not "remember harder": **the
  milestone-roll sweep IS the forcing function** — and four data points are strong evidence toward the
  still-open ADR-0002 question of wiring `review-architecture` into the roll ritual. Reading: the idea
  that a *document* has a lifecycle with transitions and guards exactly like the systems it describes,
  and that "edited but not re-stamped" is an unguarded transition.
- **Derived scope vs stored key (the multi-tenancy/membership split).** The narrowed multi-story slice
  rests on keeping per-story *membership* **derived** (a read-time filter over `entity_mentions`) while
  `project_id` is the **stored** tenancy key. It is a clean, small example of deliberately choosing
  *where the source-of-truth line sits*: a second stored copy would be a sync liability ([[materialization]]
  you don't want), so the slice needs almost no new persistence. Worth internalising that "seed scope
  (project — what might recur) ≠ membership scope (story — what occurred here)" is a modelling decision,
  not an implementation detail.

---

_Report-only. No code or config was touched. This sweep also re-synced the derived/strategic notes it
found stale (the architect's standing re-sync mandate): `overview.md` (PreNER framing + the M4 as-built
block + the "Next" + date), `PROJECT.md` (as-built parenthetical + the pipeline-classification PreNER
phrase + date), `invariants.md` (frontmatter date; body code-verified, unchanged), the `m4-multi-story`
BUILT banner, and INDEX regenerated. Trail updated: [[open-questions]] (OQ-28, the Graph-quality forward
"what if"), [[learning-log]] + [[changelog]] appended._
