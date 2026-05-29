#!/usr/bin/env python3
"""Strict dependency-age + exact-pin check.

For both backend/pyproject.toml and frontend/package.json:
  * every declared dep must be an EXACT version (no ranges, prefixes, wildcards)
  * the pinned version's release date must be >=14 days before today (UTC)

Exits 0 on a clean sweep; non-zero with a clear report on first violation kind.
stdlib only. See spec section 6.7.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sys
import tomllib
import urllib.error
import urllib.request
from pathlib import Path

# 14-day threshold, applied at script run-time.
MIN_AGE = dt.timedelta(days=14)
NOW = dt.datetime.now(tz=dt.timezone.utc)
CUTOFF = NOW - MIN_AGE

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BACKEND_PYPROJECT = PROJECT_ROOT / "backend" / "pyproject.toml"
FRONTEND_PACKAGE_JSON = PROJECT_ROOT / "frontend" / "package.json"

# Python exact-pin: name[extras]==version
PY_EXACT_RE = re.compile(
    r"^([A-Za-z0-9][A-Za-z0-9._-]*?)(?:\[[A-Za-z0-9,._-]+\])?==([A-Za-z0-9.+-]+)$"
)
# npm exact-pin: just X.Y.Z optionally with -prerelease suffix; no prefix, no wildcards, no spaces
NPM_EXACT_RE = re.compile(r"^\d+\.\d+\.\d+(?:-[A-Za-z0-9.]+)?$")

# PEP 508 direct reference to a GitHub-release wheel:
#   name @ https://github.com/<owner>/<repo>/releases/download/<tag>/<file>.whl
# Used for deps not published on PyPI — notably spaCy pipeline packages
# (spec §6.7, "Direct-URL wheel channel"). The release-asset URL is immutable and
# carries the version, so it is exact by construction; the 14-day soak is checked
# against the GitHub release date instead of a PyPI upload (uv hash-locks the wheel
# in uv.lock, and OSV does not index these artifacts — see the spec rationale).
PY_GH_WHEEL_RE = re.compile(
    r"^(?P<name>[A-Za-z0-9][A-Za-z0-9._-]*)\s+@\s+"
    r"https://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/releases/download/"
    r"(?P<tag>[^/]+)/[^/]+\.whl$"
)


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(
        url, headers={"User-Agent": "story-forge-dep-age-check"}
    )
    with urllib.request.urlopen(req, timeout=20) as resp:  # noqa: S310
        return json.loads(resp.read().decode())


def pypi_release_date(name: str, version: str) -> dt.datetime | None:
    """Earliest upload_time across the version's distributions."""
    try:
        data = fetch_json(f"https://pypi.org/pypi/{name}/{version}/json")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    urls = data.get("urls", [])
    times: list[dt.datetime] = []
    for u in urls:
        t_str = u.get("upload_time_iso_8601")
        if not t_str:
            continue
        times.append(dt.datetime.fromisoformat(t_str.replace("Z", "+00:00")))
    return min(times) if times else None


def npm_release_date(name: str, version: str) -> dt.datetime | None:
    enc = name.replace("@", "%40").replace("/", "%2F")
    try:
        data = fetch_json(f"https://registry.npmjs.org/{enc}")
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    t_str = data.get("time", {}).get(version)
    if not t_str:
        return None
    return dt.datetime.fromisoformat(t_str.replace("Z", "+00:00"))


def github_release_date(owner: str, repo: str, tag: str) -> dt.datetime | None:
    """`published_at` of a GitHub release, by tag. Unauthenticated (60/hr is plenty)."""
    try:
        data = fetch_json(
            f"https://api.github.com/repos/{owner}/{repo}/releases/tags/{tag}"
        )
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise
    t_str = data.get("published_at")
    if not t_str:
        return None
    return dt.datetime.fromisoformat(t_str.replace("Z", "+00:00"))


