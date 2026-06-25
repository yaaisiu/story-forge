---
name: pin-image
description: Pin or bump a Docker image tag in Story Forge (docker-compose.yml + CI Trivy scans) while enforcing the security baseline — exact tag, ≥7 days old, Trivy HIGH/CRITICAL-clean — using local dockerized Trivy to verify before pushing, and the scoped-.trivyignore waiver pattern for bundled-dependency CVEs no tag can fix. Use whenever adding, upgrading, or changing any image tag.
---

# Pin a Docker image (Story Forge security baseline)

Story Forge pins **every** image in `docker-compose.yml` to an exact tag that is
**≥7 days old** at time of pin and **Trivy HIGH/CRITICAL-clean** (spec §6.7). The image
soak is 7 days, not the 14 used for packages, because base images come from known signed
official publishers and the dominant risk is *known CVEs* — for which a fresher rebuild is
*safer*. The `security` CI job re-scans on every code-bearing push/PR and on a daily
schedule (spec §6.7 "CI scan cadence"; a compose/image change is code-bearing, so a pin
PR always triggers it). Follow these steps so the first push passes instead of iterating
against CI.

Two failure modes a pin can hit even when the version looks right (both seen in this repo):
a **nonexistent tag** (a valid version string + dropped OS variant → `MANIFEST_UNKNOWN`),
and a **CVE-stale tag** (a valid aged pin rots as new CVEs are disclosed against its frozen
packages). Only a real pull + scan proves a tag is good — do both here.

## 1. Identify image + candidate tag

Decide the image and the tag you intend. Prefer an explicit OS-variant suffix
(`-trixie`, `-ubi10`, `-bookworm`) over a bare alias, so the base is pinned, not floating.

## 2. Confirm the tag exists and find its date (Docker Hub)

```bash
curl -s "https://hub.docker.com/v2/repositories/<NS>/<REPO>/tags/<TAG>" \
  | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('name'), d.get('last_updated'), d.get('message',''))"
```
(`<NS>` is `library` for official images like `neo4j`.) A `404 ... not found` message means
the tag does not exist — pick another. Note: `last_updated` is the last **rebuild**, not
first publication; a patch version first cut weeks ago but rebuilt yesterday still satisfies
the ≥7-day rule via first-publication — say so explicitly when you rely on it. To list
recent tags + dates, hit `.../tags?page_size=50&ordering=last_updated`.

## 3. Scan with Trivy — locally, before pushing

There **is** a local Trivy in WSL: the dockerized one. Use it — it turns a CI round-trip
into a 30s loop and lets you compare base variants head-to-head.

```bash
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock aquasec/trivy:latest \
  image --quiet --severity HIGH,CRITICAL --ignore-unfixed --scanners vuln <IMAGE>:<TAG>
```
These flags mirror `.github/workflows/ci.yml` exactly. If the image is CVE-heavy, scan the
other OS variants of the same version (`-trixie` vs `-ubi10` vs `-bookworm`) and pick the
cleanest base — variant choice can swing the OS-package count from dozens to zero.

**If the scan output can't be read back, stop iterating locally — let CI scan.** Large
images (multi-GB, e.g. `ollama`) make the `docker run` slow enough that the harness
auto-backgrounds it, and a backgrounded shell is sandboxed: its stdout *and* even
`--output`/bind-mounted file writes never reach the real disk, so every read comes back
empty. Don't burn cycles fighting it (this cost ~10 cycles in Issue #4). Instead: scaffold
a **header-only** `infra/trivy/<image>.trivyignore` (waives nothing, documents intent),
wire it, bump the tag, and **push** — the CI Trivy step enumerates the exact CVEs in its
log. Transcribe those into the waiver in a follow-up commit. Local Trivy is best-effort
here; CI is the source of truth.

**Scan *every* image the security job scans, up front — not just the one you're bumping.**
The Trivy steps run sequentially and the job aborts on the first failure, so a red image
*masks* CVE-staleness in every image after it. This has bitten twice: neo4j masked pgvector
(#2), then fixing pgvector unmasked a stale ollama (#4). Sweep all of `docker-compose.yml`'s
images before declaring the job will go green.

## 4. Decide: clean tag, or scoped waiver

- **OS-package CVEs** are fixed by choosing a fresher rebuild or a cleaner base variant —
  fix them, do **not** waive. Going *down* a version usually means an older rebuild = more
  CVEs, so it rarely helps.
- **Bundled-dependency CVEs** (a library the image ships, e.g. neo4j's netty jars, the
  Go `stdlib` inside postgres's `gosu`) are identical across base variants and fixable only
  by an upstream rebuild. Waive these — and only these — in a **scoped** ignore file:
  `infra/trivy/<image>.trivyignore`, one `# justification` comment per CVE (what it is, why
  it's unreachable in a 127.0.0.1-bound single-user deployment, the fixed-in version, and
  "drop when upstream bumps"). Wire it to that one scan step via the action's
  `trivyignores:` input — never repo-wide, so other images stay strict.

Whenever you add or change a waiver, also record it in **`infra/trivy/WAIVERS.md`** — the
consolidated review register (every waived CVE across images, with fixed-in version + drop
condition) checked periodically for upstream fixes. The scoped `.trivyignore` stays the
functional source; `WAIVERS.md` is the index. Keep them in sync, and have each scoped file
backreference the register.

## 5. Apply the tag consistently

A tag lives in more than one place — change all of them or CI/compose drift apart:
- `docker-compose.yml` — every service using it (e.g. `neo4j` **and** `neo4j-init`) and the
  pin-rationale comment block at the top.
- `.github/workflows/ci.yml` — the matching `Trivy scan` step's `image-ref` (plus
  `trivyignores:` if you added a waiver), and any **service container** that uses the image
  (e.g. the backend job's `postgres`).

Grep the repo for the old tag afterward to be sure none survives.

## 6. Verify

```bash
# compose still parses (same call as the CI security job)
POSTGRES_USER=x POSTGRES_PASSWORD=x POSTGRES_DB=x NEO4J_AUTH=neo4j/x docker compose config --quiet
# the exact CI gate, now with any waiver in place — must exit 0
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD/infra/trivy/<image>.trivyignore:/tmp/ignore:ro" aquasec/trivy:latest \
  image --quiet --severity HIGH,CRITICAL --ignore-unfixed --exit-code 1 \
  --scanners vuln --ignorefile /tmp/ignore <IMAGE>:<TAG>; echo "exit=$?"
```
If the image is a runtime dependency (a server, an init job), also confirm it still does its
job — e.g. the chosen base still ships the tools the compose file calls (`wget` for a
healthcheck, `cypher-shell`/`bash` for an init step).

## 7. Report

Tell the user: image, exact tag pinned, its age, the Trivy result (OS + bundled counts),
any CVEs waived with their justification, and which files changed. If you switched base
variant or waived anything, say why.
