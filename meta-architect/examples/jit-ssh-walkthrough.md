# Worked example — decomposing "JIT SSH access to production"

This is an **illustrative** end-to-end walkthrough (not a live run) of what the architect
produces for one realistic requirement. It shows the artefacts `decompose-requirement` would
write into the vault, plus the teaching trail it leaves. Use it to see the doctrine in motion.

> **Requirement:** "Add just-in-time (JIT) SSH access to production servers — an engineer
> requests access, their manager approves, the session is time-boxed and recorded."

---

## What the architect writes: `proposals/jit-ssh-access.md`

```markdown
---
type: proposal
slug: jit-ssh-access
updated: 2026-06-01
status: draft
related:
  - "[[access-broker]]"
  - "[[session-recorder]]"
---

# Proposal — JIT SSH access to production

## Layers

- **User / personas** — *engineer* (requests, low standing trust to prod), *manager*
  (approves; this is a **trust boundary (granica zaufania)** — the request crosses from
  low-trust to privileged), *auditor* (reads evidence, never grants).
- **Business** — reduce standing access (audit/insurance driver); demonstrate least privilege.
- **Domain** — ubiquitous language: *access request*, *grant*, *session*, *approval*,
  *revocation*, *recording*. (No "permission" — too vague; we say *grant*.)
- **Data** — `access_request` (who, target host, reason, TTL), `grant` (approver, granted_at,
  expires_at), `session_recording` (grant_id, started_at, artefact_uri). Source of truth for
  "is this grant live?" is the **access-broker**, not the SSH host.
- **Behavior** — a state machine over the request (see below).
- **Errors** — broker unreachable → **fail-closed** (domyślnie zamknięty: on failure, deny).
  Approval-service down must NOT auto-approve.
- **Security** — threat: an engineer self-approving; an expired grant still usable; recording
  tampered. Abuse path: requesting a host unrelated to the stated reason.
- **Compliance / Audit** — every grant and every session must leave a tamper-evident record,
  retained per policy; the recording is the evidence.
- **Operations** — observability: alert on grants > N minutes, on any access without a grant.

## Stations

| Station | Present? |
|---------|----------|
| Identity | ✅ engineer + manager identities asserted via SSO |
| Intent | ✅ "reason" field on the request |
| Policy | ⚠️ *gap* — who may approve for which hosts is undefined → open question |
| Decision | ✅ manager approval |
| Access | ✅ short-lived credential / signed cert |
| Monitoring | ✅ session recording + live alerts |
| Evidence | ✅ recording + immutable grant log |
| Expiry | ✅ TTL on the grant |
| Review | ⚠️ *gap* — no periodic re-attestation of who can approve → open question |

## Data flow

​```mermaid
flowchart LR
  E[Engineer] -->|request + reason + TTL| B[Access broker]
  B -->|approval request| M[Manager]
  M -->|approve / deny| B
  B -->|on approve: issue short-lived cert| H[(Prod host)]
  E -->|SSH with cert| H
  H -->|stream| R[Session recorder]
  B -->|grant + expiry| L[(Immutable audit log)]
  R -->|artefact uri| L
​```

## State & invariants

State machine `requested → approved → active → expired | revoked` (all of expired/revoked are
terminal). Guards enforce the invariants; the `approve` and `start` transitions emit evidence.

**Invariants:**
- No standing access — every prod session is backed by a live, unexpired grant.
- An engineer can never approve their own request (separation of duties).
- A grant past `expires_at` is unusable, even mid-session (session is cut).
- Every grant and session leaves an immutable audit record.

## Decision register

**D1 — Credential mechanism.** *Context:* need short-lived prod access.
*Options:* (a) short-lived SSH certificate (CA-signed, TTL); (b) ephemeral user + key; (c)
bastion with per-session token. *My proposal:* (a) — TTL is native, no account lifecycle.
*Open questions:* do we already run an SSH CA? what TTL is acceptable to ops?

**D2 — Recorder placement.** *Options:* host-side agent vs bastion-side proxy.
*My proposal:* bastion proxy (engineer's host can't disable its own recorder — fail-closed on
recording). *Open question:* does all prod SSH already route through a bastion?

## But what if…
- …the broker is up but the recorder is down? → **fail-closed**: deny the session; a session
  we can't record is a session we can't evidence.
- …a grant expires mid-session? → terminate the live session at expiry, don't just block new ones.
- …the manager approves, then leaves the company before the session starts? → grant still valid
  until TTL; revocation is separate. (Flagged: is that acceptable?)
- …two requests for the same host race? → independent grants; no implicit exclusivity.

## Gaps for the product owner
- **Policy gap:** the approver-to-host mapping is undefined (Station: Policy).
- **Review gap:** no re-attestation cadence for approvers (Station: Review).
- Retention period for recordings is unspecified (Compliance/Audit layer).
```