def collect_python_deps() -> list[tuple[str, str, str, str | None]]:
    """Return (source, name, version, gh_url) per dep; gh_url set for GitHub wheels."""
    data = tomllib.loads(BACKEND_PYPROJECT.read_text())
    raw_specs: list[tuple[str, str]] = []
    for s in data.get("project", {}).get("dependencies", []):
        raw_specs.append(("project.dependencies", s))
    for group_name, group_list in data.get("dependency-groups", {}).items():
        for s in group_list:
            raw_specs.append((f"dependency-groups.{group_name}", s))
    for s in data.get("build-system", {}).get("requires", []):
        raw_specs.append(("build-system.requires", s))

    parsed: list[tuple[str, str, str, str | None]] = []
    for source, raw in raw_specs:
        spec = raw.strip()
        exact = PY_EXACT_RE.match(spec)
        if exact:
            parsed.append((source, exact.group(1), exact.group(2), None))
            continue
        wheel = PY_GH_WHEEL_RE.match(spec)
        if wheel:
            # Version lives in the release tag (`<name>-<version>`); exact by URL.
            tag = wheel.group("tag")
            version = tag.rsplit("-", 1)[-1]
            gh = f"{wheel.group('owner')}/{wheel.group('repo')}@{tag}"
            parsed.append((source, wheel.group("name"), version, gh))
            continue
        print(f"FAIL: non-exact pin in {source}: {raw!r}", file=sys.stderr)
        sys.exit(2)
    return parsed


def collect_npm_deps() -> list[tuple[str, str, str]]:
    data = json.loads(FRONTEND_PACKAGE_JSON.read_text())
    out: list[tuple[str, str, str]] = []
    for field in ("dependencies", "devDependencies"):
        for name, version in (data.get(field) or {}).items():
            v = str(version).strip()
            if not NPM_EXACT_RE.match(v):
                print(
                    f"FAIL: non-exact pin in package.json {field}: {name}@{version!r}",
                    file=sys.stderr,
                )
                sys.exit(2)
            out.append((field, name, v))
    return out


def main() -> int:
    print(f"Dependency-age check. Today (UTC): {NOW.date()}. Cutoff: {CUTOFF.date()}.")
    print()
    failures: list[str] = []

    print("== Python (backend/pyproject.toml) ==")
    for source, name, version, gh_url in collect_python_deps():
        if gh_url is None:
            origin, released = "PyPI", pypi_release_date(name, version)
        else:
            origin = f"GitHub {gh_url}"
            owner_repo, tag = gh_url.split("@", 1)
            owner, repo = owner_repo.split("/", 1)
            released = github_release_date(owner, repo, tag)
        if released is None:
            failures.append(f"{origin} {name}=={version}: not found")
            print(f"  X {source}: {name}=={version} NOT FOUND on {origin}")
            continue
        ok = released <= CUTOFF
        marker = "ok" if ok else "X "
        print(f"  {marker} {source}: {name}=={version} released {released.date()} ({origin})")
        if not ok:
            failures.append(f"{origin} {name}=={version}: released {released.date()} (<14d)")

    print()
    print("== npm (frontend/package.json) ==")
    for source, name, version in collect_npm_deps():
        released = npm_release_date(name, version)
        if released is None:
            failures.append(f"npm {name}@{version}: not found")
            print(f"  X {source}: {name}@{version} NOT FOUND on npm")
            continue
        ok = released <= CUTOFF
        marker = "ok" if ok else "X "
        print(f"  {marker} {source}: {name}@{version} released {released.date()}")
        if not ok:
            failures.append(f"npm {name}@{version}: released {released.date()} (<14d)")

    print()
    if failures:
        print(f"FAIL ({len(failures)} violation(s)):", file=sys.stderr)
        for f in failures:
            print(f"  - {f}", file=sys.stderr)
        return 1
    print("OK - all dependencies pinned exactly and aged >=14 days.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
