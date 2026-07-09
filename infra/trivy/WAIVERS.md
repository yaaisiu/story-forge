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

**Last reviewed:** 2026-07-09 — added **`CVE-2026-40355`** (`krb5`, HIGH — MIT Kerberos 5
NULL-pointer dereference → DoS) to the pgvector OS block; freshly disclosed against the unchanged
`pgvector/pgvector:0.8.2-pg17-trixie` pin (pure treadmill, reddened the scheduled `security` gate
on `main`). Sibling of the already-waived `CVE-2026-40356` — same krb5 linked libs, same
unreachable posture (no Kerberos service; Postgres uses OpenSSL for TLS; 127.0.0.1 single trusted
user), same fix (`1.21.3-5+deb13u1`, not yet in a pgvector rebuild). Owner-approved HIGH waiver
(§6.7). NVD/GHSA-8qgv-wm66-hrmc rate it MEDIUM; Debian/Trivy score it HIGH.
**Same review — sequential-unmask:** clearing pgvector let the scan reach ollama, which reddened
on **`CVE-2026-39831`** (`golang.org/x/crypto/ssh`, FIDO/U2F security-key presence-check bypass;
GHSA-89gr-r52h-f8rx, NVD/GHSA CRITICAL / Trivy HIGH) — added to the ollama wave-6 `x/crypto/ssh`
block on the identical unreachable posture as its siblings (ollama opens no SSH client / uses no
FIDO keys; fix x/crypto ≥0.52.0, upstream rebuild). Both fixes ride **one PR** because two reds on
the required `security` gate mutually block (root `AGENTS.md` Merge flow). Verified locally with
dockerized `aquasec/trivy:0.70.0`: neo4j / pgvector / ollama all clean with the updated waivers.
**Prior (2026-06-27):** added **`CVE-2026-39832`** (`golang.org/x/crypto/ssh/agent`,
HIGH — security bypass via improper key-restriction handling) to the ollama wave-6 block;
freshly disclosed against the unchanged `ollama/ollama:0.24.0` pin (pure treadmill, reddened
the `security` gate on an unrelated PR). Same `ssh/agent`-unreachable posture as its 8 sibling
`x/crypto/ssh` waivers (ollama opens no SSH agent client); same fix (upstream rebuild on
x/crypto ≥0.52.0). Owner-approved HIGH waiver (§6.7).
**Prior (2026-06-24):** added the bundled **jackson-databind** pair
(`CVE-2026-54512` + `CVE-2026-54513`, both fixed in jackson-databind 2.21.4) to neo4j;
published 2026-06-23, the Trivy DB picked them up overnight and reddened `main` on a
docs-only merge (pure treadmill). Deserialization-allowlist bypasses, unreachable here
(no untrusted-JSON path into Neo4j; Bolt not JSON; 127.0.0.1 single trusted user); fix
needs a Neo4j reship of the vendored jar.
**Prior (2026-06-23):** added the gosu Go-stdlib **wave 5** (`CVE-2026-27145`,
crypto/x509 `VerifyHostname`) to pgvector + ollama; then **wave 6** to ollama — 14 HIGHs
in the compiled-in `golang.org/x/crypto/ssh` + `golang.org/x/net` modules, unmasked when
wave 5 cleared (sequential scan). Same unreachable-code / outbound-TLS posture as waves 1–4;
drop-when extended to cover x/crypto ≥0.52.0 / x/net ≥0.55.0 (upstream ollama rebuild).

