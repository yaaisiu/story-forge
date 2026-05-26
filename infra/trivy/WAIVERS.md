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

**Last reviewed:** 2026-05-26.

> **Pattern note (pgvector CVE-rot recurrence).** Since 2026-05-21 the pgvector
> image has gone from green → red twice on freshly-disclosed Debian/Go advisories
> against the *same* `0.8.2-pg17-trixie` rebuild — once at Issue #4, then again on
> PR #18 with 11 additional CVEs. The image is frozen at upstream's 2026-05-15
> rebuild; the Trivy DB isn't. We waive scoped, per-CVE, with reachability
> justifications and drop them when an upstream rebuild lands — but if this
> happens a third time, **strongly consider building our own Postgres+pgvector
> image** (`postgres:17-trixie` base + `apt-get install postgresql-17-pgvector`
> in a Dockerfile we control). That's slightly beyond PoC scope today; documenting
> the option here so a reader knows we're aware of the treadmill.

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

Scoped file: `infra/trivy/pgvector.trivyignore` · Issue #4 · added 2026-05-21,
extended 2026-05-26 (PR for second CVE wave). Pinned at 6 days old (§6.7
age-bend for a CVE-fix release — see scoped file header). None reachable as RCE
on a 127.0.0.1 single-user non-root container.

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
| CVE-2026-40356 | krb5 (libgssapi-krb5-2/libk5crypto3/libkrb5-3/libkrb5support0) | HIGH | DoS via integer overflow | 1.21.3-5+deb13u1 | no Kerberos service in container; linked libs only — added 2026-05-26 |

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
| CVE-2025-47912 | HIGH | net/url (Parse non-IPv6 in bracketed host) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-58185 | HIGH | encoding/asn1 (unbounded DER allocation) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-58186 | HIGH | net/http (1MB header limit bypass) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-58187 | HIGH | crypto/x509 (inefficient name-constraint check) | 1.24.9 / 1.25.3 — added 2026-05-26 |
| CVE-2025-58188 | HIGH | crypto/x509 (DSA public-key chain validation) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-58189 | HIGH | crypto/tls (ALPN handshake error leak) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-61723 | HIGH | std (pathological-input superlinear scaling) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-61724 | HIGH | net/textproto (Reader.ReadResponse memory bloat) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-61725 | HIGH | net/mail (ParseAddress domain-literal) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-61727 | HIGH | crypto/x509 (excluded-subdomain constraint not enforced) | 1.24.11 / 1.25.5 — added 2026-05-26 |

## ollama — `ollama/ollama:0.24.0` (scanned upstream; consumed via `infra/ollama/` wrapper)

Scoped file: `infra/trivy/ollama.trivyignore` · Issue #4 · added 2026-05-21.
Class: **compiled-in** Go stdlib + `buger/jsonparser` in the ollama server binary
— no ollama tag fixes them, only an upstream rebuild on a patched Go toolchain.
Bumped 0.22.1 → 0.24.0 to minimise residual (dropped the CRITICAL + 6 others).
12 HIGH, 0 CRITICAL. Reachability: ollama is 127.0.0.1-bound, single trusted
user, backend is the only client; CVEs are mostly DoS (self-inflicted only) plus
two outbound-TLS cert-validation issues (need MITM). **Drop when** upstream
rebuilds ollama on patched Go.

| CVE | Pkg | Sev | Class | Fixed in | Why not reachable here |
|---|---|---|---|---|---|
| CVE-2026-32285 | buger/jsonparser | HIGH | DoS (crafted JSON) | jsonparser 1.1.2 | JSON from trusted local backend only |
| CVE-2026-25679 | net/url | HIGH | IPv6 host-literal parsing | Go 1.25.8 / 1.26.1 | parsing DoS; trusted caller |
| CVE-2026-27137 | crypto/x509 | HIGH | email-constraint enforcement | Go 1.26.1 | cert-validation correctness, not RCE; outbound TLS only |
| CVE-2026-32280 | crypto/x509 | HIGH | DoS (chain building) | Go 1.25.9 / 1.26.2 | DoS; outbound TLS only |
| CVE-2026-32281 | crypto/x509 | HIGH | DoS (chain validation) | Go 1.25.9 / 1.26.2 | DoS; outbound TLS only |
| CVE-2026-32283 | crypto/tls | HIGH | DoS (TLS 1.3 key updates) | Go 1.25.9 / 1.26.2 | DoS; trusted peer |
| CVE-2026-33810 | crypto/x509 | HIGH | cert-validation issue | Go 1.26.2 | correctness; outbound TLS, needs MITM |
| CVE-2026-33811 | net (cgo resolver) | HIGH | DoS (long CNAME) | Go 1.25.10 / 1.26.3 | DoS; trusted DNS |
| CVE-2026-33814 | net/http2 | HIGH | DoS (SETTINGS infinite loop) | Go 1.25.10 / 1.26.3 | DoS; only our backend connects |
| CVE-2026-39820 | net/mail | HIGH | DoS (ParseAddress) | Go 1.25.10 / 1.26.3 | ollama parses no mail; effectively unreachable |
| CVE-2026-39836 | net | HIGH | panic (NUL in Dial, Windows) | Go 1.25.10 / 1.26.3 | Linux container; Windows-specific |
| CVE-2026-42499 | net/mail | HIGH | DoS (consumePhrase) | Go 1.25.10 / 1.26.3 | ollama parses no mail; effectively unreachable |
