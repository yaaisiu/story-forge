<!--
  ADR TEMPLATE — MADR style (Markdown Any Decision Record).
  Lives in the vault at: architecture/decisions/NNNN-short-slug.md
  An ADR (Architecture Decision Record) captures ONE decision: the forces, the options,
  the call, and the consequences we accept. It is append-only history — a superseded ADR
  is never deleted, only marked and linked forward. This matches Story Forge's existing
  house style in docs/decisions/, adapted to the vault's YAML frontmatter.
-->
---
type: adr
# slug = filename without .md. NNNN is a zero-padded sequence WITHIN the vault's
# decisions/ folder (starts at 0001) — independent of the host repo's docs/decisions/.
slug: 0001-short-decision-slug
updated: 2026-06-01
# status is the ADR's lifecycle, and it lives ONLY here — not duplicated in the body.
# proposed → accepted → superseded | deprecated
status: proposed
related: []
---

# ADR 0001 — <short decision title, a noun phrase>

## Context and problem statement

<What forces are at play, and why does a decision have to be made now? One or two short
paragraphs. Define any architectural term on first appearance — in the project's working language,
with a second-language gloss only if its `PROJECT.md` calibration asks for one, e.g.
"idempotency (idempotentność) — the property that running an operation twice yields the same
state as running it once." Name the source of truth for any fact you assert.>

<!--
  FORM ESCALATION RULE (the agent applies this automatically):
  Default to the LEAN four sections below. ESCALATE to the fuller form — adding the
  "Decision drivers" section and per-option Pros/Cons — when EITHER trigger fires:
    (a) the decision has 3 or more serious, live options, OR
    (b) it crosses a security or data boundary (touches authn/authz, secrets, PII,
        an external trust boundary, or the system's data ownership/source-of-truth).
  Routine calls stay lean; high-stakes calls get the rigor. Delete the escalated
  sections when they don't apply — don't ship empty headings.
-->

## Decision drivers
<!-- ESCALATED FORM ONLY. The criteria that decide this, listed BEFORE the options so the
     reasoning can't be retrofitted to a favourite. e.g. "must fail closed", "no standing
     access", "reversible within one sprint". -->

- <driver 1>
- <driver 2>

## Considered options

- **<Option A>** — <one line>
- **<Option B>** — <one line>
- **<Option C>** — <one line>

<!-- ESCALATED FORM ONLY — append a Pros/Cons block per option:
  ### <Option A>
  - **Pros:** <…>
  - **Cons:** <…>
-->

## Decision

<The chosen option, stated plainly, and WHY it won — which forces/drivers were decisive.
This is a record of a *made* decision. An UNRESOLVED choice does not belong in an ADR; it
belongs in the decision register inside the proposal note (`proposals/<slug>.md`) and
[[open-questions]].>

## Consequences

- **Good:** <what improves as a result>
- **Cost we accept:** <the tradeoff we take on with eyes open — every real decision has one>
- **Follow-ups:** <new questions this opens → recorded in [[open-questions]]>

<!--
  When this ADR is later overturned: do NOT edit the Decision. Instead set status to
  `superseded` and append below:  "Superseded by [[NNNN-new-slug]] on YYYY-MM-DD."
  The old reasoning stays readable — that is the point of a decision record.
-->
