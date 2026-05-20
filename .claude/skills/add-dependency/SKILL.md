---
name: add-dependency
description: Add or bump a Python (pyproject.toml) or JS (package.json) dependency in Story Forge while enforcing the security baseline — exact pin, first published ≥14 days ago, no known HIGH/CRITICAL advisory — then regenerate the lockfile and verify with scripts/check_dependency_age.py. Use whenever adding, upgrading, or pinning any backend or frontend dependency.
---

# Add a dependency (Story Forge security baseline)

Story Forge pins **every** dependency to an exact version that is **≥14 days old**
at time of pin, with **no known HIGH/CRITICAL advisory** (spec §6.7). CI's `security`
job and the `check_dependency_age.py` pre-push hook will reject anything that violates
this. Follow these steps so the first attempt passes, instead of iterating against CI.

## 1. Identify package + candidate version

Decide the package name and the version you intend to pin. If the user said "latest",
that means "latest version that is already ≥14 days old" — not the newest release.

## 2. Verify first-publication date (the 14-day rule)

The rule applies to when the **version was first published**, not to image-rebuild or
manifest dates. Query the registry directly:

- **PyPI:**
  ```bash
  python3 - <<'PY'
  import json, urllib.request, datetime
  pkg, ver = "PACKAGE", "VERSION"
  d = json.load(urllib.request.urlopen(f"https://pypi.org/pypi/{pkg}/json"))
  files = d["releases"][ver]
  first = min(f["upload_time_iso_8601"] for f in files)
  age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(first)
  print(ver, "published", first, "->", age.days, "days old")
  PY
  ```
- **npm:**
  ```bash
  python3 - <<'PY'
  import json, urllib.request, datetime
  pkg, ver = "PACKAGE", "VERSION"
  d = json.load(urllib.request.urlopen(f"https://registry.npmjs.org/{pkg}"))
  first = d["time"][ver]
  age = datetime.datetime.now(datetime.timezone.utc) - datetime.datetime.fromisoformat(first.replace("Z","+00:00"))
  print(ver, "published", first, "->", age.days, "days old")
  PY
  ```

If `age.days < 14`, pick the newest version that *is* ≥14 days old instead. State the
chosen version and its age to the user.

## 3. Check for known advisories (no HIGH/CRITICAL)

- Quick check via OSV (covers PyPI and npm):
  ```bash
  curl -s "https://api.osv.dev/v1/query" -d '{"package":{"name":"PACKAGE","ecosystem":"PyPI"},"version":"VERSION"}'
  ```
  (`"ecosystem":"npm"` for JS.) An empty `{}` means no known vulnerabilities for that
  version. If advisories come back, read severity; do not pin a version with an
  unfixed HIGH/CRITICAL — choose a patched version (re-run step 2 for its age).
- Frontend additionally gets `npm audit --audit-level=high` in step 5.

## 4. Add the exact pin

- **Backend** (`backend/pyproject.toml`): exact `==` pin. Runtime deps go under
  `[project].dependencies`; tooling under the `dev` group in `[dependency-groups]`.
  Never use `>=`, `~=`, `^`, or ranges — `check_dependency_age.py` fails on non-exact pins.
- **Frontend** (`frontend/package.json`): exact version string, **no** `^` or `~`
  prefix. Runtime in `dependencies`, tooling in `devDependencies`.

## 5. Regenerate the lockfile

- Backend: `cd backend && uv lock` (then `uv sync` to install).
- Frontend: `cd frontend && npm install` (updates `package-lock.json`), then
  `npm audit --audit-level=high` — must report no high/critical.

## 6. Verify

Run the same gate CI runs, from the repo root:
```bash
python3 scripts/check_dependency_age.py
```
It must exit 0 (exit 2 = a non-exact pin slipped in; exit 1 = something is too young).

## 7. Report

Tell the user: package, exact version pinned, its age in days, advisory check result,
and which file + lockfile changed. If you had to choose an older version because the
newest was <14 days, say so explicitly.
