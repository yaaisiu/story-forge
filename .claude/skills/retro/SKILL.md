---
name: retro
description: Process retrospective for Story Forge. Reflects on whether the skills and CLAUDE.md rules served the session well, surfaces friction, and proposes — human-in-the-loop — new or changed skills/rules before any change is made. Referenced by /wrap-session so it is never forgotten; can also be run ad hoc whenever the process feels off.
---

# Story Forge process retrospective

This skill turns the lens on **our process itself**, not the product. Everything else in
this repo improves the application; this improves how we build it. It is deliberately
separate from `/wrap-session` (which closes out the *work*), but `/wrap-session` references
it so a retrospective is never silently skipped.

**Two non-negotiables:**

- **Human-in-the-loop.** This skill *proposes*; it never edits a skill, a `CLAUDE.md`, or
  the workflow on its own. Findings go to the user as recommendations; the user decides.
- **Simplicity-first applies to process too.** A new skill or rule must earn its place by
  removing *repeatable* friction. Do not add ceremony for a one-off. The best outcome of a
  retro is often "nothing to change."

Run it near the end of a working session (after `/wrap-session`'s substantive steps) or any
time the process feels like it's fighting you.

## 1. Look back over the session

Review how the conversation actually went, not how it was supposed to go. Note concretely:

- Which skills ran (`/resume-session`, `/wrap-session`, `/add-dependency`, others) and
  whether each did its job cleanly or needed manual patching mid-run.
- Repeated manual steps, re-explanations, or corrections — friction that recurs is a
  signal a skill or rule is missing or wrong.
- Moments the process *helped* (caught drift, prevented a mistake) — worth keeping and
  knowing why, not just the failures.
- Anything we had to figure out ad hoc that the next session would also have to figure out.

## 2. Evaluate the skills and rules

- **Each skill touched:** did it do what its description promises? Is a step missing,
  stale, or now contradicted by how we actually work? Is the description still accurate?
- **`CLAUDE.md` (root + directory-level):** did a rule prevent a misstep this session? Was
  a rule *absent* where one would have helped — i.e. did we improvise a convention that
  ought to be written down? Does any rule now contradict reality?

## 3. Identify candidates (keep the bar high)

From the evaluation, list only changes that improve repeatable efficiency:

- A **new skill** worth creating (a multi-step ritual we keep doing by hand).
- An **existing skill to amend** (add/fix/remove a step; correct a stale description).
- A **new or changed `CLAUDE.md` rule** (a convention we relied on but never recorded).

If nothing clears the bar, say so plainly and stop — a clean retro is a valid result.

## 4. Surface to the human — one decision at a time

Present each candidate as: *what I observed → what I propose → why it earns its place.*
Recommend, don't decide. Ask one question at a time. Do **not** edit any skill or
`CLAUDE.md` before the user approves.

## 5. Apply approved changes with the same hygiene as everything else

For anything the user approves:

- Land it on a short governance branch and — **after the owner's explicit OK** (the owner
  holds the merge button — root `CLAUDE.md` Merge flow) — squash-merge to `main` (clean-history
  hygiene) — process changes follow the same discipline as code.
- If a change touches the spec or is architectural, **stop** and reconcile
  `story-forge-poc-spec.md` / `docs/PLAN_LONG.md` / `docs/PLAN_SHORT.md` first, per the workflow rules.
- Keep skill descriptions truthful after editing — the description is what future sessions
  match against.
- **Record outcomes in project files, never only in agent memory** (root `CLAUDE.md`,
  "Where knowledge lives"). A retro's product is an edit to a skill, a `CLAUDE.md`, the
  spec, or the plan — the granular file the next contributor reads — so the change is
  visible, reviewed, and version-controlled on this public repo.

## 6. Report

A short close-out: what was reviewed, what (if anything) is changing and why, what was
explicitly considered and rejected. The user should finish knowing the process is a little
sharper than it was — or that it was already fine.
