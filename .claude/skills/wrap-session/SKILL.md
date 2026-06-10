---
name: wrap-session
description: End-of-session ritual for Story Forge. Run AFTER the feature work is committed/PR'd/merged (it closes out the plan, not the feature). Runs the green-state checks (report-only), prompts the process retrospective (/retro) early so its outcomes are captured, updates docs/PLAN_SHORT.md (check off tasks, strike obsolete ones, append a dated Done line, refresh Blocked/Decided), rewrites the Session handoff block to point at the next session, checks spec/plan consistency, and commits its own bookkeeping as a docs: close Session N change. Run near the end of every working conversation. Pairs with /resume-session, which reads the handoff block this writes.
---

# Wrap a Story Forge session

This is the **end-of-session** half of the handoff loop. Its job: leave the repo and the
plan in a state where the next conversation can resume with zero archaeology. It is the
mirror of `/resume-session` — this skill *writes* the handoff block; that skill *reads*
it. They share one contract: the `▶ Session handoff` block at the top of `docs/PLAN_SHORT.md`,
delimited by `<!-- ── HANDOFF ── -->` / `<!-- ── END HANDOFF ── -->` markers. Keep that
block's shape stable so the pair keeps working without extra glue.

Work through the steps in order.

## 0. Preflight — the feature should already be merged

`/wrap-session` closes out the **plan**, not the feature work. The usual order is:
commit the implementation on a feature branch → push → open a PR → await **CI** (and the
best-effort GitHub Codex PR review, if it posts) → fold review fixes + your own `/review-pr`
(+ `/code-review` for substantive code) → **squash-merge to `main`** → *then* run
`/wrap-session`. This skill produces the separate **`docs: close Session N`** bookkeeping
commit; it does **not** replace the feature PR.

So before wrapping, confirm the session's implementation is committed and (normally)
merged. If it isn't, **stop and do that first** — wrapping over uncommitted feature work
forces a stale Done line and a second wrap pass. The green-state checks below then run
against the merged result. This default is skippable in whole or part **by explicit
agreement** (e.g. a docs-only session with nothing to PR, or deliberately bundling the
plan bookkeeping into the feature branch) — surface the order, don't enforce it blindly.

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
- **Dependency age** (if any dep changed) — cwd-independent path so it runs from `backend/` too (a recurring foot-gun): `python3 "$(git rev-parse --show-toplevel)/scripts/check_dependency_age.py"`

Summarize each as pass/fail with the failing output. If something is red, say so plainly
in the wrap-up and in the handoff block — never record a red session as cleanly closed.

## 2. Process retrospective — prompt `/retro`

Run this **before** the bookkeeping steps below, not after — this is the ordering that
makes the wrap honest. The retrospective can change skills, `CLAUDE.md`, or settings (and
commit them), so it must happen *first*; then the Done line, handoff, and commit steps that
follow naturally capture whatever it changed. (Putting retro last leaves the bookkeeping
stale and tempts a second wrap pass that re-fires retro.)

Prompt the user to run **`/retro`** (a separate, human-in-the-loop skill): it reflects on
whether the skills and `CLAUDE.md` rules served this session and proposes any new/changed
skill or rule. Kept separate so it stays deliberate, but referenced here so it is never
silently skipped.

**A retro is a reflective pass, not just folding a directive.** Even when the user already
named a change to make this session, still do the reflection — walk what ran, what *recurred*
(friction that bit more than once is the signal), and what helped — and surface anything it
turns up. Folding an explicit instruction is *not* a substitute for the look-back; conflating
the two is how a recurring foot-gun survives another session (it's how the cwd-invocation
gotcha did). If the reflection genuinely turns up nothing, say so — but do the pass.

**Once per session:** if `/retro` already ran this session, don't re-prompt — just fold its
outcomes into the steps below. If the session was routine and nothing felt like friction,
say so — a retro skipped *by choice* is fine; a forgotten one is not.

## 3. Update the task lists in docs/PLAN_SHORT.md

- Check off (`[x]`) every task actually completed and verified this session.
- ~~Strike through~~ (don't delete) tasks that became obsolete; add a brief reason.
- Add any tasks that emerged. Keep them in the right session block.
- If a whole session finished, mark its `[ ]` heading `[x]`.

## 4. Refresh Decided / Blocked / questions

- Move any decision made this session into **Decided** with the date and a one-line rationale.
- Update **Blocked / questions**: remove resolved items, add new blockers, keep deferred
  ones with their "decide in Session N" note.

## 5. Append a Done line

Add one dated bullet to **Done in previous sessions** summarizing what was accomplished
(what works, what tests pass, what's left), **including any process changes the
retrospective produced**. Write it for an outsider — this is public.

## 5b. Migrate any agent memory into project files, then clear it

Per root `CLAUDE.md` ("Where knowledge lives"), durable knowledge belongs in the repo,
not in private agent memory. If anything was stashed in agent memory this session, move
each item into its proper project home — a decision → **Decided**; a convention → the
relevant `CLAUDE.md`; a roadmap note → `docs/PLAN_LONG.md`; a follow-up → the cross-cutting
list — and then delete the memory entry (and its index line). The wrap is not done while a
durable fact lives only in memory. A session that used no memory: nothing to do, say so.

## 6. Check spec / plan consistency

If the work revealed the spec was wrong or incomplete: **stop.** The spec
(`story-forge-poc-spec.md`) is the source of truth and must be amended first, then
`docs/PLAN_LONG.md` and `docs/PLAN_SHORT.md` reconciled with it before the session is considered
wrapped. Note any amendment in the Done line and the relevant ADR if architectural.

## 7. Rewrite the Session handoff block

Overwrite the `▶ Session handoff` block (between the markers) so it describes the **next**
session. Fill every field literally:
- **Next session:** the next unchecked session number + title (or the next milestone if M1 is done).
- **Read before starting:** this file + the exact spec sections and directory `CLAUDE.md` that session needs.
- **Verify on disk:** the concrete anchors `/resume-session` should check (files/dirs that should or should not exist). **Do not write an anchor that asserts live *infra* state — "table X is already in the schema", "CI runs the neo4j service", "the compose service works" — without verifying it *as you write it* (grep the migration / `ci.yml`, or boot it). A false infra claim here is the bug `/resume-session` then has to catch; the cheaper fix is to never author it. Session 15 wrote two such false anchors that cost the next session real time.** Prefer "M2.S4 must *create* table X (not in the schema)" over an unverified "X already exists".
- **Last session ended:** today's date + one line on where you stopped (note any red checks).
- **Open blocks/questions:** point to the Blocked/questions section or restate the decision the next session must make first.

## 8. Commit the wrap's own output

By the preflight, the *feature* is already merged — what's uncommitted now is **this
wrap's bookkeeping**: the `docs/PLAN_SHORT.md` edits, the rewritten handoff, and anything the
retrospective produced (skill / `CLAUDE.md` changes). Story Forge keeps `main` clean
(squash-merge, curated messages — see root `CLAUDE.md`), so land these on a short
governance branch and squash-merge as a **`docs: close Session N`** commit (bundling the
retro changes is fine — see how `#7` closed the prior session). A docs/governance-only
change still goes via PR so CI runs. **Commit only when the user asks** — do not
auto-commit. Offer the `commit` / `commit-push-pr` skills if useful.

## 9. Report

Give a short close-out: checks pass/fail, what got checked off, what the next session is,
and any open question carried forward. The user should be able to close the terminal here
and pick up cleanly next time with `/resume-session`.
