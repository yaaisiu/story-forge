# Review lessons — Story Forge

Accumulated, project-specific review heuristics for the `review-pr` skill. **Read in full at the
start of every review; appended to at the end.** Keep tight and deduplicated — this file is read
every run, so bloat makes every future review slower and worse. One dated bullet per durable
lesson; no one-off findings.

## Lessons

- 2026-06-02 (seed) The **§6.7 security baseline** is the highest-value lens in this repo — check
  it first: exact-pinned deps ≥14 days, `127.0.0.1`-only binds, non-root containers, no
  telemetry, no secrets, strict loopback CORS.
- 2026-06-02 (seed) **Two-sources-of-truth is a recurring smell.** Flag any fact *duplicated*
  across files instead of *referenced* (spec ↔ plan ↔ docs ↔ AGENTS.md). The repo deliberately
  uses symlinks/references to avoid drift; new copies are a regression.
- 2026-06-02 (seed) **"Report-only" tools must stay report-only** — flag any reviewer/analysis
  component wired to auto-fix, auto-write an ADR, or merge.
- 2026-06-02 (seed) Docs/prompts/templates are written **for an outsider** and the repo is
  public — flag home paths, secrets, `TODO: explain later`, and tool-specific naming where a
  tool-agnostic term would do.
- 2026-06-02 Tooling agents with "write only here" guardrails must cover **every write-capable
  path**, including Bash/shell redirection and directory creation, not just explicit Write/Edit
  tools.
