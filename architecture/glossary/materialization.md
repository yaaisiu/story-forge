---
type: glossary-term
slug: materialization
updated: 2026-06-22
status: living
related:
  - "[[source-of-truth]]"
  - "[[referential-integrity]]"
  - "[[m4-s3c-manual-tagging]]"
  - "[[m4-inline-highlights]]"
---

# materialization (materializacja)

**Definition:** turning a value that was **computed on demand** (a *derived* view / projection) into a
**stored** record that durably exists — so it gains an identity that can be addressed, corrected, and
reversed. The inverse move is keeping the value *derived* (recompute it each read, store nothing). A
"materialized view" in databases is the same idea: cache the result of a query as a real table.

**Answers:** "this thing is recomputed every time we render it and has no row anywhere — so how does a
user *correct one specific instance* of it, when there's nothing to point at, edit, or delete?"

**First encountered in:** [[m4-s3c-manual-tagging]]

The architectural tension it names: a derived projection is cheap and self-healing (Story Forge's reader
*searches* the prose for entity names at render time — [[m4-inline-highlights]] DM-IH-1 — so a rename
re-highlights for free and there's nothing to migrate), but it is **anonymous** — a search hit has no id,
so you cannot say "this *particular* highlight is wrong." The moment a feature needs per-instance
correction (manual tag / un-tag / change-boundaries), some of the projection must **materialize** into
stored, addressable records. The design lever is *how far*: materialize **everything** (a backfill
migration; uniform but you lose the derived view's self-healing) vs **incrementally** (materialize only
the instances the user actually touches; keep the derived view for the rest, plus a *suppression* record
to subtract a derived instance the user rejected). Materialization moves a fact's [[source-of-truth]]
from "the computation" to "the stored row" — do it deliberately, because a half-materialized projection
(some instances stored, some derived) must be **reconciled** at read time, which is new complexity to test.
