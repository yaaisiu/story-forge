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

## 7. Write the report — `reports/<YYYY-MM-DD>-architecture-review.md` (type `review`)
- Findings **grouped by category**, each tagged with a severity: **blocker · risk · watch**.
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
