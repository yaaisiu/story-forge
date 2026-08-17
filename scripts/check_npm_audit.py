#!/usr/bin/env python3
"""Frontend npm-audit gate with scoped, dated waivers (spec §6.7).

Runs `npm audit --omit=dev --json` over the frontend's *shipped* dependencies and fails
on any HIGH/CRITICAL advisory that is not explicitly waived. This is the same threshold
the raw `npm audit --omit=dev --audit-level=high` step enforced; what it adds is the
ability to waive an advisory that is **assessed unreachable here and has no soaked fix**,
which `npm audit` itself cannot express.

Why a waiver mechanism exists at all: `npm audit` was the one §6.7 gate without one, so
an unreachable-but-unfixable advisory could only be handled by relaxing the gate wholesale
to `--audit-level=critical` — which would stop gating *every* future HIGH. A scoped, dated,
justified exception is strictly narrower. The trigger was GHSA-qwww-vcr4-c8h2 (React Router
RSC-mode CSRF), patched only in `react-router` 8.3.0 while `react-router-dom` has no v8 —
no forward bump could clear it, and this SPA uses no RSC APIs.

That trigger was overtaken on 2026-08-13: the advisory was amended upstream to record a 7.x
backport, so `react-router-dom` 7.18.1 → 7.18.2 cleared it and the waiver was dropped by a
fix, with nothing in this repo having changed. The rationale for the mechanism is unaffected
— but note what it means for anything this script reports: an advisory's "no fix available"
is a point-in-time fact, not a permanent property, and auditing the *installed* version can
never reveal that a fix has since become available. See `infra/npm/WAIVERS.md` and spec §6.7.

Waivers live in `infra/npm/audit-waivers.toml` (enforced) with the human-readable register
in `infra/npm/WAIVERS.md` — the same scoped-ignore + register split the Trivy image scans
and the backend OSV SCA use. Every waiver **must** carry an `ignoreUntil` date, so an
ignore re-reds on its own rather than rotting behind a green board. `/triage-advisory` owns
the lifecycle, including dropping a waiver once its fix lands.

Fails closed: an unparseable waiver file, or an `npm audit` that did not actually audit
anything, is an error — never a silent pass.
"""

from __future__ import annotations

import json
import subprocess
import sys
import tomllib
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = REPO_ROOT / "frontend"
WAIVER_FILE = REPO_ROOT / "infra" / "npm" / "audit-waivers.toml"

# Only these block the build. `npm audit --audit-level=high` used the same cut.
BLOCKING_SEVERITIES = frozenset({"high", "critical"})


@dataclass(frozen=True)
class Waiver:
    """One assessed-unreachable advisory, ignored until a date."""

    id: str
    reason: str
    ignore_until: date


@dataclass(frozen=True)
class Finding:
    """One HIGH/CRITICAL advisory against a shipped dependency."""

    advisory_id: str
    package: str
    severity: str
    title: str
    url: str


@dataclass
class Verdict:
    blocking: list[Finding] = field(default_factory=list)
    waived: list[tuple[Finding, Waiver]] = field(default_factory=list)
    expired: list[tuple[Finding, Waiver]] = field(default_factory=list)
    stale: list[Waiver] = field(default_factory=list)

    @property
    def failed(self) -> bool:
        return bool(self.blocking)


def _advisory_id(url: str, source: object) -> str:
    """Prefer the GHSA id from the advisory URL; fall back to npm's numeric source id.

    The GHSA id is the stable, human-checkable handle a waiver is written against.
    """
    tail = url.rstrip("/").rsplit("/", 1)[-1]
    if tail.startswith("GHSA-"):
        return tail
    return f"npm:{source}"


