# Security finding disposition (R2.13.0-rc3)

**Date:** 2026-06-27  
**Baseline:** `r2.13.0-rc3` (post-rc2 closure)  
**Sources:** `CODEX-REVIEW-RESULTS.md`, `CLAUDE-CODE-REVIEW-RESULTS.md`

## Critical

| ID | Disposition | Evidence |
|----|-------------|----------|
| C-01 JWT parallel auth | **FIXED** | `allow_legacy_jwt_auth` defaults `false`; session cookie + opaque bearer first in `dependencies.py`; tests set legacy flag only in `conftest.py` |
| C-02 Encryption fallback | **FIXED** | `crypto.py` requires `TOKEN_ENCRYPTION_KEY` outside test/local; encrypt uses primary key only; decrypt tries legacy `APP_SECRET` in development for migration |

## High

| ID | Disposition | Evidence |
|----|-------------|----------|
| H-01 OAuth in-memory state | **ACCEPTED (local)** | Documented in `KNOWN-LIMITATIONS.md`; cloud ADR required before multi-worker deploy |
| H-02 Session token in login JSON | **FIXED** | `expose_session_token_in_login_response` defaults `false`; login returns empty `access_token` for browser clients |
| H-03 Gmail sync race | **FIXED** | `_claim_message` uses nested transaction + `IntegrityError` handling in `gmail_lifecycle.py` |
| H-04 Packet partial commit | **FIXED** | `generate_application_packet` uses `flush` during generation; single commit after files written |
| H-05 ATS substring hosts | **FIXED** | `ats_detection.py` host suffix equality; `test_linkedin_substring_host_not_prohibited` |
| H-06 Permanent duplicate override | **FIXED** | `OVERRIDE_TTL_DAYS = 30` in `duplicate_risk.py` |
| H-07 Legacy recruiter POST | **FIXED** | `POST /api/recruiter-signals` returns 403 outside test/local without `gmail_message_id` |

## Medium (documented / partial)

| ID | Disposition |
|----|-------------|
| M-01 Ask SQL mode unused | **OPEN** — documented limitation |
| M-02 Silent decrypt failure | **MITIGATED** — `get_token` skips undecryptable rows; `integration_status` exposes `token_usable` |
| M-03 Duplicate URL O(n) | **OPEN** — acceptable at current scale |

## Open Critical / High for final `r2.13.0`

**Zero open Critical** in validated code paths.  
**Zero open High security/data-integrity** after rc3 fixes; H-01 remains **accepted local limitation** only.
