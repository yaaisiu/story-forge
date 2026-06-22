# ADR 0008 — Manual correction in the reader: an overlay storage model + reconciled highlights

**Status:** Accepted
**Date:** 2026-06-22
**Related spec section:** §3.5 (manual tagging + the right-click corrections), §6.4 (`entity_mentions`
gains `source`; new `mention_suppressions` table — amended 2026-06-22), §3.2 (character offsets),
§11 / §4.3 (reversibility / deterministic undo stack)
**Builds on:** ADR 0006 (edit committed graph under human-reached handlers) + ADR 0007 (grouped,
reversible operations under the human gate). This is the **mention-layer** counterpart: it reuses
ADR 0006/0007's **broaden-don't-mint** move on INV-9 and the grouped append-only `graph_edits` undo
log ADR 0007 built.
**Scope note:** landed with **M4.S3c-be (backend)** — the reconciling resolver, the storage model,
the mutators + endpoints, and the new undo op-kinds. The **frontend** half (Tiptap read-only +
ProseMirror decorations + selection + context menu + tag picker) is **M4.S3c-fe**; the Tiptap
adoption itself (DM-S3c-7, owner override of the native-selection lean) is recorded here but built
there.

## Context

The reader (ADR-less M4.S1) projects the accepted graph onto the prose. The finding that dominates
this slice: **a rendered highlight is not a stored record — it is a render-time *search hit* with no
identity.** `GET /stories/{id}/reader` reads `entity_mentions` only to learn *which* accepted
entities appear in a story, then `domain/highlights.resolve_highlights` *searches* each paragraph for
those entities' `canonical_name` + aliases (DM-IH-1: `span_start`/`span_end` are NULL and unused).

§3.5's manual correction breaks two assumptions of that derived model:

- **A manual tag is an arbitrary span search can never re-find** — an inflected form ("Jankowi"), a
  pronoun ("he"), or a brand-new entity. So a manual span **must persist real offsets**; it cannot be
  a search target.
- **Un-tagging acts on a highlight with no row to delete** — "not this entity" / "not an entity"
  right-click a *derived* search hit; there is no `entity_mentions` row backing that specific
  occurrence. You cannot `DELETE` a search result — you can only **suppress** it.

So S3c is first a **storage-model decision**: how far to *materialize* the highlight layer (turn a
computed projection into durable, addressable records). Produced through a meta-architect dogfood pass
— `decompose-requirement` → `architecture/proposals/m4-s3c-manual-tagging.md` (register DM-S3c-1..9)
— resolved with the owner on 2026-06-22, with §6.4 amended first via the stop-and-amend flow.

## Decision

1. **Overlay storage — "save only what you touch" (DM-S3c-1 → B).** Render-time search stays for the
   auto layer; a **manual tag persists a stored span** (`source='manual'`, real offsets) that
   *overlays and wins* over search; a rejected highlight writes a **`mention_suppressions`** row the
   resolver subtracts; "change boundaries" on a search hit **materializes** that one occurrence
   (promote to a stored span, then edit). **Materialization is incremental** — only occurrences the
   author touches become stored; no backfill, and DM-IH-1's rename-free / edit-robust properties are
   preserved for the common (auto) case. *Rejected:* **(A) materialize-all** — a backfill migration
   that *discards* the rename-free/edit-robust properties the owner chose in DM-IH-1; **(C)
   alias-only** — structurally cannot express change-boundaries or single-occurrence un-tag.

