---
type: review
slug: 2026-07-24-architecture-review
updated: 2026-07-24
status: living
related: ["[[project]]", "[[overview]]", "[[invariants]]", "[[open-questions]]", "[[llm-router]]", "[[entity-edit-service]]"]
---

# Architecture review — 2026-07-24 (pre-milestone vault-maintenance, Session 103)

**Scope:** whole vault. **Trigger:** the Session-103 pre-milestone vault-maintenance unit — pulled
forward out of the "Grzymalin reality check" milestone (was slice S6) so the vault is current *before*
the milestone's build slices and their decomposes read it. **This is a maintenance sweep, not a
discovery sweep:** every finding below was resolved in the same unit. No production code has changed
since Session 100 (the last two commits are the Session-101 roll and the Session-102 milestone open),
so there is no code-vs-vault as-built drift to chase — the drift here is purely *strategic-note
staleness* introduced by opening a new milestone in the plan while the vault still described the prior
"unchosen" state.

**No blockers.**

## Drift — vault vs reality

- **`risk` — the milestone-framing notes were a step stale (reconciled on sight).** [[project]]
  (§Identity: "The next milestone is **not yet chosen**") and [[overview]] (§as-built: "**Next — the
  milestone is deliberately unchosen**") both predated the Session-102 opening of the **Grzymalin
  reality check** milestone. This is the *exact same class* as the 2026-07-23 finding (the vault lagging
  a milestone transition) — caught one step earlier this time, because the milestone was *opened* rather
  than *closed*, so only two notes lagged rather than a whole as-built record. **Both re-synced:** they
  now name the milestone (run the pipeline unaided on real English non-fiction Grzymalin material), state
  the fork stays **open** and is locked only in the milestone's last session, and [[overview]] records
  the owner's *"Story Forge → History Forge"* framing as a **fork input** (weights toward deeper
  extraction without locking; raises a reversible-decisions spec-identity watch, spec §2 being
  narrative-framed).

- **`risk` — `INDEX.md` "Start here" said "INV-1…INV-9" (fixed).** INV-10 (the edge surrogate handle)
  shipped at Graph-quality S5b-be. `architecture/AGENTS.md` was corrected to "INV-1…INV-10" on 2026-07-23
  (OQ-35 S-1), but the parallel line in the regenerated `INDEX.md` was missed. Now "INV-1…INV-10". A
  reminder that "regenerated" `INDEX.md` is in practice append-maintained and needs the same targeted
  care as an update-in-place note.

## Source-of-truth conflicts

- **`risk` — the glossary Polish-strip scope was recorded two different (both imprecise) ways
  (corrected + executed).** The strip task was carried as **"22 notes"** in `docs/PLAN_SHORT.md`
  Decided-101(d), the Session-102/103 handoff, and [[open-questions]] OQ-35 — a number produced by a
  **diacritics-only grep**, which silently misses every diacritic-free Polish gloss (`(granica
  zaufania)`, `(model C4)`, `(BFF)`-adjacent forms). [[project]] §Calibration meanwhile said **"36"**.
  Neither is exactly right, and the gap would have caused an **incomplete strip** had "22" been executed
  literally. **Established the true state by reading every H1:** all **36** term notes carry a
  parenthetical; of those **~34 are Polish glosses to remove**, and **2 are not Polish and must be
  preserved** — `agent (agent — in Story Forge's sense)` (an English disambiguation) and
  `backend-for-frontend (BFF)` (an acronym) — while `software-composition-analysis (SCA) (analiza składu
  oprogramowania)` keeps its `(SCA)` and drops only the *second* parenthetical, and `toctou` /
  `c4-model` keep their English expansions. This is the "possibly-incomplete keyword-list" caution from
  root `CLAUDE.md` in miniature: a grep-derived count asserts more completeness than a grep can give.
  **Resolved:** the exact set + rule are recorded in OQ-36, the imprecise "22" in OQ-35 annotated, and
  the strip executed in this same unit against the real set.

## Invariant violations & near-misses

