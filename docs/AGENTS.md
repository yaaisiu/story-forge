# AGENTS.md — docs/

This directory holds Story Forge's tactical and strategic planning artifacts,
plus the ADRs. Everything here is the living record of *how* we build, separate
from the spec (`story-forge-poc-spec.md`, at the repo root, which is the source
of truth for *what* we build).

- **`PLAN_LONG.md`** — strategic, V1/V2/V3 milestones, stable. Update only when
  scope genuinely shifts.
- **`PLAN_SHORT.md`** — tactical, current milestone broken into one-conversation
  sessions. Read at session start (`/resume-session`); update at session end
  (`/wrap-session`).
- **`BACKLOG.md`** — post-PoC backlog: concrete items surfaced *during* PoC work
  (features, UX nits, bugs, design refinements) that are real but out of PoC scope.
  Kept separate from `PLAN_LONG.md` so the strategic plan stays milestone-level and
  stable. Its header carries the **routing rule** (which kind of follow-up goes where —
  `PLAN_LONG` vs `PLAN_SHORT` cross-cutting vs Decided vs here). Reviewed at milestone
  rolls; an item is promoted to `PLAN_SHORT.md` when picked up. (Added 2026-06-18, Session 33.)
- **`decisions/`** — Architecture Decision Records, one per file.

The two plan files were moved here at the M1 → M2 roll (2026-05-26) so the repo
root stays focused on top-level artifacts (`README.md`, `AGENTS.md`, the spec,
`docker-compose.yml`, `LICENSE`, `SECURITY.md`). All references in the root
`AGENTS.md`, `README.md`, and the `.claude/skills/` files now point at
`docs/PLAN_*.md`.

## Plan conventions

The conventions below are deliberate and have earned their place over M1. They
look like ceremony but each closes a specific failure mode we hit. Don't
deviate without proposing a change first.

### 1. The Session handoff block

`PLAN_SHORT.md` opens with a `▶ Session handoff` block delimited by HTML
comment markers — `<!-- ── HANDOFF ── -->` / `<!-- ── END HANDOFF ── -->`.
This block is the **contract** between two skills:

- **`/wrap-session`** *writes* it at the end of every working conversation.
- **`/resume-session`** *reads* it at the start of the next.

Keep the shape stable. Five fields, all literal:

1. **Next step** — the next unchecked session's number, title, and goal; the
   first concrete work step (often "the failing test").
2. **Read before starting** — every doc the next session needs *by path*:
   this file, the spec sections, the directory-level `AGENTS.md`s. Be specific.
3. **Verify on disk** — anchors `/resume-session` should literally check
   (files that should exist, files that should not exist). Catches drift.
4. **Last session ended** — today's date + one-line summary of where things
   stopped. Note any red checks.
5. **Open blocks/questions** — decisions the next session must make first; any
   carry-forward from the cross-cutting list.

Do not delete the markers. The skills depend on them.

### 2. Decided / Blocked / Done structure

Three running sections under the current-milestone task list:

- **Decided** — every non-obvious decision made in the session, dated, with a
  one-line rationale and what was *considered + rejected*. New entries go to
  the *top* (reverse chronological). The reverse-chronological order means
  the most recent decision is closest to the handoff block, which is the
  thing the next session reads first.

- **Blocked / questions** — currently-open decision points. Format: `~~bold
  decision title~~ ✅ Resolved YYYY-MM-DD: …` strikes the item without
  deleting it (history). Pure-open items stay un-struck.

- **Done in previous sessions** — one dated bullet per *completed session*,
  written for an outsider (the repo is public). Captures what shipped, what
  was reviewed, what the retro produced, and the *lesson* the session
  earned. New entries go to the top.

### 3. Cross-cutting curation

Cross-cutting items (the `### Cross-cutting (do as the relevant session
touches it)` list) are **scoped to the current milestone**. At each milestone
roll, the wrap-session author **manually reviews** each item:

- Resolved this milestone? → strike + ✅ note.
- Still relevant and likely to bite the next milestone? → carry forward,
  with a note tying it to the next milestone's expected work.
- No longer relevant? → strike + reason.

**Nothing moves automatically.** A new milestone starts only when this review
has happened — it's the moment the plan asserts the cross-cutting list is
still honest. If you find yourself wanting to copy/paste the cross-cutting
list from the M1 file unchanged, stop: the review hasn't actually happened
yet.

### 4. Strikethroughs over deletions

We never delete plan content. Obsolete items get `~~strikethrough~~` plus a
brief reason. The repo is public; the plan history is the portfolio's record
of how decisions evolved. A deleted decision is invisible; a struck one tells
the reader "we used to think this, here's why we changed our mind."

### 5. The two skills, summarised

| | Skill | Purpose |
|---|---|---|
| At start | `/resume-session` | Reads the handoff, verifies anchors, surveys git, reports drift before any code is written. |
| At end | `/wrap-session` | Runs green-state checks, prompts `/retro` early, ticks tasks, updates Decided/Blocked/Done, rewrites the handoff for the next session, commits its own bookkeeping. |

Both skills are in `.claude/skills/`. Read their SKILL.md before invoking
them — they encode the small steps that keep the loop honest.

### 6. When the spec is wrong

The spec (`story-forge-poc-spec.md`) is the source of truth. If implementation
forces a spec change: **stop.** Propose the amendment, get explicit approval,
amend the spec first, *then* reconcile `PLAN_LONG.md` and `PLAN_SHORT.md` with
it. This is the "spec- and test-driven, in this order" rule from the root
`AGENTS.md` workflow rules.

Plans, spec, and code must not drift apart. If you notice they have, the
reconciliation is the next session's first task — not a quiet fix.