---

## A decision the human accepted → `decisions/0001-ssh-cert-jit-access.md`

Once you accept **D1**, the architect drafts a MADR ADR. This one **escalates** to the fuller
form automatically — it has 3 live options *and* crosses a security boundary:

```markdown
# ADR 0001 — Short-lived SSH certificates for JIT prod access

## Decision drivers
- must fail closed · no standing credentials · native expiry · auditable issuance

## Considered options
- Short-lived CA-signed SSH certificate · Ephemeral user+key · Bastion per-session token

### Short-lived certificate
- **Pros:** TTL native; no account lifecycle; issuance is centrally logged.
- **Cons:** requires an SSH CA and host trust config.
…

## Decision
CA-signed short-lived certificates, TTL-bounded, issued only against a live grant.

## Consequences
- **Good:** expiry is intrinsic; issuance is the audit point.
- **Cost we accept:** we must run and protect an SSH CA (a new high-value asset).
```

---

## The teaching trail it leaves

**`glossary/` gains** (each its own note, cross-linked):

```markdown
### fail-closed (domyślnie zamknięty)
- **Definition:** on failure, deny rather than allow.
- **Answers:** what should happen when the security control itself breaks?
- **First encountered in:** [[jit-ssh-access]]
```

**`learning-log.md` gains:**
```markdown
- 2026-06-01 · **trust boundary** · appeared in [[jit-ssh-access]] · the request crossing from engineer to manager is the exact line where enforcement must live for THIS feature.
- 2026-06-01 · **separation of duties** · appeared in [[jit-ssh-access]] · it's why "engineer can't self-approve" is an invariant, not a nice-to-have.
```

---

## What a later `review-architecture` might surface

```markdown
## Drift — risk
- `access-broker` component note claims grants are checked on every connection, but the new
  bastion config caches grant state for 60s → an expired grant stays usable up to a minute.
  Near-miss against invariant "a grant past expires_at is unusable".

## Concepts worth studying
- **TOCTOU (time-of-check to time-of-use)** — the 60s cache is a classic TOCTOU window; worth
  reading why check-then-use gaps are exploitable.
```

---

## The research-backed choices behind this tool

- **Packaging = Claude Code plugin** (not the Agent SDK). The SDK is for embedding the agent
  engine in your own app; here Claude Code *is* the app and the architect is skills + a persona.
- **ADRs = MADR** — research-backed and consistent with common house styles; lean-with-escalation.
- **Vault frontmatter = `type/slug/updated/status/related`** with `[[wikilinks]]` — Obsidian-native,
  so the vault is both machine-readable and human-wander-able.
- **Pedagogy = vocabulary-first + organic knowledge graph + progressive disclosure** — terms
  anchored to the questions they answer, grown only as real work surfaces them.

## How it differs from a generic architect agent

A generic agent would answer "here's how I'd build JIT SSH" in chat and stop. This tool instead
left behind a proposal, a state machine, four named invariants, two **open** decisions (it did
not pick for you), an edge-case list, explicit PO gaps, two glossary nodes, and two learning-log
lines — durable, versioned, and teaching. That difference *is* the product.
