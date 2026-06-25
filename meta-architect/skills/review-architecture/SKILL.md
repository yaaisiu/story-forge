---
name: review-architecture
description: >-
  Periodic or on-demand architecture sweep. Detects drift between vault claims and current
  code/config, source-of-truth conflicts, missing decision records for choices visible in code,
  invariant violations or near-misses, orphan components, ghost references, and stale ADRs; runs
  a fresh "but what if" pass on recently-changed components. Produces a dated, grouped-findings
  report ending in a "concepts worth studying" section. Report-only — never auto-fixes or edits
  code. Updates open-questions and learning-log.
argument-hint: "[scope: path or component slug; default whole vault]"
---

# Review architecture

**Operate as the meta-architect.** Read `${CLAUDE_PLUGIN_ROOT}/agents/meta-architect.md` first
and adopt it. Before writing, read `${CLAUDE_PLUGIN_ROOT}/templates/vault-note.md` for the
canonical frontmatter shape. **A `review` note has no dedicated template by design: its section
structure is the one this skill enumerates below** (kept in the skill body as the single home, not
duplicated as a template). **Report-only: you never edit code, never auto-fix, never resolve a
decision.** Get today's date with `date +%F`.

## 0. Ground yourself
- Scope = `$ARGUMENTS` (a path or component slug) if given, else the whole vault.
- Read the vault: `INDEX.md`, `PROJECT.md`, `overview.md`, `components/`, `invariants.md`,
  `state-machines/`, `decisions/`, the glossary, `open-questions.md`.
- Survey the current code/config in scope, and use git to find what moved recently
  (`git log --oneline -20`, `git diff`). Recently-changed code is where drift hides.

## 1. Drift — vault vs reality
- Compare what the vault **claims** against what the code/config actually **does**. A component
  note that describes a behaviour the code no longer has is drift. Flag each mismatch.

## 2. Source-of-truth conflicts
- Two notes (or a note and a host doc) claiming authority over the same fact → a conflict.
  Name both and which should win.

## 3. Missing decision records
- Choices visible in the code but absent from `decisions/` — a library swap, an auth scheme, a
  data-ownership call — are undocumented decisions. Flag each as a missing ADR (propose, don't
  author it unprompted).

## 4. Invariant violations & near-misses
- Check `invariants.md` against the code. Flag outright violations, and **near-misses** — places
  where only luck, ordering, or a single guard currently holds the line.

## 5. Structural rot
- **Orphan components** (no `related` edges in or out), **ghost references** (dangling
  `[[wikilinks]]`), **stale ADRs** (status disagrees with reality).

## 6. Fresh "but what if"
- Run a new edge-case pass over the recently-changed components in scope.

## 6b. Self-check — don't leave the staleness you came to fix
This sweep **re-syncs derived/strategic notes on sight** (the `update-in-place`/`regenerated` notes —
`overview.md`, `PROJECT.md`, `INDEX.md`, a proposal's BUILT/resolved banner). A freshness-fixing pass
that *itself* leaks freshness debt defeats its own purpose — so before writing the report (step 7),
run the same `/review-pr` §2-style discipline over **your own edits**:

- **Bump `updated:` on every note you edited this run** — including a proposal you only touched to add
  a **BUILT/resolved banner** (a banner is an edit; an `accepted` proposal still bumps its date and
  gets a `CHANGELOG` line). Grep the notes you changed and confirm none has a body dated newer than its
  frontmatter `updated:`. (The `update-in-place` mode already requires this; this is the closing
  *verification* that it actually happened.)
- **Grep your regenerated/edited notes for stale framing the sweep is supposed to clear** — residual
  `Next: <shipped-milestone>`, `proposed` / `register OPEN` / `awaiting owner` on a now-resolved item,
  a `build-pending` hand-off on shipped work. **`INDEX.md` is the usual culprit:** it is *regenerated*,
  but in practice the "Next steps" list grows by **append**, so a prior session's `Next: …` breadcrumb
  reads as live unless the current next is unambiguous (the list carries a run-log framing note; the
  *current* next is the last item). If the handoff that triggered this sweep named a specific stale
  anchor (e.g. `INDEX.md:NNN "Next: M4"`), confirm *that line* is cleared or reframed — adding new
  items below it is not the same as clearing it.

Why this step exists: doc-freshness drift is a recurring failure (a `learning-log` motif), and the
sweep is its forcing function — but only if the sweep holds itself to the standard it enforces on the
rest of the vault. (Earned 2026-06-25: the sweep added a proposal BUILT banner without a date bump and
left a handoff-flagged `INDEX` "Next:" line un-cleared; only the follow-on `/review-pr` §2 grep caught
both.)

## 7. Write the report — `reports/<YYYY-MM-DD>-architecture-review.md` (type `review`)
- Findings **grouped by category**, each tagged with a severity: **blocker · risk · watch**.
- **Write findings to be *triaged*, not just read.** A report has no forcing function of its own (a
  decision register blocks the build; a waiver re-reds CI) — so it relies on the **consumer half of the
  pairing**: `/resume-session` step 3c walks the latest report's **blocker/risk** findings at the next
  resume and flags any not yet resolved-or-tracked. Hold up your end: make every blocker/risk finding
  **actionable and self-contained** (what's wrong, where, and the concrete next move), and **mirror it
  into `open-questions.md`** (step 8) so it has a tracked home the triage can check against. A vague
  `risk` with no locus or action is one step 3c can't triage — and the filed-and-forgotten finding the
  pairing exists to prevent.
- **Report only — never auto-fix.** You describe and locate; the human acts.
- End with **Concepts worth studying**: terms or patterns visible in the project the reader
  would benefit from reading more about — a brief why for each, and a pointer where useful. This
  is the teaching payoff of the review.

## 8. Update the trail
- Add new findings to `open-questions.md` (deduped). Append `learning-log.md` lines for concepts
  surfaced. Append a `CHANGELOG.md` entry.

## Idempotency (how re-runs behave)
- The report is **date-stamped**: a same-day re-run regenerates that day's report; different days
  produce different reports.
- `open-questions.md`: deduped by finding. `learning-log.md` + `CHANGELOG.md`: append-only.
- **Never mutates code or config.** The sweep only reads the system and writes the vault.