2. **A pure reconciliation contract: `search ∪ manual − suppressions` (DM-S3c-1/6).** A new
   `domain/highlights.reconcile_highlights(paragraph, targets, manual_spans, suppressions)` merges the
   three sources deterministically under **manual-wins-then-longest-match** (a manual span beats an
   overlapping search hit; within a source class the existing longest/leftmost/id tiebreak holds), then
   **subtracts suppressions post-overlay** (an exact-offset match where the suppression keys all
   entities — `entity_id` NULL, "not an entity" — or that highlight's entity — "not this entity"). With
   empty manual/suppression inputs it returns exactly `resolve_highlights`' output, so the S1/S2 reader
   is unchanged. Each highlight carries `source: "search"|"manual"` + a nullable `mention_id`
   (DM-S3c-6) so a correction addresses a specific occurrence.

3. **A tag can create a new entity — INV-9's enumeration grows again (DM-S3c-2).** `tag_new_entity`
   mints an accepted Neo4j node directly (no candidate, no cascade) + its first manual mention. It is a
   **new human-reached path** reaching the *existing* `create_entity` writer from the tag endpoint —
   the same broaden-don't-mint move as S3a (edit) / S3b (merge/delete): the *guarded property is
   unchanged* (only human-reached handlers write Neo4j), the enumeration grows by a path, not a writer
   class, and **no new Neo4j-writing symbol** is added (`create_entity` is reused, as the undo executor
   reuses it). The human *is* the §3.3 Stage-4 gate in person, so bypassing the cascade is INV-1's
   strongest form, not a weakening. A manual entity is **embedding-less at PoC** (it isn't a candidate;
   the cascade matches candidates) — named so a NULL vector doesn't read as a bug. *Rejected:*
   existing-only (guts the headline "add an entity extraction missed").

4. **Rejection is *uniformly* a suppression (build refinement of DM-S3c-3).** "not an entity"
   (`entity_id` NULL — clears all claimants) and "not this entity" (`entity_id` set — clears one) both
   write a `mention_suppressions` row the resolver subtracts post-overlay — *including over a manual
   span* (so "not an entity" genuinely clears a span the author had tagged). A manual mention is never
   *deleted* by a rejection. This honours DM-S3c-1(B)'s wording ("a rejected highlight writes a
   suppression record the resolver subtracts") and gives **one rejection mechanism + one inverse**
   (`RemoveSuppression`). *Rejected at build:* deleting manual rows on rejection — two code paths (delete
   vs suppress) and two inverses, for no user-visible gain. **Atomic re-assign** ("not this entity" →
   re-tag to Z) is one grouped op `[suppress(from), add_mention(to)]`; a leftover suppressed manual row
   is the same inert-data posture as a dangling suppression (Consequences).

5. **Corrections ride the S3b grouped undo via new op-kinds, contract-tested from the writer's real
   output (DM-S3c-5).** `graph_edits` gains `add_mention`, `create_entity_from_tag`, `suppress_span`,
   `edit_mention_span` (and `target_kind` grows `"mention"`/`"suppression"`), with inverters
   `RemoveMention` / `DeleteEntity` (+ a present-drift guard) / `RemoveSuppression` /
   `RestoreMentionSpan`. tag-new-entity, atomic re-assign, and materialize-boundary are **grouped** ops
   (single-step undo: tag-new removes the mention *then* deletes the node; materialize removes the new
   span *and* un-hides the vacated original). Per the PR-#108 lesson, every inverter is **driven from
   the service's real recorded rows**, never a hand-built op-row fixture (a fabricated fixture validates
   a fiction). *Rejected:* tagging outside the undo system (the entity-creating tag writes real graph
   state and must be reversible).

6. **§6.4 amended; §3.5 unchanged (DM-S3c-9, the S3a precedent).** The data model gains
   `entity_mentions.source` (`'extraction'` default vs `'manual'`) — an *explicit* flag, not a
   "non-null span" heuristic, so the two stay distinguishable the day extraction stores real offsets —
   and a `mention_suppressions` table (`paragraph_id` FK + cascade; `entity_id` nullable, no FK — the
   OQ-1 cross-store seam). §3.5 already specifies manual tagging + the three corrections, so **no
   capability amendment** was needed (as S3a). Taken through the stop-and-amend flow before the
   migration landed.

## Consequences

- **The reader's highlight layer becomes *partly authoritative*** rather than purely derived: stored
  manual spans + suppressions overlay the search projection. This is the new architectural idea
  ([[materialization]]) the slice introduces — applied *incrementally*, so DM-IH-1's two earned
  properties (a rename re-highlights for free; offsets aren't fragile under later text edits) survive
  for every occurrence the author hasn't touched.
- **Materialize-then-edit suppresses the vacated original (build call).** Change-boundaries on an auto
  hit records, as one grouped op, the new stored span **and** a suppression at the *old* offsets — else
  render-time search re-surfaces the original position as a duplicate. The trickiest mechanic; the undo
  reverses both.
- **A suppression / manual span keyed to an entity dangles if that entity is later merged/deleted
  (S3b).** Harmless (it subtracts a hit that no longer renders) but inert data — the reader skips a
  manual span whose entity is gone. Accepted at PoC (the same none-at-PoC posture as the candidate /
  relation gates, OQ-4); a V1 cleanup refinement, recorded not solved.
- **INV-9 grows a sixth witnessed instance** (`tag_new_entity` reaches `create_entity` from the tag
  handler; the mention/suppression mutators write Postgres only — the *staging* side of the line INV-9
  draws, like on-accept re-match). Folded into `architecture/invariants.md`. The grep guard's Neo4j set
  is **unchanged** (no new graph-writing symbol).
- **Tiptap is adopted in the fe slice (DM-S3c-7, owner override).** DM-IH-3 named this slice as Tiptap's
  arrival; the owner chose to pay the ProseMirror selection+decoration setup in M4.S3c-fe so the V2
  inline-editing features (§4) inherit it, replacing the read-only `<mark>` renderer with Tiptap
  read-only mode + decorations. A new frontend dependency → `/add-dependency` (exact pin, ≥14 days old,
  §6.7) at that build.
- **Reader response shape changed (DM-S3c-6):** `ReaderHighlight` gains `source` + `mention_id`; the
  OpenAPI snapshot + typed client were regenerated, and the reader's existing frontend test fixtures
  updated to the new required field.
- **After this slice + its fe, "manual correction in the reader" is feature-complete for the PoC** —
  the last of the three write-risk-sliced families (S3a edit · S3b merge/delete/undo · S3c
  tag/un-tag/boundaries). General entity *split* and relation temporal/source qualifiers remain
  post-PoC (`docs/BACKLOG.md`).
