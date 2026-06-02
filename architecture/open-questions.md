---
type: open-questions
slug: open-questions
updated: 2026-06-02
status: living
related: ["[[overview]]", "[[project]]", "[[invariants]]"]
---

# Open questions — Story Forge

Decision points and gaps the architect has **framed but not resolved**. The architect's job is
to surface the consequence and lay out options; the human decides. Resolved items are struck
through with a dated note (history is never deleted), mirroring the plan files' convention.

Two homes, kept distinct:
- **Owned by the spec** — the spec's own §10 has ten "decide as we go" questions. Those stay
  the spec's; this note **references** them (below) rather than copying, so there is one home.
- **Raised by this vault** — architectural gaps the nine-layer/nine-station seed pass surfaced
  that the spec does not yet track. Those are the numbered items here.

---

## Priority queue (from the init interview — "check what's built, then strategize")

The operator's stated order for the architect's *next* deep work, after this seed run:

1. **OQ-A · Validation/drift sweep over what's already built.** Run the meta-architect
   `review-architecture` skill over M0→M2.S1 + the existing ADRs (`docs/decisions/0001–0002`):
   does the code match the decisions on record? Are there choices visible in code with no ADR?
   Any invariant near-misses already present? **Specifically, audit each invariant's "Enforced
   at" guard against actual build state** — INV-2/3/4/5/7 currently describe guards that are
   partly *planned* (router, paid providers, consent UI, candidate schemas, review queue land in
   M2.S2+/M3); keep each invariant's as-built-vs-planned split honest as that code lands. —
   *This is the literal first thing to do next; it is what the operator asked for.*
2. **OQ-B · Forward strategy pass.** Once the present is validated, a strategy pass on the
   upcoming work (M2.S2 router+budget, then M2.S3–S6) and its alignment with `docs/PLAN_LONG.md`
   — likely via `decompose-requirement` on the next concrete feature (the `LLMRouter`).
3. **OQ-C · Then, and only then,** decide where the first per-component note (`components/`)
   should land — candidates: the cascade (§3.3), the router (§6.5), the ingest job (§7).

> Deferred by design (ADR 0002): wiring these skills into `/resume-session`, `/wrap-session`,
> `/review-pr` happens *after* living with this vault once — not pre-emptively.

---

## Raised by this vault (gaps the seed pass found)

### OQ-1 — Two-store write consistency (Neo4j entity ↔ Postgres mention)
An entity's identity lives in Neo4j; its `entity_mentions` live in Postgres. The two stores
**cannot share a transaction**. *But what if* the Neo4j write succeeds and the Postgres
mention write fails (or vice versa)?
- **Options:** (a) write-Neo4j-then-Postgres with a reconciliation/repair pass on startup;
  (b) outbox pattern (record intent in one store, replay); (c) accept eventual inconsistency at
  PoC scale and add a "verify graph↔mentions" maintenance check.
- **My proposal:** (c) for the PoC (single user, low volume, reversible), with a cheap
  consistency check surfaced in the UI — but flag it as a real seam to revisit if it bites.
- **Lands in:** M2.S4 (first time both writes coexist). Open.

### OQ-2 — Ingest job partial-failure recovery
*But what if* extraction dies halfway through a 50k-word story? Is the job resumable, or does
the user re-run from scratch? Is there an ingest-job state record at all, or only per-paragraph
side effects?
- **Options:** (a) per-paragraph idempotent writes + resume-from-last-done; (b) whole-story
  transaction-ish redo; (c) no recovery at PoC (re-upload).
- **My proposal:** (a), leaning on idempotency (see [[idempotency]]) — paragraphs already have
  stable ids. Needs the candidate/job state machines drawn (see [[overview]] Layer 5). Open.

### OQ-3 — `cloud_free` quota-exhausted behaviour
§6.5 step 5 says "degrade to local_small with warning OR pause for user." On a GPU-less host,
local_small is impractical — so the real choices narrow. *But what if* the Ollama Cloud weekly
GPU quota runs out mid-ingest?
- **Options:** (a) pause and ask the user to switch to a paid tier; (b) auto-escalate to
  cloud_strong within a budget ceiling; (c) hard-stop.
- **My proposal:** (a) by default, (b) only if the user pre-authorised a budget — ties to
  INV-5. Lands around M2.S2. Open.

### OQ-4 — Retention / Expiry policy (the empty station)
The nine-station pass found **Expiry** empty: no stated retention for uploaded source files,
per-call LLM logs, or orphaned upload sandboxes (the latter is already a known cross-cutting
cleanup item in `PLAN_SHORT.md`). *But what if* logs of full prompts (which contain the
author's text) accumulate indefinitely?
- **Options:** (a) no retention policy at PoC, documented as accepted; (b) a simple
  age-based cleanup for sandboxes + a cap on log volume.
- **My proposal:** (b) for sandboxes (already tracked), (a) documented for logs at PoC. Open.

### OQ-5 — `ExtractionAgent` prompt-injection-by-structure pass
Before M2.S3 ships, confirm the extraction prompt renders structure **only** from the trusted
Jinja2 template and never reparses model output mixed with story text — the same class of
hardening already applied to `ChunkingAgent` and encoded in `/review-pr` §4.
- **Status:** not a decision so much as a **must-verify** gate for M2.S3. Tracked here so it is
  not forgotten. See [[overview]] Layer 7 (Security).

---

## Referenced — owned by spec §10 (not duplicated)

The spec carries ten "decide as we go" questions; they remain the spec's to own. Listed here by
title only so the vault's reader knows they exist and where to read them
(`story-forge-poc-spec.md` §10):

1. LLM extraction granularity (per-paragraph / scene / chapter). · 2. Graph versioning /
rollback strategy. · 3. Shared-world conflicting-property resolution. · 4. Export format for
the "world bible". · 5. **Agent framework — roll-our-own vs adopt** (Pydantic AI / LangGraph /
smolagents …) — *architecturally the heaviest; a likely future ADR.* · 6. Backup strategy. ·
7. `edit_history` export format (JSONL/SFT/DPO). · 8. Multilingual entity naming (PL/EN peers
vs main). · 9. Keyboard shortcuts. · 10. V1 "world summary" export to Obsidian.

When any of these is actually decided, it becomes an **ADR** (in `docs/decisions/` if it is a
product decision, or framed here first) — the spec then references the ADR. The architect never
resolves one of these unilaterally.
