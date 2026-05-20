---
name: wrap-session
description: End-of-session ritual for Story Forge. Runs the green-state checks (report-only), updates PLAN_SHORT.md (check off tasks, strike obsolete ones, append a dated Done line, refresh Blocked/Decided), rewrites the Session handoff block to point at the next session, checks spec/plan consistency, and reminds you to commit with portfolio hygiene. Run near the end of every working conversation. Pairs with /resume-session, which reads the handoff block this writes.
---

# Wrap a Story Forge session

This is the **end-of-session** half of the handoff loop. Its job: leave the repo and the
plan in a state where the next conversation can resume with zero archaeology. It is the
mirror of `/resume-session` — this skill *writes* the handoff block; that skill *reads*
it. They share one contract: the `▶ Session handoff` block at the top of `PLAN_SHORT.md`,
delimited by `<!-- ── HANDOFF ── -->` / `<!-- ── END HANDOFF ── -->` markers. Keep that
block's shape stable so the pair keeps working without extra glue.

Work through the steps in order.

## 1. Run the green-state checks (report-only)

Run the same gates CI runs, for whichever side(s) this session touched. **Report-only:**
report failures clearly, but do not refuse to wrap — the user decides whether to finalize.

- **Backend** (if touched), from `backend/`:
  ```bash
  uv run ruff check . && uv run ruff format --check . && uv run mypy && uv run pytest
  ```
- **Frontend** (if touched), from `frontend/`:
  ```bash
  npm run lint && npm run format:check && npm run build && npm run test
  ```
  (`npm run test` only if a test script exists yet.)
- **Dependency age** (if any dep changed), from repo root: `python3 scripts/check_dependency_age.py`

Summarize each as pass/fail with the failing output. If something is red, say so plainly
in the wrap-up and in the handoff block — never record a red session as cleanly closed.

## 2. Update the task lists in PLAN_SHORT.md

- Check off (`[x]`) every task actually completed and verified this session.
- ~~Strike through~~ (don't delete) tasks that became obsolete; add a brief reason.
- Add any tasks that emerged. Keep them in the right session block.
- If a whole session finished, mark its `[ ]` heading `[x]`.

## 3. Refresh Decided / Blocked / questions

- Move any decision made this session into **Decided** with the date and a one-line rationale.
- Update **Blocked / questions**: remove resolved items, add new blockers, keep deferred
  ones with their "decide in Session N" note.

## 4. Append a Done line

Add one dated bullet to **Done in previous sessions** summarizing what was accomplished
(what works, what tests pass, what's left). Write it for an outsider — this is public.

## 5. Check spec / plan consistency

If the work revealed the spec was wrong or incomplete: **stop.** The spec
(`story-forge-poc-spec.md`) is the source of truth and must be amended first, then
`PLAN_LONG.md` and `PLAN_SHORT.md` reconciled with it before the session is considered
wrapped. Note any amendment in the Done line and the relevant ADR if architectural.

## 6. Rewrite the Session handoff block

Overwrite the `▶ Session handoff` block (between the markers) so it describes the **next**
session. Fill every field literally:
- **Next session:** the next unchecked session number + title (or the next milestone if M1 is done).
- **Read before starting:** this file + the exact spec sections and directory `CLAUDE.md` that session needs.
- **Verify on disk:** the concrete anchors `/resume-session` should check (files/dirs that should or should not exist).
- **Last session ended:** today's date + one line on where you stopped (note any red checks).
- **Open blocks/questions:** point to the Blocked/questions section or restate the decision the next session must make first.

## 7. Remind about commit hygiene

Story Forge keeps `main` clean (squash-merge per feature, curated messages — see root
`CLAUDE.md`). Remind the user to commit this session's work on a feature branch with a
message a stranger could read, ready for squash-merge. **Commit only when the user asks** —
do not auto-commit. Offer the `commit` / `commit-push-pr` skills if useful.

## 8. Report

Give a short close-out: checks pass/fail, what got checked off, what the next session is,
and any open question carried forward. The user should be able to close the terminal here
and pick up cleanly next time with `/resume-session`.
