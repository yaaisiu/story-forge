# OSV-Scanner waiver register (backend Python deps)

Single reference for **every** advisory we waive in the backend SCA gate, so
they can be reviewed for upstream fixes from time to time. This file is
**documentation only** — the **functional** waiver lives in
`infra/osv/osv-scanner.toml` (`[[IgnoredVulns]]`), wired to exactly one CI step
via `--config` (spec §6.7 keeps waivers *scoped*, never repo-wide). This is the
PyPI-lockfile analogue of `infra/trivy/WAIVERS.md` (which covers Docker images).

The gate is **fail-on-any**: any unwaived advisory in `backend/uv.lock` reds CI.
**Prefer a fix to a waiver** — bump to the fixed version via `/add-dependency`
(exact pin, ≥14-day soak, OSV-clean). Waive only an advisory that is assessed
unreachable, withdrawn/disputed, or genuinely unfixable (e.g. a transitive a
parent's version range forbids bumping). Each waiver here carries a reachability
justification and a **condition-based "drop when"** (mirroring Trivy's model;
the SCA analogue of "drop when upstream rebuilds" is "drop when a fixed version
clears the 14-day soak"). An optional `ignoreUntil` hard date in the toml is a
backstop, not the primary expiry. A dated "drop when (soaks)" is a **floor** =
fixed-version publication date **+ 15 days** (one past the 14-day soak): the age
gate is time-precise to the second, so a bare `+14` date is intra-day optimistic
and a drop acting on it can red the gate by hours (`/triage-advisory` step 3).

This complements, but does not replace, **Dependabot** on `main` (server-side,
post-merge) — keeping both is [[defense-in-depth]]: the CI gate is the pre-merge
blocking net, Dependabot the post-merge redundant one, and their advisory DBs
lag differently.

**How to review (do this whenever a dep is bumped, or periodically):** for each
row, re-scan `backend/uv.lock`; if the advisory no longer appears (a fixed
version is now locked), delete its `[[IgnoredVulns]]` block from
`osv-scanner.toml` **and** its row here.

```bash
# Re-scan the backend lockfile exactly as CI does (pinned scanner = the action's
# bundled osv-scanner v2.3.8; see .github/workflows/ci.yml):
docker run --rm -v "$PWD/backend:/src:ro" \
  -v "$PWD/infra/osv/osv-scanner.toml:/cfg/osv.toml:ro" \
  ghcr.io/google/osv-scanner:v2.3.8 \
  scan source -L /src/uv.lock --config=/cfg/osv.toml
```

**Last reviewed:** 2026-07-21 — **extended the setuptools waiver** `ignoreUntil` 2026-07-19 →
**2026-07-23**. The 2026-07-19 floor passed and the scheduled `main` run re-reddened on the
advisory, as designed — but the drop turned out **blocked**: the fix `setuptools==83.0.0` (soaked)
is forbidden by `torch==2.12.0`, which caps `setuptools<82` (`uv lock` fails on the conflict).
Only **torch 2.13.0** relaxes it (`setuptools>=77.0.3`, no cap), and 2.13.0 (pub 2026-07-08)
does not clear its own 14-day soak until **2026-07-23** (floor = pub + 15). Bumping torch early
was rejected — the `check_dependency_age.py` gate has no per-dep exception, so it would just swap
the OSV red for an age red. So a short, condition-honest extension to torch 2.13.0's soak floor;
on/after 2026-07-23 drop via a combined `torch 2.12.0 → 2.13.0` + `setuptools==83.0.0` bump.
Prior (2026-07-15) — **added the setuptools waiver** (GHSA-h35f-9h28-mq5c /
CVE-2026-59890 / PYSEC-2026-3447, MEDIUM 6.1): the scheduled `main` run reddened on this
freshly-surfaced advisory (published 2026-07-08) against unchanged deps. Fixed in 83.0.0
(pub 2026-07-04) but **not yet soaked** on the resume date (11 days < 14), so a time-boxed
waiver with `ignoreUntil = 2026-07-19` (floor = pub + 15). Prior (2026-07-06) — **dropped the pydantic-settings waiver**: bumped
`pydantic-settings` 2.14.0 → 2.14.2 (its floor, 2026-07-04, reached; the `ignoreUntil`
had expired and re-red the gate), clearing GHSA-4xgf-cpjx-pc3j (MEDIUM 5.3); removed the
`[[IgnoredVulns]]` block + this section. Prior (2026-06-27): **dropped the starlette waiver**:
bumped `starlette` 1.2.0 → 1.3.1 (its floor, 2026-06-27, reached), clearing both CVE-2026-54283
(HIGH DoS) and CVE-2026-54282 (LOW); removed both `[[IgnoredVulns]]` blocks + this section. Prior
(2026-06-26): corrected the starlette floors to pub+15 and batched the LOW's `ignoreUntil`
to 2026-06-27. Prior (2026-06-18): dropped the python-multipart waiver — 0.0.31 cleared its
soak, advisory GHSA-v9pg-7xvm-68hf gone.

---

## Active waivers

### setuptools — `setuptools==81.0.0` (transitive, added 2026-07-15; extended 2026-07-21)

Scoped file: `infra/osv/osv-scanner.toml` (`[[IgnoredVulns]]`, `ignoreUntil = 2026-07-23`).
Class: **sdist-packing exclusion bypass** — `setuptools`' `FileList` applies `MANIFEST.in`
exclude/global-exclude/recursive-exclude/prune directives by matching compiled globs against
on-disk names **without Unicode normalization**, so on macOS APFS/HFS+ an NFD file name can
bypass an NFC exclusion rule and be packed into a source distribution. `setuptools` is a
**transitive** dependency (pulled by `spacy`/`thinc`/`torch`; not declared in
`backend/pyproject.toml`). **Drop when:** the fix `setuptools==83.0.0` is already soaked (pub
2026-07-04), but the drop is **blocked by `torch==2.12.0`**, which caps `setuptools<82` — `uv
lock` fails on the conflict. Only **torch 2.13.0** relaxes it (`setuptools>=77.0.3`, no cap),
and 2.13.0 (pub 2026-07-08) clears its own 14-day soak on **2026-07-23** (floor = pub + 15).
So on/after 2026-07-23 do a **combined** bump — `torch 2.12.0 → 2.13.0` (in the `embeddings`
group) **and** an explicit `setuptools==83.0.0` pin — via `/add-dependency`, then delete the
toml block + this row. (Bumping torch before its soak was rejected: `check_dependency_age.py`
has no per-dep exception, so it would only swap the OSV red for an age red.) The `ignoreUntil`
re-reds CI on 2026-07-23 as the backstop.

| CVE / advisory | Severity | Class | Why not reachable here |
|---|---|---|---|
| GHSA-h35f-9h28-mq5c (CVE-2026-59890, PYSEC-2026-3447) | MEDIUM (CVSS 6.1) | `MANIFEST.in` NFD/NFC exclude bypass when building an sdist | The bug only triggers when **running `setuptools sdist`** (building a source distribution) **on macOS APFS/HFS+**. Story Forge is a local web app — it never packages/publishes a source distribution of itself or anything, and deploys on Linux/WSL with a single trusted local user. There is no sdist build and no untrusted file-name source, so the affected code path is never reached. A fixed version (83.0.0) exists; this waiver is purely the 14-day soak wait, not an unfixable case. |

### torch — `torch==2.12.0` (M3.S2, added 2026-06-12)

Scoped file: `infra/osv/osv-scanner.toml` (`[[IgnoredVulns]]`).
Class: **memory corruption via `torch.jit.script`** (local, attacker-controlled
script input). **Drop when:** a fixed torch version is published and clears the
14-day soak — bump via `/add-dependency`, then delete the toml block + this row.
(`torch` lives in the optional `embeddings` dependency group, but `uv.lock` locks
group deps too, so the SCA gate scans it regardless of the lean default install.)

| CVE / advisory | Severity | Class | Why not reachable here |
|---|---|---|---|
| GHSA-rrmf-rvhw-rf47 (CVE-2025-3000, PYSEC-2025-194) | MEDIUM (CVSS 5.3) | `torch.jit.script` memory corruption | The embedding stack (sentence-transformers) only runs **inference** — `model.encode(...)`. We never call `torch.jit.script`, the sole affected API. The advisory affects **all** versions ≤2.12.0 with **no fixed version**, so a bump cannot resolve it; it is unfixable-by-pin and unreachable, the two conditions a waiver requires. |

_Historical note: the advisory that motivated this gate — `starlette` 1.0.0,
GHSA-86qp-5c8j-p5mr / PYSEC-2026-161, MEDIUM — was resolved by an explicit
`starlette==1.0.1` pin in `backend/pyproject.toml`, not a waiver. That bump was
this gate's first live self-test: red on 1.0.0, green on 1.0.1._