def collect_findings(audit_json: dict) -> list[Finding]:
    """Extract the blocking advisories from `npm audit --json` output.

    npm reports a package as vulnerable either directly — `via` holds advisory objects —
    or transitively, where `via` holds the *names* of other packages. Only the objects are
    advisories, so a transitively-affected package (e.g. `react-router-dom` via
    `react-router`) contributes no separate finding and needs no separate waiver.
    """
    findings: dict[str, Finding] = {}
    for pkg_name, pkg in (audit_json.get("vulnerabilities") or {}).items():
        for via in pkg.get("via") or []:
            if not isinstance(via, dict):
                continue  # a package name — the advisory itself is reported on its own entry
            severity = str(via.get("severity", "")).lower()
            if severity not in BLOCKING_SEVERITIES:
                continue
            url = str(via.get("url", ""))
            advisory_id = _advisory_id(url, via.get("source"))
            # First occurrence wins; the same advisory can be listed under several packages.
            findings.setdefault(
                advisory_id,
                Finding(
                    advisory_id=advisory_id,
                    package=str(via.get("name") or pkg_name),
                    severity=severity,
                    title=str(via.get("title", "")),
                    url=url,
                ),
            )
    return list(findings.values())


def load_waivers(text: str) -> list[Waiver]:
    """Parse the waiver TOML, rejecting anything underspecified.

    `ignoreUntil` must be a native TOML date (unquoted). A quoted date is a string, and
    silently accepting one would let a typo disable the expiry that makes the waiver safe.
    """
    try:
        data = tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise ValueError(f"waiver file is not valid TOML: {exc}") from exc

    entries = data.get("IgnoredVulns") or []
    if not isinstance(entries, list):
        # `[IgnoredVulns]` (single table) instead of `[[IgnoredVulns]]` (array of tables) —
        # a one-bracket typo. Iterating the dict would yield its keys as strings and blow up
        # with an AttributeError that main()'s `except ValueError` cannot catch, replacing
        # this file's diagnostics with a traceback.
        raise ValueError(
            "`IgnoredVulns` must be an array of tables — write `[[IgnoredVulns]]`, not "
            "`[IgnoredVulns]`, once per waived advisory"
        )

    waivers = []
    seen: set[str] = set()
    for entry in entries:
        if not isinstance(entry, dict):
            raise ValueError(f"a waiver entry is {type(entry).__name__}, expected a table")
        advisory_id = entry.get("id")
        if not advisory_id:
            raise ValueError("a waiver entry is missing `id`")
        if advisory_id in seen:
            # Two entries for one advisory means two different reasons/expiries, and only one
            # would win. Reject rather than silently pick — the losing expiry could be the
            # earlier one, quietly extending a waiver nobody agreed to extend.
            raise ValueError(f"duplicate waiver for {advisory_id} — keep exactly one entry")
        seen.add(advisory_id)
        reason = entry.get("reason")
        if not reason:
            raise ValueError(f"waiver {advisory_id} is missing `reason` — an ignore needs a why")
        ignore_until = entry.get("ignoreUntil")
        if not isinstance(ignore_until, date):
            raise ValueError(
                f"waiver {advisory_id} needs an unquoted `ignoreUntil` date (got "
                f"{ignore_until!r}) — an ignore without an expiry never gets revisited"
            )
        waivers.append(Waiver(id=advisory_id, reason=reason, ignore_until=ignore_until))
    return waivers


def evaluate(findings: list[Finding], waivers: list[Waiver], today: date) -> Verdict:
    """Apply waivers to findings. A waiver suppresses through its `ignoreUntil` date."""
    by_id = {w.id: w for w in waivers}
    verdict = Verdict()
    matched: set[str] = set()

    for finding in findings:
        waiver = by_id.get(finding.advisory_id)
        if waiver is None:
            verdict.blocking.append(finding)
            continue
        matched.add(waiver.id)
        if today > waiver.ignore_until:
            verdict.expired.append((finding, waiver))
            verdict.blocking.append(finding)
        else:
            verdict.waived.append((finding, waiver))

    # A waiver matching nothing is dead weight — surfaced for cleanup, but it does not fail
    # the build: the dependency it covered is fixed, which is good news, not a regression.
    verdict.stale = [w for w in waivers if w.id not in matched]
    return verdict


