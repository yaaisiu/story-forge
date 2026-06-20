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

**When an anchor asserts *infrastructure* state — a service container runs, a CI job
has a given service, a DB has a table — verify it *runs/exists*, not just that a config
file mentions it.** A handoff that says "CI's neo4j service runs" gets a `grep` of
`.github/workflows/*.yml` for that service; "table X is in the schema" gets checked
against the migrations (or a live `\d` / `SHOW`); "the compose service works" gets a real
`docker compose up` + healthcheck. *Scanned/config-valid ≠ runs* — Session 15 lost time to
a handoff that twice asserted infra state (a table "already in the schema", "CI runs
neo4j") that file-presence checks had passed but that was false.

## 3b. Scan for expiring security waivers (don't let an "ignore" rot)

A security-gate **waiver** (`infra/osv/osv-scanner.toml`, the three `infra/trivy/*.trivyignore`)
is a deliberate "ignore *for now*" — safe only while its drop-condition holds. A waiver
nobody revisits = a known-vulnerable dependency shipping behind a green board. This is the
proactive layer; the `ignoreUntil` dates also make CI auto-re-red as a backstop, but catch
it *before* the break, on purpose.

Cheap, **date-only** check (no network — today's date is in your session context):

```bash
grep -n "ignoreUntil" infra/osv/osv-scanner.toml
grep -nE "[Dd]rop when.*soaks|soaks 2026|2026-[0-9]{2}-[0-9]{2}" infra/osv/WAIVERS.md infra/trivy/WAIVERS.md
```

Compare each dated drop-when / `ignoreUntil` against **today**. If any is **due or overdue**
(or within ~3 days), flag it in the report and recommend **`/triage-advisory`** to fix-first
(bump now that the fix has soaked) and drop the waiver. **Compute drop-readiness from the floor
date vs today yourself — do not inherit the prior handoff's framing.** A handoff line that says
a waiver is "due this week / should have soaked by now / fix-first next" is a stale pre-judged
verdict, not a fact (the wrap that wrote it couldn't know today's date); a fix is droppable only
once its floor date is **≤ today**, so a future floor date (e.g. 2026-06-26 read on 2026-06-20)
is *not yet* actionable however the handoff phrased it. Acting on the stale framing means bumping
a dep still inside its 14-day soak (a §6.7 misstep). Condition-based drop-whens ("drop when neo4j
ships netty ≥4.1.135") aren't date-checkable here — `/triage-advisory` re-scans those by running
the gates; just note they exist so the next sweep covers them.

## 3c. Triage the latest architecture report (don't let a finding rot)

A `meta-architect:review-architecture` sweep writes a dated `architecture/reports/<date>-architecture-review.md`
snapshot, grouping findings as **blocker · risk · watch**. But unlike a decision register (which stays
OPEN and blocks the build) or a security waiver (which CI re-reds on its `ignoreUntil` and step 3b
scans), a **report's findings have no forcing function** — they get mirrored into `open-questions.md`
and linked in INDEX, but nothing *forces* a look, so a real `risk` can sit filed-and-forgotten. This
step is that forcing function (the consumer half of the pairing the report's own skill writes — see
`meta-architect/skills/review-architecture/SKILL.md` step 7).

This is **not** wiring the architect into the ritual (that stays deferred — ADR 0002 / `architecture/AGENTS.md`):
it only triages a report that *already exists*. Find the newest report:

```bash
ls -t architecture/reports/*.md 2>/dev/null | head -1
```

If that report is **newer than the last session's close** (i.e. a sweep ran since you last resumed and
it hasn't been worked yet), open it and walk its **blocker / risk** findings (skim `watch`). For each,
confirm it is either **resolved** or **tracked** with a home (an `open-questions.md` OQ, a `docs/PLAN_SHORT.md`
cross-cutting item, or the handoff's open-blocks). **Flag any blocker/risk that is neither**, and
recommend addressing it **this session** — a report exists to be acted on, not filed. (Reports older
than the last close are presumed already triaged; don't re-litigate them.)

## 3d. Flag PLAN_SHORT bloat (the §7 backstop)

`PLAN_SHORT.md` is read at the start of every session, so it must stay slim — **current
milestone only** (`docs/AGENTS.md` §7). The roll-ritual archive move (`/wrap-session` step 5c)
is the primary mechanism; this is the cheap backstop that catches a file that slipped past it.

```bash
wc -c docs/PLAN_SHORT.md   # bytes
```

If it's **over ~200 KB** (approaching the 256 KB single-read limit, above which the file can't
be read in one pass), flag it in the report and recommend the **`/wrap-session` §7 archive move**
— either now as a focused task or at the session's wrap. A milestone that has already *rolled*
but whose content still sits in `PLAN_SHORT.md` is the usual cause; name it.

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
- **State check:** git branch/tree status; anchors verified ✓ or drift ⚠ with specifics; any **expiring security waiver** (step 3b) ⚠ with the date + a pointer to `/triage-advisory`.
- **This session's goal + tasks:** the unchecked tasks for this session from `docs/PLAN_SHORT.md`.
- **Decisions needed first:** any Blocked/questions item this session must resolve before coding (e.g. a library or threshold choice) — raise it now, one question at a time.

End by confirming the session goal with the user before starting. Per the spec- and
test-driven rule, the first work step is the failing test, not production code.
