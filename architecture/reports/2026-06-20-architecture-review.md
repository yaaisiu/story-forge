---
type: review
slug: 2026-06-20-architecture-review
updated: 2026-06-20
status: living
related: ["[[overview]]", "[[invariants]]", "[[open-questions]]", "[[m4-entity-editing]]", "[[candidate-lifecycle]]", "[[relation-lifecycle]]", "[[2026-06-17-architecture-review]]"]
---

# Architecture review — 2026-06-20 (pre-M4.S3b re-sync)

**Scope.** Full vault sweep, run at the owner's request **before the M4.S3b decompose** so the
architect reads current state. Since the last snapshot ([[2026-06-17-architecture-review]], the
M3→M4 roll) three M4 slices shipped: **M4.S1** inline highlights (backend #81 / frontend #86),
**M4.S2** entity side panel (#89 / #91), and **M4.S3a** entity & relation editing — the **first M4
*write* slice** (backend #96 / frontend #98, ADR 0006). This is the overdue as-built diff plus a
forward "but what if" over the M4.S3b boundary (entity↔entity merge + re-point + delete + undo).

**Headline.** No **blockers**. The invariant/state-machine layer is honest and current — the S3a
decompose + build correctly folded the INV-9 rewording, the candidate/relation lifecycle extensions,
OQ-23's resolution, and ADR 0006. The one **risk** is the recurring one: `overview.md`'s as-built
snapshot **stops at M3** — it lists every M4 slice (highlights, side panel, editing) as *future
"Next — M4" work* though all three shipped. Three state/invariant notes carry **current bodies under
stale frontmatter dates** (`watch`). Nothing here gates the S3b decompose; it is the doc-freshness
hygiene the roll sweep flagged for INV-2/latency and again for `overview.md` at the last roll.

---

## 1. Drift — vault vs reality

- **`overview.md` is ~6 sessions stale — `risk`.** `updated: 2026-06-17`. Its "Built and merged"
  list ends at M2.S6 + the M3 cascade; its closing **"Next — M4"** block names *"inline highlights,
  side panel, manual annotation, properties/relations edit, multi-story, world graph"* as upcoming.
  **M4.S1 / S2 / S3a all shipped since** (PRs #81/#86, #89/#91, #96/#98). This is the same
  **doc-freshness-as-a-state-machine** failure the 2026-06-17 sweep fixed for the M3 block (an
  update-in-place note drifts exactly when nobody re-reads it). **Fixed in this sweep:** a new
  *Built (M4 so far)* block + the "Next" reduced to the remaining M4 work (S3b merge/delete/undo →
  S3c spans → multi-story + §3.4 → world graph). Decision-independent honesty, folded on sight.

- **Frontmatter dates lag current bodies — `watch` (×3).** `invariants.md` (`updated: 2026-06-15`),
  `candidate-lifecycle.md` (`updated: 2026-06-15`), and `relation-lifecycle.md` (`updated: 2026-06-18`)
  all carry **M4.S3a / M3.S4e** body content (INV-9 third instance + ADR-0006 refs; the committed-node
  edit self-transition; the M4.S3a edit-path section) under a date that predates it. Content is
  honest; only the freshness stamp drifted — these notes were edited at the S36 decompose / S37 build
  without a date bump. **Bumped to 2026-06-20 in this sweep** (body unchanged).

- **`m4-entity-editing.md` reads build-pending though M4.S3a is complete — `watch`.** Status is
  correctly `accepted`, and the DM-S3a-3 build update + data-flow build note are folded — but the
  **Hand-off** section still says *"build M4.S3a-be test-first"* and the proposal nowhere records that
  **S3a-fe shipped** (PR #98) or the lone read-side deviation (`language` on `EntityDetailResponse`).
  **Fixed:** a BUILT banner appended (be #96 / fe #98), pointing forward to S3b. (A proposal has no
  "built" status — `accepted` is the right terminal; the banner carries the as-built note.)

- **INDEX priority-queue item 21 stale — `watch` (self-healing).** "Next steps" item 21 ends *"build
  M4.S3a-be test-first."* S3a-be **and** S3a-fe shipped; M4.S3a is complete. INDEX is a **regenerated**
  note — this sweep regenerates it (new items for S3a-be/fe built + S3b as next), so no manual debt is
  owed; flagged only so the reader knows the pre-regen INDEX lied by a slice-and-a-half.

## 2. Source-of-truth conflicts

- **None found.** The vault references the spec/PLAN/code throughout; ADR 0004/0005/**0006** live in
  `docs/decisions/` (product home), the vault folder stays empty by design. OQ-23's resolution names
  `docs/PLAN_SHORT.md` Decided + `[[m4-entity-editing]]` as the authoritative homes and references
  them. No note claims authority over a fact another note owns.

## 3. Missing decision records

- **None.** The one new code-visible major call since the last sweep — *editing already-committed
  graph state, and what it does to INV-9's "exactly two writers"* — is recorded in **ADR 0006**
  (`docs/decisions/0006`), including the build-time DM-S3a-3 resolution (direct edge-writer, because
  the decide path is surface-name/paragraph-keyed). The M4.S1/S2 read slices were read-only projections
  that minted no invariant-touching decision (deliberately ADR-free, recorded in their proposals).
  Decision coverage is clean.

## 4. Invariant violations & near-misses

- **INV-1 / INV-9 hold for the edit path (S3a) — verified.** `EntityEditService` (`agents/entity_edit.py`)
  is reached **only** from the human edit endpoints (`PATCH …/entities/{eid}`, `POST`/`DELETE …/relations`);
  no automated stage edits a committed node/edge. The coordinator still constructs with no graph writer.
  INV-9's rewording ("exactly two writers" → "only human-reached handlers — accept, decide, edit") keeps
  the guarded property unchanged — the enumeration grew, the rule didn't weaken.
- **The INV-9 grep guard widened correctly — `watch`, not a violation.** S3a adds a **third node-writer**
  (`update_entity`) and a **second edge-writer** (`create_relation`/`delete_relation` now reachable from
  `EntityEditService`, not only `RelationReviewService`). ADR 0006 + INV-9's body both widen the grep set
  to `create_entity / add_alias / create_relation / update_entity / delete_relation`, each asserted
  reachable only from a human handler. The near-miss to keep in view: the edge-writer set is now **two
  services**, so a future reviewer's "find every edge writer" must check *both* — the rule is documented,
  the cost is a wider grep.
- **INV-3 reversibility — substrate landed, execution not yet wired (expected).** Every S3a edit records a
  before→after `graph_edits` row (the prior-value image undo needs). The **undo *endpoint/UI* does not
  exist** — same posture as `candidate_decisions` (evidence without a shipped "un-accept"). This is
  explicitly **S3b's** work; flagged here because S3b is the slice that must *consume* this log (see §6).

## 5. Structural rot

- **The committed-entity edit is modelled — by folding, not a new note. Acceptable, no gap.** The S3a
  proposal floated "a short committed-entity state-machine note." Instead the edit self-transition was
  folded as a **bullet in [[candidate-lifecycle]]** ("The candidate terminal is *not* the committed
  graph node (M4.S3a)") and the edge twin as the **M4.S3a section in [[relation-lifecycle]]**. That is a
  defensible modelling call — the edit is a *self-transition on an existing object*, not a new lifecycle
  worth its own note — and it explicitly prevents the "did the terminal candidate re-open?" misread.
  **Recorded as resolved-by-folding, not a structural gap.** (If S3b's merge/delete/undo grows a richer
  committed-entity machine — multiple transitions, an undo path — that is the moment to promote it to its
  own note; flag for the S3b decompose.)
- **Orphans / ghost links — none.** All recently-touched notes carry `related` edges; `[[wikilinks]]`
  in the core notes + the S3a proposal resolve (incl. `[[lost-update]]`, added at S36). No dangling refs.
- **Stale ADRs — none.** ADR 0006 status `Accepted` matches reality; INV-8 stays correctly `RETIRED`
  with history preserved.

## 6. Fresh "but what if" — the M4.S3b boundary (merge · re-point · delete · undo)

S3b is the **next** slice and the one this sweep most needs to brief. The forward edge cases (the S3b
decompose owns *resolving* them — these are the "what if" inputs to it):

- **The `graph_edits` before-image is *per-edit*; a merge is a *compound* op — `watch`/design.** Today a
  row is `(target_id, target_kind, op, before, after)` — fine for "entity E `type`: X→Y" or one
  edge add/remove. An entity↔entity **merge** is **N writes at once**: re-point every edge incident to
  B onto A (each a delete+recreate, since `relation_edge_id = uuid5(subject,predicate,object)` changes
  when an endpoint id changes), re-point B's `entity_mentions` rows, fold B's aliases/properties into A,
  delete B. **Undo-merge** must reverse *all* of it atomically. So the S3b design weight is whether the
  per-edit `graph_edits` shape can represent a **grouped/compound** before-image (a merge id grouping its
  child rows), or whether undo replays child rows in reverse — a real schema/contract question the
  decompose must answer before the merge write is built. This is the centre of gravity the handoff named.
- **MERGE-collision on re-point silently folds two edges into one — `watch`.** When B's edge
  `(B, predicate, X)` re-points to `(A, predicate, X)` and that edge **already exists** on A, the
  `uuid5`-keyed MERGE collapses them — the same silent-fold hazard DM-S3a-3 surfaced for re-predicate
  (there handled by `merged_into_existing`). On a *merge* this can lose edge multiplicity without a
  signal. The S3b re-point must decide: surface the collision, or accept the fold (and what the
  before-image records so undo can restore the distinct edges). Ties the **provenance-vs-dedup** carried
  follow-up (ADR 0005 / the 2026-06-17 report).
- **`entity_mentions.entity_id` re-point is the cross-store half — `watch`.** Merging B into A must
  re-point B's Postgres `entity_mentions` to A or the reader silently drops B's highlights / the side
  panel shows ghosts (the latent coupling [[m4-inline-highlights]] OQ-21 and [[m4-side-panel]] OQ-22 both
  named). A merge is therefore a **Neo4j + Postgres** write — the two-store seam ([[open-questions]] OQ-1)
  on the *write* side; order it so a crash is retryable, not a half-merge.
- **Held-relation visibility (a) + edge Expiry (b) still open — carry, don't reopen.** [[relation-lifecycle]]
  "Open points" (a)/(b) — a held relation is an invisible non-decision (no Evidence row), and held rows
  never expire (none-at-PoC). A merge that resolves a previously-held endpoint, or a delete that orphans
  staged relations, both touch (a); the S3b "reject/merge prunes now-impossible held relations" rule (ADR
  0005 names it) is the natural home. Confirm posture in the S3b decompose; don't silently inherit.
- **Whole-entity delete vs dangling references — `watch`.** Deleting A must refuse-or-cascade against
  edges incident to A and `entity_mentions` pointing at A ([[referential-integrity]], fail-closed). The
  S3a "refuse to write to a ghost (404/409)" posture is the read of this; S3b makes the *delete* side real.

## Concepts worth studying

- **Compound / transactional undo.** S3a's per-edit before→after log is the easy case; a *merge* is one
  user action that is many writes, so its reversal needs a **grouped** before-image (a saga/compensating-
  transaction shape), not N independent rows. Reading: compensating transactions / the saga pattern, and
  event-sourcing's "one command → many events, replay to undo." This is the single biggest S3b design call.
- **Content-addressed identifiers and re-pointing.** `relation_edge_id = uuid5(subject, predicate, object)`
  is a *content-addressed* id: it deduplicates beautifully but means an edge's identity **changes** when an
  endpoint changes, so re-pointing is delete+recreate with collision-folding — not an in-place update. Worth
  knowing the tradeoff vs a surrogate (opaque) id that survives re-pointing but loses free dedup.
- **Doc-freshness as a state machine (again).** `overview.md` drifted for the third time in the exact same
  way — an update-in-place note that nobody re-reads between milestone rolls. The pattern worth internalising:
  *update-in-place notes need a forcing function* (the roll sweep is it). The vault's own version of the
  forcing-function gap it closed for review reports (resume step 3c).

---

_Report-only. No code or config was touched. This sweep also re-synced the derived/strategic notes it
found stale (the `review-architecture` re-sync the handoff requested): `overview.md` M4 as-built block,
the three frontmatter date bumps, the `m4-entity-editing` BUILT banner, INDEX regenerated. Trail updated:
[[open-questions]] (S3b forward "what if" recorded against the coming decompose), [[learning-log]] +
[[changelog]] appended._