- **`watch` — no change.** `invariants.md` (INV-1…INV-10) is current with the code (nothing shipped
  since S100). The two INV-1 near-misses from the last sweep stand, both already tracked: the
  **normalise-names nominal gate** (now *promoted* to milestone slice **S2** — OQ-35 N-1, updated this
  sweep) and the **index-anchored review-queue cursor** (`docs/BACKLOG.md`, N-2).

## Structural rot

- **`watch` — the two new `components/` notes are not orphans.** [[llm-router]] and
  [[entity-edit-service]] were written this session with `related` edges into [[invariants]],
  [[overview]], the relevant state-machines and glossary terms, and are linked from `INDEX.md` and OQ-35
  T-1. `components/` is no longer an unnamed empty box (T-1 closed).
- **`watch` — inline Polish glosses remain in `proposals/` + append-only history.** The Session-103
  strip's committed scope was the glossary (term-notes + index) plus the two headline notes I was
  already editing ([[overview]]'s three architectural glosses stripped; [[project]]'s "Wody Święte" is a
  content-domain fixture name, kept). The **~11 `proposals/` notes** and the append-only `CHANGELOG.md` /
  older `reports/` still carry inline Polish — the latter correctly left verbatim (append-only history),
  the former a *possible* later cleanup deliberately not bundled here. English-only holds for new
  writing. Tracked in OQ-36; no forcing need.
- **`watch` — `state-machines/` still lists two lifecycles "still to draw"** (ingest-job, LLM-call). The
  LLM-call lifecycle is *sketched* in the `m2s2-llm-router-budget-cap` proposal and now cross-referenced
  from the new [[llm-router]] component note's State section; drawing it as a formal state-machine note
  remains deferred (no forcing need — the router's failure/fallback behaviour is captured in the
  component note). Left as a watch, not scheduled.

## Fresh "but what if" (recently-changed surface = the vault itself)

No production code changed, so the edge-case pass runs over the *vault-maintenance* surface:

- **What if the glossary strip removed a parenthetical that a `[[wikilink]]` or the glossary index
  depends on?** It does not — the strip touches only the H1 display text, not slugs or filenames, so
  every `[[slug]]` and the `glossary.md` term list resolve unchanged. Verified: the slug frontmatter and
  filenames are untouched; only the human-readable heading loses its Polish parenthetical.
- **What if a future reader treats [[project]]'s "36 glossary notes carry Polish" as still true after the
  strip?** Guarded: [[project]] §Calibration is updated in this same unit to say the strip is *done*
  (English-only headings), so the note does not outlive its own claim.

## 1b — foundational inputs (flag, don't validate)

All three were **re-confirmed by the owner on 2026-07-23** (OQ-35, Session 101) — persona (single-user,
full-trust, now with a stated *"usable one day, not only for me"* expiry), business weighting
(portfolio-primary), and calibration (English-only, beginner-accessible, not written for the operator).
That is one day old; **no re-flag this sweep.** The one live consequence to keep visible: the expiry
means a shortcut that is *wrong under many users and expensive to undo* now deserves a note when taken
(the standing example is OQ-35 W-1, the cross-project label-embedding cache).

## Concepts worth studying

- **C4 "Component" altitude** — this sweep populated the vault's long-empty `components/` folder for the
  first time. The C4 model's four zoom levels (System → Container → Component → Code) are worth reading
  as a deliberate practice: the two new notes sit at Component altitude, where Data / Errors / Security /
  Compliance-Audit / Operations dominate and the whole-system layers (personas, business) recede — see
  [[c4-model]] and the `component.md` template's "layer fingerprint".
- **Keyword-grep completeness illusions** — the "22 vs 34" glossary miscount is a clean, low-stakes
  instance of the failure root `CLAUDE.md` warns about repeatedly: a grep-derived list (or count) reads
  as exhaustive but silently drops whatever the pattern didn't match (here, diacritic-free Polish). The
  cheap fix is always the same — enumerate the actual set once before acting on a count someone else
  derived.
