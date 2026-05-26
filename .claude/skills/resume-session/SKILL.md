---
name: resume-session
description: Start-of-session ritual for Story Forge. Reads the Session handoff block in docs/PLAN_SHORT.md, verifies the on-disk anchors it names, surveys git state, opens the spec sections it points to, and confirms reality matches the recorded state before any work begins. Run at the start of every working conversation. Pairs with /wrap-session, which writes the handoff block this reads.
---

# Resume a Story Forge session

This is the **start-of-session** half of the handoff loop. Its job: rebuild context
fast and catch drift before a single line is written. It is the mirror of
`/wrap-session` — that skill *writes* the handoff block; this skill *reads* it. They
share one contract: the `▶ Session handoff` block at the top of `docs/PLAN_SHORT.md`,
delimited by `<!-- ── HANDOFF ── -->` / `<!-- ── END HANDOFF ── -->` markers.

Do not skip steps or start coding mid-way through — finish the survey, then report.

## 1. Read the handoff

Read `docs/PLAN_SHORT.md`, focusing on the **▶ Session handoff** block. Extract:
- **Next session** — which session number/title to work on
- **Read before starting** — the docs and spec sections to load
- **Verify on disk** — the anchors that must (or must not) exist
- **Last session ended** — the one-line summary of where things stopped
- **Open blocks/questions** — anything that must be decided before or during this session

## 2. Load the referenced docs

Open every doc the handoff names. Always re-read root `CLAUDE.md`. Read the spec
sections listed (`story-forge-poc-spec.md`) — the spec is the source of truth; do not
work from memory of it. Read the directory-level `CLAUDE.md` for the area you'll touch.

## 3. Survey git + disk state

```bash
git status --short && git log --oneline -10
```

Then verify each "Verify on disk" anchor literally — that the files/dirs the handoff
says should (or should not) exist actually do. Use `ls`/`Read`/`Glob`, don't assume.

## 4. Reconcile — surface drift, don't paper over it

Compare what you found against the handoff. If anything disagrees — an anchor file is
missing or unexpectedly present, the working tree is dirty when the handoff implied a
clean close, the branch isn't what you expect, or the spec contradicts the planned task
— **stop and report it as the first thing.** Do not silently work around it. This is the
main value of the ritual: catching a bad handoff before building on it.

If a spec change is implied by the planned work, confirm `docs/PLAN_SHORT.md`, `docs/PLAN_LONG.md`,
and the spec are already consistent; if not, that reconciliation is the first task.

## 5. Report and confirm direction

Give the user a short brief:
- **Where we are:** milestone + the session we're resuming, one line on last session.
- **State check:** git branch/tree status; anchors verified ✓ or drift ⚠ with specifics.
- **This session's goal + tasks:** the unchecked tasks for this session from `docs/PLAN_SHORT.md`.
- **Decisions needed first:** any Blocked/questions item this session must resolve before coding (e.g. a library or threshold choice) — raise it now, one question at a time.

End by confirming the session goal with the user before starting. Per the spec- and
test-driven rule, the first work step is the failing test, not production code.
