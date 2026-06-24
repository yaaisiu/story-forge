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
commit the implementation on a feature branch → push → open a PR → await **CI** → fold
review fixes + your own `/review-pr` (+ `/code-review` for substantive code) → **pause for
the owner's OK, then squash-merge
to `main`** (the owner holds the merge button — root `AGENTS.md` Merge flow) → *then* run
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

**Always put the prompt to the user — never self-assess "this was routine" and skip the
ask.** Do the reflective pass, surface what it turned up (including "nothing cleared the
bar" if that's the honest result), then **explicitly ask the user** whether to run `/retro`
— or just run it. Skipping is the **user's** call made in answer to that ask, **never the
agent's**: an unasked retro is a forgotten one, not a skipped-by-choice one. Don't bury the
ask as an optional aside ("you can run it if you like") — make it a clear question the user
answers. **Once per session:** if `/retro` already ran this session, don't re-prompt — fold
its outcomes into the steps below.

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
relevant `CLAUDE.md`; a roadmap note → `docs/PLAN_LONG.md`; a *current-milestone* follow-up →
the cross-cutting list; a *post-PoC* follow-up (feature / UX nit / bug / refinement to revisit
after V1) → `docs/BACKLOG.md` — and then delete the memory entry (and its index line). The wrap
is not done while a durable fact lives only in memory. A session that used no memory: nothing to
do, say so. (Full routing rule: root `CLAUDE.md` "Where knowledge lives" + `docs/BACKLOG.md` header.)

## 5c. Slim PLAN_SHORT — archive a rolled milestone (§7)

`PLAN_SHORT.md` carries the **current milestone only** (`docs/AGENTS.md` §7). Two triggers
move content out — both **move, not delete** (§4), into **`docs/PLAN_ARCHIVE.md`**:

- **At a milestone roll (the standing ritual step):** when this wrap closes a milestone and the
  next session opens a new one, **move the just-closed milestone** to the archive — its
  `## Completed milestone:` task section, its Decided entries, its Done log, and the
  struck/resolved cross-cutting + Blocked items *that milestone raised* (the §3 re-curation is
  the moment to sort those). Append them under a new dated `## Archived YYYY-MM-DD (Session N):
  <milestone>` heading **at the top** of the archive (newest batch first; preserve each section's
  reverse-chronological order verbatim). Leave the pointers in `PLAN_SHORT.md`: the
  `> **Earlier milestones — archived.**` blockquote near the top and the `- _Earlier
  decisions/sessions … see PLAN_ARCHIVE.md_` lines at the foot of Decided/Done.
- **Mid-milestone, if visibly bloated:** a *current* milestone can't be archived — it stays in
  full — so there is no rolled milestone to move mid-cycle. A single milestone whose own
  Done/Decided log alone threatens the **256 KB single-read limit** is therefore primarily a
  **sizing signal**: the durable fix is to slice milestones small enough that one never
  approaches the limit. If a milestone nonetheless nears it before its roll, **flag it to the
  owner** rather than silently slim; the fallback relief valve (owner's call) is to archive
  *that milestone's own earliest sessions'* Decided/Done — keep the recent ones + a pointer, the
  same batch mechanism applied intra-milestone. Live cross-cutting/Blocked always stay
  (§7 "what never moves").

Preserve bytes exactly when moving (a scripted line-range split beats re-typing dense entries);
then verify nothing was lost or duplicated (dated-bullet count before == sum after; no bullet in
both files). If this session neither closed a milestone nor bloated the file: nothing to do, say so.

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
  - **A security-waiver note in the handoff states a neutral floor date to compute against, never a pre-judged verdict.** Write "starlette waiver droppable on 2026-06-26 (→ 1.3.1)" — *not* "DUE THIS WEEK / the fix should have soaked by now / fix-first next session." The drop-when floor is the truth; whether it's *actionable* is `/resume-session`'s call at resume (step 3b), computed against *that* day's date. A pre-judged "soaked / due" verdict is the soak-equivalent of a false infra anchor — it goes stale, and acting on it (bumping a dep that hasn't actually cleared the 14-day soak) is a §6.7 misstep the CI age-gate then has to backstop. (Earned Session 42: a prior handoff's "should have soaked by now" framing led the resume brief to call a still-soaking starlette fix actionable; the floor dates were days in the future.)
  - **When the next session's task is a cross-repo reconciliation/removal (a spec amendment, a decision flip, a rename), any list of "homes to reconcile/fix" you put in the handoff is keyword-grep-derived — flag it as such and tell the next session to sweep semantically before trusting it. Never write the list as exhaustive.** A fact lives in more homes than a keyword grep finds — synonyms ("World mode" for "world graph"), the data model (a `worlds` table, a `world_id` column/FK), the code, a UX-flow phrasing ("part of world X") — exactly the cross-phrasing `/review-pr` §2 + root `AGENTS.md` "Reconcile a decision across every home" warn about. A handoff that enumerates homes as if complete is the *reconciliation* twin of the false-infra-anchor above: it asserts more certainty than a grep can give, and a session that trusts it under-reconciles. So write "world-graph homes found via `[Ww]orld graph` grep: lines …; **sweep for synonyms/schema/code before treating as complete**", not a bare line list. (Earned Session 49: the handoff listed 6 world-graph spec homes from a keyword grep; the reconciliation actually needed 11 — the 5 extra the broad resume/review sweeps re-found, not the handoff's list.)
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
auto-commit — and **the squash-merge of that PR waits for the owner's explicit OK**, like
any merge to `main` (root `AGENTS.md` Merge flow). Offer the `commit` / `commit-push-pr`
skills if useful.

## 9. Report

Give a short close-out: checks pass/fail, what got checked off, what the next session is,
and any open question carried forward. The user should be able to close the terminal here
and pick up cleanly next time with `/resume-session`.