def parse_audit_payload(stdout: str) -> dict:
    """Validate that npm actually performed an audit, and return the payload.

    npm's exit code carries no signal here — it is non-zero whenever advisories exist. But it
    is *also* not the failure signal: when npm cannot audit at all (a missing lockfile, a
    registry error) it prints `{"error": {...}}` and exits **0**. That payload parses cleanly
    and contains no `vulnerabilities`, so treating "no vulnerabilities found" as "nothing to
    report" would let the gate pass green having audited nothing — a fail-*open* security gate.

    So a real report must carry BOTH `vulnerabilities` and `metadata` as objects. Checking the
    key is merely *present* is not enough: `{"vulnerabilities": null}` would pass that check and
    then be coerced to an empty mapping downstream — the same fail-open by a different route.
    `metadata` is npm's own summary of what it audited; a report that omits it is not a report.
    """
    try:
        payload = json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"npm audit produced no parseable JSON: {stdout[:300]}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"npm audit returned {type(payload).__name__}, expected an object")

    error = payload.get("error") or {}
    detail = error.get("summary") or error.get("code") or json.dumps(payload)[:300]
    for key in ("vulnerabilities", "metadata"):
        if not isinstance(payload.get(key), dict):
            raise ValueError(f"npm audit reported no `{key}` object — it did not audit: {detail}")
    return payload


def _run_npm_audit() -> dict:
    proc = subprocess.run(
        ["npm", "audit", "--omit=dev", "--json"],
        cwd=FRONTEND_DIR,
        capture_output=True,
        text=True,
    )
    # npm exits 1 whenever advisories exist, so a non-zero code is not itself a failure —
    # but anything outside {0, 1} is npm reporting an operational error, and the raw
    # `npm audit` step this replaced treated that as a red. Keep that guard: a partial or
    # truncated report that still happens to carry the right keys must not pass as clean.
    if proc.returncode not in (0, 1):
        raise SystemExit(
            f"FAIL: npm audit exited {proc.returncode} (an operational failure, not an "
            f"advisory count).\nstderr: {proc.stderr[:300]}"
        )
    try:
        return parse_audit_payload(proc.stdout)
    except ValueError as exc:
        raise SystemExit(
            f"FAIL: {exc}\n(npm exit {proc.returncode}) stderr: {proc.stderr[:300]}"
        ) from exc


def main() -> int:
    try:
        waiver_text = WAIVER_FILE.read_text(encoding="utf-8") if WAIVER_FILE.exists() else ""
        waivers = load_waivers(waiver_text)
    except ValueError as exc:
        print(f"FAIL: {WAIVER_FILE.relative_to(REPO_ROOT)}: {exc}")
        return 1

    # UTC, not local time: the CI runner is UTC and advisory/publication dates are too, so a
    # local-time `today()` could expire a waiver hours early or late depending on the machine.
    today = datetime.now(UTC).date()
    verdict = evaluate(collect_findings(_run_npm_audit()), waivers, today)

    for finding, waiver in verdict.waived:
        print(
            f"waived   {finding.advisory_id} ({finding.severity}) {finding.package} "
            f"— until {waiver.ignore_until}: {waiver.reason}"
        )
    for waiver in verdict.stale:
        print(
            f"STALE    {waiver.id} waives nothing any more — delete it from "
            f"{WAIVER_FILE.relative_to(REPO_ROOT)} and its WAIVERS.md row"
        )
    for finding, waiver in verdict.expired:
        print(f"EXPIRED  {finding.advisory_id} waiver lapsed on {waiver.ignore_until}")
    for finding in verdict.blocking:
        print(f"BLOCKING {finding.advisory_id} ({finding.severity}) {finding.package}")
        print(f"         {finding.title}")
        print(f"         {finding.url}")

    if verdict.failed:
        print(
            f"\nFAIL: {len(verdict.blocking)} unwaived HIGH/CRITICAL advisory(ies) in shipped "
            "frontend dependencies.\nFix first (bump via /add-dependency); waive only an "
            "assessed-unreachable advisory with no soaked fix, via /triage-advisory."
        )
        return 1

    print(
        f"OK: no unwaived HIGH/CRITICAL advisories "
        f"({len(verdict.waived)} waived, {len(verdict.stale)} stale)."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