> **Pattern note (pgvector CVE-rot recurrence) — THRESHOLD TRIPPED 2026-05-27.**
> Since 2026-05-21 the pgvector image has gone from green → red **three times**
> on freshly-disclosed Debian/Go advisories against the *same*
> `0.8.2-pg17-trixie` rebuild: Issue #4 (initial waiver), PR #19 (11 additional
> CVEs, wave 2), and now PR #21 (3 additional Go-stdlib CVEs, wave 3 — fixed in
> Go 1.25.10/1.26.3 but gosu unchanged). The image is frozen at upstream's
> 2026-05-15 rebuild; the Trivy DB isn't. We waive scoped, per-CVE, with
> reachability justifications and drop them when an upstream rebuild lands.
>
> This threshold ("if this happens a third time, strongly consider building our
> own image") has now tripped. **Evaluation of the proposed Path A recipe —
> `postgres:17-trixie` base + `apt-get install postgresql-17-pgvector` in a
> Dockerfile we control — is tracked in [Issue #22](https://github.com/yaaisiu/story-forge/issues/22).**
> The first task there is verifying the premise: gosu is shipped by the
> *official* postgres image, not by pgvector, so building our own image only
> escapes the treadmill if `postgres:17-trixie` rebuilds faster than pgvector
> does. Issue #22 lays out the verification + the contingency paths if it doesn't.

---

## neo4j — `neo4j:5.26.25-community-ubi10`

Scoped file: `infra/trivy/neo4j.trivyignore` · Issue #2 · added 2026-05-21
(extended 2026-06-10: +CVE-2026-44249, +CVE-2026-45416; 2026-06-16: +CVE-2026-50010).
Class: **bundled** netty jars Neo4j ships itself (no base variant fixes them).
**Drop when:** a Neo4j 5.26.x patch bundles netty ≥ 4.1.135.Final (the 4.1.x fix
for the 2026-06-10/2026-06-16 additions; the first three were fixed in 4.1.133.Final,
2026-05-04). None is data-disclosure/RCE on a 127.0.0.1 single-user deployment.
**Partial-drop opportunity (noted 2026-06-19, not yet taken):** the soaked
`neo4j:5.26.26-community-ubi10` (pushed 2026-06-06) ships netty **4.1.133.Final**,
which fixes the first three (CVE-2026-42583/42584/42587) — a future `/pin-image` bump
to a soaked tag could drop those three waivers; the other three still need 4.1.135.
Revisit with the netty/shiro waivers at the next neo4j tag bump.

| CVE | Pkg | Sev | Class | Fixed in | Why acceptable here |
|---|---|---|---|---|---|
| CVE-2026-42583 | netty-codec | HIGH | DoS (LZ4 mem exhaustion) | netty 4.1.133.Final | resource-exhaustion only |
| CVE-2026-42584 | netty-codec-http | HIGH | HTTP client-codec desync | netty 4.1.133.Final | needs Neo4j as outbound HTTP client — never exercised |
| CVE-2026-42587 | netty-codec-http | HIGH | DoS (decompression bomb) | netty 4.1.133.Final | resource-exhaustion only |
| CVE-2026-44249 | netty-handler | HIGH | IPv6 subnet-filter bypass (access-control) | netty 4.1.135.Final | netty IP-filtering not used as a boundary; 127.0.0.1 bind is |
| CVE-2026-45416 | netty-handler | HIGH | DoS (SNI 16 MiB pre-alloc) | netty 4.1.135.Final | no public TLS surface; loopback, trusted client only |
| CVE-2026-50010 | netty-handler | HIGH | TLS hostname-verification bypass (MITM; GHSA-c653-97m9-rcg9) | netty 4.1.135.Final | no public TLS surface; loopback, single trusted client — no untrusted TLS peer to impersonate |

### Bundled Apache Shiro (Neo4j's auth framework) — added 2026-06-19

Class: **bundled** Apache Shiro jar Neo4j ships as its auth framework (like the netty
jars above; no base variant fixes it). Surfaced by the PR-#94 gate; **pre-existing on
the `.25` pin** (the Trivy DB learned of the CVE on 2026-06-19), unrelated to that PR.
**Not reachable here:** CVE-2026-49268 is in Shiro's **LDAP realm** (`DefaultLdapRealm`,
unescaped DN construction), and **Neo4j LDAP/AD auth is Enterprise-only** — this is Neo4j
**Community**, native auth realm only, so `DefaultLdapRealm` is never instantiated and no
DN is built from user input (defence in depth: 127.0.0.1, single trusted user, native
`NEO4J_AUTH`). **Fix-first not possible yet:** neo4j `5.26.26` (soaked) and `.27` (unsoaked)
both still bundle shiro-core 2.1.0 (verified by local Trivy scan 2026-06-19).
**Drop when:** a soaked (≥ 7-day) Neo4j 5.26.x patch bundles shiro-core ≥ 2.2.1 (re-scan to
confirm the CVE is gone); checked at each neo4j tag bump.

| CVE | Pkg | Sev | Class | Fixed in | Why acceptable here |
|---|---|---|---|---|---|
| CVE-2026-49268 | org.apache.shiro:shiro-core | HIGH | LDAP injection (unescaped DN in `DefaultLdapRealm`) | Shiro 2.2.1 / 3.0.0-alpha-2 | LDAP realm is Enterprise-only; Community uses native auth, `DefaultLdapRealm` never instantiated; 127.0.0.1, single trusted user |

### Bundled Jackson databind (Neo4j's JSON (de)serialization) — added 2026-06-24

Class: **bundled** Jackson `jackson-databind` jars Neo4j ships (like the netty/shiro jars
above; no base variant fixes them). A sibling pair (GHSA-j3rv-43j4-c7qm), both HIGH, both
published 2026-06-23, surfaced on the `main` push the next day (the Trivy DB learned of them
between PR #125's branch scan and the merge push — pure treadmill, unrelated to that docs PR).
Trivy finds them in **two** bundled jars: `jackson-databind-2.21.1.jar` (2.21.1) and the copy
shaded into `parquet-jackson-1.17.0.jar` (2.19.2) — both in the `>= 2.19.0, <= 2.21.3` range.
**Not reachable here:** both are deserialization-allowlist bypasses that require deserializing
**untrusted** JSON into a vulnerable type with polymorphic/default typing enabled. Neo4j
Community here is 127.0.0.1-bound, single trusted user, non-root; the backend is its only
client, queries ride Bolt (not JSON), and no attacker-controlled JSON reaches Neo4j's Jackson.
**Fix-first not possible yet:** the fix is `jackson-databind >= 2.21.4`, a jar Neo4j vendors —
no image bump fixes it until a Neo4j 5.26.x patch reships it. **Drop when:** a soaked (≥ 7-day)
Neo4j 5.26.x patch bundles jackson-databind ≥ 2.21.4 (re-scan to confirm both CVEs are gone);
checked at each neo4j tag bump.

| CVE | Pkg | Sev | Class | Fixed in | Why acceptable here |
|---|---|---|---|---|---|
| CVE-2026-54512 | com.fasterxml.jackson.core:jackson-databind | HIGH | PolymorphicTypeValidator bypass via generic type params (deserialization gadget) | jackson-databind 2.21.4 / 2.18.8 / 3.1.4 | no untrusted-JSON deserialization path; Bolt not JSON; 127.0.0.1, single trusted user |
| CVE-2026-54513 | com.fasterxml.jackson.core:jackson-databind | HIGH | array subtype allowlist bypass (deserialization gadget) | jackson-databind 2.21.4 / 2.18.8 / 3.1.4 | same — no untrusted polymorphic deserialization; loopback, trusted client |

## pgvector — `pgvector/pgvector:0.8.2-pg17-trixie`

Scoped file: `infra/trivy/pgvector.trivyignore` · Issue #4 · added 2026-05-21,
extended 2026-05-26 (PR #19, second CVE wave) and 2026-05-27 (PR for third CVE
wave — pattern threshold tripped, evaluation tracked in [Issue #22](https://github.com/yaaisiu/story-forge/issues/22)).
Pinned at 6 days old (§6.7 age-bend for a CVE-fix release — see scoped file
header). None reachable as RCE on a 127.0.0.1 single-user non-root container.

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
| CVE-2026-29111 | systemd (libsystemd0/libudev1) | HIGH | DoS via spurious IPC (assert+freeze on v250+, stack corruption on v249-; not arbitrary code execution per NVD) | 257.13-1~deb13u1 | no systemd/D-Bus daemon in container; libs only — description tightened 2026-05-27 after waiver audit |
| CVE-2026-4878 | libcap2 | HIGH | local privesc (TOCTOU race) | 1:2.75-10+deb13u1 | needs local attacker already inside container |
| CVE-2026-40356 | krb5 (libgssapi-krb5-2/libk5crypto3/libkrb5-3/libkrb5support0) | HIGH | DoS via integer *underflow* in NegoEx → OOB read (corrected from "overflow" 2026-05-27) | 1.21.3-5+deb13u1 | no Kerberos service in container; linked libs only — added 2026-05-26 |
| CVE-2026-40355 | krb5 (libgssapi-krb5-2/libk5crypto3/libkrb5-3/libkrb5support0) | HIGH | DoS via NULL-pointer dereference (krb5 <1.22.3; process crash) — Debian/Trivy HIGH, NVD/GHSA-8qgv-wm66-hrmc rate MEDIUM | 1.21.3-5+deb13u1 | no Kerberos service in container; linked libs only — sibling of CVE-2026-40356, same deb13u1 fix; added 2026-07-09 |
| CVE-2026-45447 | openssl (libssl3t64/openssl/openssl-provider-legacy) | HIGH | heap UAF in PKCS7_verify() (potential RCE) | 3.5.6-1~deb13u2 | Postgres uses OpenSSL for TLS, never PKCS#7/S-MIME verify; loopback, trusted client — added 2026-06-10 |

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
| CVE-2026-33811 | HIGH | net (cgo DNS LookupCNAME on long CNAME → double-free + crash; tightened from DoS-only 2026-05-27) | 1.25.10 / 1.26.3 |
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
| CVE-2025-61723 | HIGH | encoding/pem (non-linear parse time on invalid PEM; package tightened from "std" 2026-05-27 after audit) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-61724 | HIGH | net/textproto (Reader.ReadResponse memory bloat) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-61725 | HIGH | net/mail (ParseAddress domain-literal) | 1.24.8 / 1.25.2 — added 2026-05-26 |
| CVE-2025-61727 | HIGH | crypto/x509 (excluded-subdomain constraint not enforced) | 1.24.11 / 1.25.5 — added 2026-05-26 |
| CVE-2026-39823 | HIGH | html/template (XSS via URLs in `<meta>` content attribute; ASCII-whitespace `=` bypass) | 1.25.10 / 1.26.3 — added 2026-05-27 (wave 3; class corrected from net/url after Codex P2) |
| CVE-2026-39825 | HIGH | net/http/httputil (ReverseProxy forwards params past ParseQuery limit) | 1.25.10 / 1.26.3 — added 2026-05-27 (wave 3) |
| CVE-2026-39826 | HIGH | html/template (XSS via `<script>` with empty/whitespace `type`) | 1.25.10 / 1.26.3 — added 2026-05-27 (wave 3) |
| CVE-2026-42504 | HIGH | mime (quadratic `WordDecoder.DecodeHeader` on crafted encoded-words → CPU DoS; CWE-407, GO-2026-5038) | 1.25.11 / 1.26.4 — added 2026-06-08 (wave 4) |
| CVE-2026-27145 | HIGH | crypto/x509 (`VerifyHostname` → `matchHostnames` hostname-match correctness) | 1.25.11 / 1.26.4 — added 2026-06-23 (wave 5); gosu opens no TLS / verifies no certs → `VerifyHostname` never called |

## ollama — `ollama/ollama:0.24.0` (scanned upstream; consumed via `infra/ollama/` wrapper)

Scoped file: `infra/trivy/ollama.trivyignore` · Issue #4 · added 2026-05-21,
extended 2026-05-27 (PR #23 wave-3 fold — sequential-Trivy unmask after the
pgvector wave-3 waiver let Trivy reach this scan; same three Go-stdlib CVEs
fixed in Go 1.25.10/1.26.3 hit ollama's binary, same precedent as PR #6).
Class: **compiled-in** Go stdlib + `buger/jsonparser` in the ollama server binary
— no ollama tag fixes them, only an upstream rebuild on a patched Go toolchain
(plus one Ubuntu-base **OS** openssl CVE added 2026-06-10, fixed by a base rebuild).
Bumped 0.22.1 → 0.24.0 to minimise residual (dropped the CRITICAL + 6 others).
Reachability: ollama is 127.0.0.1-bound, single trusted user, backend is the only
client; CVEs are mostly DoS (self-inflicted only) plus a few outbound-TLS
cert-validation issues (need MITM). **Drop when** upstream rebuilds ollama on
patched Go **and** on the patched `golang.org/x/crypto` (≥0.52.0) /
`golang.org/x/net` (≥0.55.0) modules.

**Wave 6 (2026-06-23; +1 on 2026-06-27):** 15 freshly-disclosed HIGHs in the compiled-in
`golang.org/x/crypto/ssh` (9, incl. `ssh/agent` CVE-2026-39832 surfaced 2026-06-27) and
`golang.org/x/net` (6) modules — unmasked once `CVE-2026-27145` cleared (sequential scan).
All unreachable here: ollama runs no
SSH server/client (the whole `x/crypto/ssh` set) and renders no HTML (the
`x/net/html` set); the lone `x/net/idna` Punycode issue is outbound-TLS-hostname
only and needs an attacker-controlled IDN hostname the trusted local user supplies.
Rows below; rationale per CVE in `infra/trivy/ollama.trivyignore` wave-6 block.

| CVE | Pkg | Sev | Class | Fixed in | Why not reachable here |
|---|---|---|---|---|---|
| CVE-2026-45447 | openssl (libssl3t64/openssl) | HIGH | heap UAF in PKCS7_verify() (potential RCE) | Ubuntu 3.0.13-0ubuntu3.11 | ollama serves a JSON inference API, no PKCS#7/S-MIME verify; loopback, trusted client — added 2026-06-10 |
| CVE-2026-32285 | buger/jsonparser | HIGH | DoS (crafted JSON) | jsonparser 1.1.2 | JSON from trusted local backend only |
| CVE-2026-25679 | net/url | HIGH | IPv6 host-literal parsing | Go 1.25.8 / 1.26.1 | parsing DoS; trusted caller |
| CVE-2026-27137 | crypto/x509 | HIGH | email-constraint enforcement | Go 1.26.1 | cert-validation correctness, not RCE; outbound TLS only |
| CVE-2026-32280 | crypto/x509 | HIGH | DoS (chain building) | Go 1.25.9 / 1.26.2 | DoS; outbound TLS only |
| CVE-2026-32281 | crypto/x509 | HIGH | DoS (chain validation) | Go 1.25.9 / 1.26.2 | DoS; outbound TLS only |
| CVE-2026-32283 | crypto/tls | HIGH | DoS (TLS 1.3 key updates) | Go 1.25.9 / 1.26.2 | DoS; trusted peer |
| CVE-2026-33810 | crypto/x509 | HIGH | cert-validation issue | Go 1.26.2 | correctness; outbound TLS, needs MITM |
| CVE-2026-33811 | net (cgo resolver) | HIGH | long CNAME → double-free + crash (tightened from DoS-only 2026-05-27) | Go 1.25.10 / 1.26.3 | reachable only via outbound cgo DNS to a trusted resolver |
| CVE-2026-33814 | net/http2 | HIGH | DoS (SETTINGS infinite loop) | Go 1.25.10 / 1.26.3 | DoS; only our backend connects |
| CVE-2026-39820 | net/mail | HIGH | DoS (ParseAddress) | Go 1.25.10 / 1.26.3 | ollama parses no mail; effectively unreachable |
| CVE-2026-39836 | net | HIGH | panic (NUL in Dial, Windows) | Go 1.25.10 / 1.26.3 | Linux container; Windows-specific |
| CVE-2026-42499 | net/mail | HIGH | DoS (consumePhrase) | Go 1.25.10 / 1.26.3 | ollama parses no mail; effectively unreachable |
| CVE-2026-39823 | html/template | HIGH | XSS via URLs in `<meta>` content (added 2026-05-27 wave 3) | Go 1.25.10 / 1.26.3 | ollama returns JSON; renders no HTML templates |
| CVE-2026-39825 | net/http/httputil | HIGH | ReverseProxy forwards params past ParseQuery limit (added 2026-05-27 wave 3) | Go 1.25.10 / 1.26.3 | ollama is an HTTP server, not a reverse proxy; ReverseProxy unused |
| CVE-2026-39826 | html/template | HIGH | XSS via `<script>` with empty/whitespace `type` (added 2026-05-27 wave 3) | Go 1.25.10 / 1.26.3 | ollama returns JSON; renders no HTML templates |
| CVE-2026-42504 | mime | HIGH | quadratic `WordDecoder.DecodeHeader` on crafted encoded-words → CPU DoS (CWE-407, GO-2026-5038; added 2026-06-08 wave 4) | Go 1.25.11 / 1.26.4 | DoS reachable only via crafted MIME headers; 127.0.0.1, backend is the only trusted client |
| CVE-2026-27145 | crypto/x509 | HIGH | `VerifyHostname` → `matchHostnames` hostname-match correctness (not RCE; added 2026-06-23) | Go 1.25.11 / 1.26.4 | cert-validation correctness; outbound TLS (to Ollama Cloud) only, needs active MITM |
| CVE-2026-39827 | x/crypto/ssh | HIGH | authenticated SSH client repeatedly opening channels → DoS (wave 6, added 2026-06-23) | x/crypto 0.52.0 | ollama runs no SSH server / opens no SSH client → unreachable |
| CVE-2026-39828 | x/crypto/ssh | HIGH | SSH denial of service (wave 6) | x/crypto 0.52.0 | ollama runs no SSH → unreachable |
| CVE-2026-39829 | x/crypto/ssh | HIGH | SSH denial of service (wave 6) | x/crypto 0.52.0 | ollama runs no SSH → unreachable |
| CVE-2026-39830 | x/crypto/ssh | HIGH | SSH denial of service (wave 6) | x/crypto 0.52.0 | ollama runs no SSH → unreachable |
| CVE-2026-39831 | x/crypto/ssh | HIGH | FIDO/U2F security-key physical-presence check bypass (GHSA-89gr-r52h-f8rx; NVD/GHSA rate CRITICAL, Trivy HIGH; added 2026-07-09, unmasked by the pgvector krb5 waiver) | x/crypto 0.52.0 | ollama opens no SSH client and uses no FIDO/U2F keys → unreachable |
| CVE-2026-39832 | x/crypto/ssh/agent | HIGH | security bypass via improper key-restriction handling (added 2026-06-27) | x/crypto 0.52.0 | ollama opens no SSH agent client → unreachable |
| CVE-2026-39835 | x/crypto/ssh | HIGH | SSH servers using CertChecker as a public-key callback (wave 6) | x/crypto 0.52.0 | ollama runs no SSH server → unreachable |
| CVE-2026-42508 | x/crypto/ssh/knownhosts | HIGH | revocation bypass (wave 6) | x/crypto 0.52.0 | ollama does no SSH host-key checking → unreachable |
| CVE-2026-46595 | x/crypto/ssh | HIGH | SSH denial of service (wave 6) | x/crypto 0.52.0 | ollama runs no SSH → unreachable |
| CVE-2026-46597 | x/crypto/ssh | HIGH | incorrectly-placed bytes→int cast on parse (wave 6) | x/crypto 0.52.0 | ollama runs no SSH → unreachable |
| CVE-2026-25680 | x/net/html | HIGH | parsing arbitrary HTML → excessive CPU (DoS) (wave 6) | x/net 0.55.0 | ollama returns JSON, renders no HTML → unreachable |
| CVE-2026-25681 | x/net/html | HIGH | arbitrary HTML via `Render` (wave 6) | x/net 0.55.0 | renders no HTML → unreachable |
| CVE-2026-27136 | x/net/html | HIGH | arbitrary HTML via `Render` (wave 6) | x/net 0.55.0 | renders no HTML → unreachable |
| CVE-2026-39821 | x/net/idna | HIGH | privilege escalation via incorrect Punycode label processing (wave 6) | x/net 0.55.0 | outbound TLS hostname only, needs attacker-controlled IDN hostname supplied by the trusted local user |
| CVE-2026-42502 | x/net/html | HIGH | arbitrary HTML via `Render` (wave 6) | x/net 0.55.0 | renders no HTML → unreachable |
| CVE-2026-42506 | x/net/html | HIGH | arbitrary HTML via `Render` (wave 6) | x/net 0.55.0 | renders no HTML → unreachable |
