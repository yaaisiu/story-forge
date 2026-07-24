---
type: glossary-term
slug: defense-in-depth
updated: 2026-06-08
status: living
related:
  - "[[software-composition-analysis]]"
  - "[[fail-closed]]"
  - "[[trust-boundary]]"
---

# defense in depth

**Definition:** layering **multiple independent controls** over the same risk so that one control
failing (or missing a case) is not a breach — each layer is a separate net, deliberately redundant,
ideally failing in *different* ways.

**Answers:** "if one control misses this, does another still catch it?"

**First encountered in:** [[backend-dependency-advisory-scan]]

The live instance is the supply-chain control pair: **Dependabot** (server-side, advisory,
post-merge on `main`) **and** the proposed **CI [[software-composition-analysis]] gate** (pre-merge,
blocking, on the PR). They are not duplicates — they run on different schedules, query DBs that lag
differently, and fail differently (one informs, one blocks), so keeping both is the point. The
distinction from a single stronger control: redundancy buys coverage of the *gaps* a lone control
has (here, the pre-merge blocking window Dependabot's post-merge net leaves open), at the cost of
some duplicated noise.
