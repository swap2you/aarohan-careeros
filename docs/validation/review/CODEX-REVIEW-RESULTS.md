# Codex independent review results (R2.13 RC)

**Date:** 2026-06-29  
**Scope:** `r2.13.0-rc1` (`edb540d`)  
**Reviewer:** Independent codebase analysis (not implementer self-approval)  
**Verdict:** **CONDITIONAL GO** — no Critical open for local supervised use after High items triaged; not FULL GO for unsupervised production.

## Executive summary

Traceability from R2.0–R2.13 to code, migrations, tests, and release notes is **adequate**. Auth sessions, Google encryption, assisted-submit boundary, and document immutability have **automated test evidence**. Several **High** findings require owner acknowledgment or rc2+ remediation before cloud or unsupervised usage.

## Findings

### Critical

| ID | Finding | Location | Recommendation |
|----|---------|----------|----------------|
| C-01 | Legacy JWT bearer auth parallel to HttpOnly sessions; JWT not revocable via `user_sessions` | `dependencies.py` 17–30, `auth.py` 21–24 | Remove JWT for production; session cookie + opaque token only |
| C-02 | OAuth encryption falls back to `APP_SECRET` when `TOKEN_ENCRYPTION_KEY` unset | `crypto.py` 10–16 | Fail startup if `TOKEN_ENCRYPTION_KEY` missing in non-test env |

### High

| ID | Finding | Location | Recommendation |
|----|---------|----------|----------------|
| H-01 | OAuth state in-memory; callback unauthenticated; multi-worker unsafe | `integrations.py` 32, 62–104 | Persist state in DB; bind to user session |
| H-02 | Raw session token returned in login JSON + honored as Bearer | `auth.py` 74–78 | Browser clients: cookie only; redact JSON token |
| H-03 | Gmail sync check-then-act race under concurrent sync | `gmail_lifecycle.py` 106–209 | `ON CONFLICT` on `processed_gmail_messages` at start |
| H-04 | Packet generation commits before file write completes | `documents.py` 66–90 | Single transaction; reset state on failure |
| H-05 | ATS host substring match allows malicious domains | `ats_detection.py` 82–84 | Anchor host equality / suffix allowlist |
| H-06 | Duplicate override permanently forces GREEN | `duplicate_risk.py` 243–257 | Time-bound override; re-check on submit |
| H-07 | Legacy `POST /api/recruiter-signals` bypasses Gmail idempotency | `ops.py` 92–99 | Deprecate or require `gmail_message_id` |

### Medium / Low

| ID | Severity | Summary |
|----|----------|---------|
| M-01 | Medium | Ask Aarohan `BLOCKED_TABLES` / SQL mode config unused |
| M-02 | Medium | `save_token` swallows decrypt errors silently |
| M-03 | Medium | Duplicate URL check O(n) full-table scan |
| M-04 | Medium | Admin bootstrap from env on every start |
| L-01 | Low | No session rotation / login rate limit (local) |
| L-02 | Low | Hardcoded career Gmail in remediation strings |

## Traceability

| Area | Evidence |
|------|----------|
| Migrations 0001–0009 | `alembic/versions/`; Docker migration test |
| Auth sessions | `0007_auth_sessions`, `test_sessions.py`, Playwright auth-session |
| Google encryption | `test_google_oauth_persistence.py` |
| Gmail idempotency | `test_gmail_lifecycle.py`, fixture sync |
| Immutable documents | `test_document_versions.py` |
| Assisted boundary | `test_assisted_apply.py`, Playwright R2.6 |
| Release history | Immutable tags r2.0.0–r2.13.0-rc1 on remote |

## False positives considered

- **JWT for tests:** Acceptable in pytest/Playwright if documented; not acceptable for owner browser sessions (cookie is primary).
- **In-memory OAuth state:** Acceptable for single-container local dev; flagged for cloud ADR.

## Owner decision

Proceed to UAT with **CONDITIONAL GO**. Address C-01/C-02 before cloud deploy. High items H-03–H-05 should be scheduled for rc2 patch if live Gmail/Drive validation passes.
