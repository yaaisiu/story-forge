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

**The two-roll rule — "carry forward" is not available a third time.** An item
that has now survived **two rolls untouched** does not get a third free carry.
At its second roll it gets a **binary** decision, and the reviewer must pick one:

- **Name it as a task in the incoming milestone** — it becomes a real, scheduled
  slice or sub-task in that milestone's list, not a standing note.
- **Move it to `docs/BACKLOG.md`** — it is honestly post-PoC; route it there per
  the BACKLOG header's routing rule and strike it here with a pointer.

**If the incoming milestone isn't chosen yet, BACKLOG is the branch** — don't let the missing
milestone become a third free carry. The item is reconsidered when the milestone is planned,
which is what `docs/BACKLOG.md` already promises ("reviewed at milestone rolls; promoted when
picked up"). That is the *stronger* reconsideration, not a weaker one: a standing carry-forward
never got reviewed at all. (Hit on the rule's first run, Session 101 — the Graph-quality roll
closed with the next milestone deliberately unchosen, so all ten aged items took this branch.)

There is no third option for that age band. The reason is evidence, not tidiness:
by the Graph-quality roll **nine** items were 2+ rolls old and untouched, every one
carrying the same escape hatch — *"fix when the relevant code is next touched."*
That is not a forcing function. The code **was** touched and the items still didn't
move: the per-screen error-mapper item's own trigger is "fold when one of these
screens next needs an error-message change", and when Session 96 needed exactly
that, it **added the seventh copy** and updated the item's count from 6 to 7. The
`get_story`-outside-the-503-guard item promised "one focused pass over all the edit
routes"; the pass never came and Session 100 found the debt had spread to the reader
route. Meanwhile the items that *did* get fixed this milestone (`CandidateView`,
`useReviewQueue`) were fixed because a **slice named them** — which is precisely
what option one forces. (Earned at the Graph-quality roll, Session 101, 2026-07-23.)

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

### 7. Keep `PLAN_SHORT.md` slim — archive completed milestones, don't accumulate

`PLAN_SHORT.md` is an **operational document read at the start of every session**, so it must
stay slim. It is *not* the project's permanent archive — its job is the **current milestone
only**: the handoff block, the current-milestone task list + Decided/Done, the live
cross-cutting list, and the live Blocked/questions. Everything from a milestone that has
**rolled** belongs in the archive, not here.

This does **not** override §4 (no deletions): the rule is **move, not delete.** Migrate
completed-milestone content (its `## Completed milestone:` task section, its Decided entries,
its Done log — and, at the roll, the struck cross-cutting items + resolved Blocked items that
that milestone raised) into **`docs/PLAN_ARCHIVE.md`** — a dated, append-only companion that
preserves the full public-portfolio history — and leave a one-line pointer in `PLAN_SHORT.md`
(a `> **Earlier milestones — archived.**` blockquote near the top + an `- _Earlier
decisions/sessions … see PLAN_ARCHIVE.md_` line at the foot of Decided/Done). The history stays
readable; the operational doc stays light. **Archive convention:** newest batch on top, each
under a dated `## Archived YYYY-MM-DD (Session N): <milestone(s)>` heading; within a batch the
original reverse-chronological order is preserved verbatim.

- **When (part of the milestone-roll ritual):** the roll is the moment the *just-closed*
  milestone moves to the archive — `/wrap-session` does/offers it as a roll step (see that
  skill). **Before that move, the roll first *mines* the departing batch** — `/wrap-session §5c`
  runs `/retro` in milestone-roll mode over the milestone's record (Done lines, decisions, lessons)
  to turn its accumulated experience into process improvements, not just relocate it (owner
  directive, Session 61). **The roll also runs `meta-architect:review-architecture`** (`/wrap-session §5c`)
  to catch vault/code drift accumulated over the closing milestone — wired into the roll on evidence
  (ADR 0002 §4, Session 68), the producer paired with `/resume-session §3c`'s report triage. A *current* milestone can't be archived (it stays in full), so a single milestone
  whose own Done/Decided log alone threatens the 256 KB limit is primarily a **sizing** signal —
  slice milestones small enough to stay readable; the fallback is to archive that milestone's own
  earliest sessions (keep recent + a pointer). `/resume-session` flags bloat as a backstop. Don't
  let it accrue across milestones — cross-milestone accumulation *is* the failure mode this rule
  names.
- **What stays in `PLAN_SHORT.md`:** the **current milestone only** — its task section in full,
  its Decided + Done entries, and the live cross-cutting/Blocked working lists.
- **What never moves:** the handoff block (it always describes the *next* session) and any
  still-live cross-cutting / Blocked item, regardless of which milestone first raised it. (A
  resolved/struck cross-cutting or Blocked item only moves at the roll of the milestone that
  raised it, when the whole list is re-curated per §3 — not piecemeal mid-milestone, where
  disentangling a resolved item from a live one's "why" is error-prone.)

(Earned 2026-06-20, Session 39: the owner flagged `PLAN_SHORT.md` at 346 KB / 617 lines —
"better than accumulation of data" — as too heavy for a read-every-session doc. **Tightened
2026-06-20, Session 41** to *current-milestone-only* (was "current + immediately-prior Done
tail"): even keeping one prior milestone left the file at ~365 KB / over the 256 KB single-read
limit, so the owner directed current-only with older milestones archived-and-referenced as a
standing roll-ritual step. First archive batch — M3 and earlier → `docs/PLAN_ARCHIVE.md` — moved
the same session, taking `PLAN_SHORT.md` 368 KB → ~134 KB.)
