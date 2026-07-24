---
type: glossary-term
slug: software-composition-analysis
updated: 2026-06-08
status: living
related:
  - "[[prefer-deterministic]]"
  - "[[defense-in-depth]]"
  - "[[source-of-truth]]"
---

# software composition analysis (SCA)

**Definition:** scanning a project's **dependency graph** against a known-vulnerability database
(here **OSV**) to find third-party components carrying publicly-disclosed advisories (CVE / GHSA /
GO-id) — the "are any of the bricks we built on known-cracked?" check.

**Answers:** "do any of our dependencies have a publicly-known vulnerability — including one
disclosed *after* we pinned it?"

**First encountered in:** [[backend-dependency-advisory-scan]]

The key distinction this surfaced in Story Forge: SCA is **not** the same control as the freshness
soak. The §6.7 14-day soak defends against a *freshly-hijacked* release (a malicious package); SCA
defends against a *known-vulnerable* one. A package can be old enough to clear the soak and still
carry a CVE disclosed yesterday — so a **pin-time** OSV check (one-shot, in `/add-dependency`) cannot
replace a **continuous** scan (every CI run, against the live DB). The gap between them is the
*time-of-disclosure* problem, and it is exactly why GHSA-86qp-5c8j-p5mr (`starlette` 1.0.0) was
invisible to CI and caught only by Dependabot.
