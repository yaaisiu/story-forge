# Trivy waiver register

Single reference for **every** HIGH/CRITICAL CVE we waive in the Trivy scans, so
they can be reviewed for upstream fixes from time to time. This file is
documentation only — the **functional** waivers live in the per-image
`*.trivyignore` files, each wired to exactly one CI scan step (spec §6.7 keeps
waivers *scoped*, never repo-wide, so an unrelated image can never inherit one).

**How to review (do this whenever an image tag is bumped, or periodically):**
for each row, re-scan the image; if the CVE no longer appears (upstream rebuilt
with the fix), delete its line from the scoped `.trivyignore` **and** its row
here. The scan command is in each image's `/pin-image` flow.

```bash
# Re-scan an image exactly as CI does (swap in the image + its ignore file):
docker run --rm -v /var/run/docker.sock:/var/run/docker.sock \
  -v "$PWD/infra/trivy/<image>.trivyignore:/tmp/ignore:ro" aquasec/trivy:latest \
  image --quiet --severity HIGH,CRITICAL --ignore-unfixed --scanners vuln \
  --ignorefile /tmp/ignore <IMAGE>:<TAG>
```

**Last reviewed:** 2026-05-21.

---

## neo4j — `neo4j:5.26.25-community-ubi10`

Scoped file: `infra/trivy/neo4j.trivyignore` · Issue #2 · added 2026-05-21.
Class: **bundled** netty jars Neo4j ships itself (no base variant fixes them).
**Drop when:** a Neo4j 5.26.x patch bundles netty ≥ 4.1.133.Final (released
2026-05-04). None is data-disclosure/RCE on a 127.0.0.1 single-user deployment.

| CVE | Pkg | Sev | Class | Fixed in | Why acceptable here |
|---|---|---|---|---|---|
| CVE-2026-42583 | netty-codec | HIGH | DoS (LZ4 mem exhaustion) | netty 4.1.133.Final | resource-exhaustion only |
| CVE-2026-42584 | netty-codec-http | HIGH | HTTP client-codec desync | netty 4.1.133.Final | needs Neo4j as outbound HTTP client — never exercised |
| CVE-2026-42587 | netty-codec-http | HIGH | DoS (decompression bomb) | netty 4.1.133.Final | resource-exhaustion only |

## pgvector — `pgvector/pgvector:0.8.2-pg17-trixie`

Scoped file: `infra/trivy/pgvector.trivyignore` · Issue #4 · added 2026-05-21.
Pinned at 6 days old (§6.7 age-bend for a CVE-fix release — see scoped file header).
None reachable as RCE on a 127.0.0.1 single-user non-root container.

**OS packages (Debian 13.4) — atypical waiver.** Normally OS CVEs are *fixed* by
a fresher rebuild, not waived; here `0.8.2-pg17-trixie` is already the newest
pgvector image (all tags rebuilt 2026-05-15) and these are freshly-disclosed
advisories not yet baked in. **Drop the moment a rebuilt pgvector image ships
the fixed packages** (re-scan should clear them without the waiver).

| CVE | Pkg | Sev | Class | Fixed in (Debian) | Why not reachable here |
|---|---|---|---|---|---|
| CVE-2026-42010 | gnutls | CRIT | TLS auth bypass (NUL in username) | 3.8.9-3+deb13u4 | Postgres TLS uses OpenSSL; gnutls transitive/unused |
| CVE-2026-33845 | gnutls | CRIT | DoS (DTLS zero-len fragment) | 3.8.9-3+deb13u4 | DoS only; no DTLS path |
| CVE-2026-33846 | gnutls | HIGH | DoS (DTLS heap overflow) | 3.8.9-3+deb13u4 | DoS; no DTLS |
| CVE-2026-3833 | gnutls | HIGH | nameConstraints policy bypass | 3.8.9-3+deb13u4 | not RCE; gnutls unused for our TLS |
| CVE-2026-42009 | gnutls | HIGH | DoS (DTLS reordering) | 3.8.9-3+deb13u4 | DoS; no DTLS |
| CVE-2026-42011 | gnutls | HIGH | name-constraint bypass | 3.8.9-3+deb13u4 | not RCE; gnutls unused for our TLS |
| CVE-2026-29111 | systemd (libsystemd0/libudev1) | HIGH | arb. code exec or DoS via spurious IPC | 257.13-1~deb13u1 | no systemd/D-Bus daemon in container; libs only |
| CVE-2026-4878 | libcap2 | HIGH | local privesc (TOCTOU race) | 1:2.75-10+deb13u1 | needs local attacker already inside container |

**Bundled — `gosu` Go stdlib (gobinary).** gosu is a setuid step-down wrapper
that drops root and `exec`s Postgres: no sockets, no TLS, no URL/archive/mail
parsing — all of these sit in unreachable code. Same class as the netty waiver.
**Drop when** upstream rebuilds gosu on a patched Go toolchain.

| CVE | Sev | Stdlib area | Fixed in (Go) |
|---|---|---|---|
| CVE-2025-68121 | CRIT | crypto/tls (resumption cert validation) | 1.24.13 / 1.25.7 |
| CVE-2025-58183 | HIGH | archive/tar | 1.24.8 / 1.25.2 |
| CVE-2025-61726 | HIGH | net/url | 1.24.12 / 1.25.6 |
| CVE-2025-61728 | HIGH | archive/zip | 1.24.12 / 1.25.6 |
| CVE-2025-61729 | HIGH | crypto/x509 | 1.24.11 / 1.25.5 |
| CVE-2026-25679 | HIGH | net/url | 1.25.8 / 1.26.1 |
| CVE-2026-32280 | HIGH | crypto/x509 | 1.25.9 / 1.26.2 |
| CVE-2026-32281 | HIGH | crypto/x509 | 1.25.9 / 1.26.2 |
| CVE-2026-32283 | HIGH | crypto/tls | 1.25.9 / 1.26.2 |
| CVE-2026-33811 | HIGH | net (cgo DNS LookupCNAME) | 1.25.10 / 1.26.3 |
| CVE-2026-33814 | HIGH | net/http2 | 1.25.10 / 1.26.3 |
| CVE-2026-39820 | HIGH | net/mail | 1.25.10 / 1.26.3 |
| CVE-2026-39836 | HIGH | net (Dial/LookupPort, Windows) | 1.25.10 / 1.26.3 |
| CVE-2026-42499 | HIGH | net/mail | 1.25.10 / 1.26.3 |
