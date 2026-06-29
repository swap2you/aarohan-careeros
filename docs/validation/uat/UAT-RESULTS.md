# Cowork UAT results (R2.13 RC)

**Date:** 2026-06-29  
**Baseline:** `r2.13.0-rc1` (`edb540d`)  
**Executor:** Automated Playwright + API checks where possible; live OAuth/Gmail blocked without unlocked SecretStore in validation session.

**Overall:** **CONDITIONAL GO** — automated critical paths PASS; live Drive/Gmail and SecretStore-gated scenarios **BLOCKED** pending owner session.

| # | Scenario | Result | Evidence / notes |
|---|----------|--------|------------------|
| 1 | Login | **PASS** | Playwright `auth-session.spec.ts`, `r25-workflow.spec.ts` |
| 2 | Remember Me | **PASS** | `test_sessions.py`, Playwright auth-session |
| 3 | Restart persistence | **PASS** | Documented `AUTH-SESSION-AND-GOOGLE-PERSISTENCE.md` |
| 4 | Logout | **PASS** | Playwright auth-session |
| 5 | Google persistence | **BLOCKED** | SecretStore not unlocked in validation session; owner must verify after Settings OAuth |
| 6 | Run job search | **PASS** | Fixture ingest Playwright + API |
| 7 | Connector health | **PASS** | Connectors UI; status categorical |
| 8 | Trust and fit | **PASS** | R2.3 tests + job detail UI |
| 9 | Duplicate block | **PASS** | `r25-workflow` exact duplicate API test |
| 10 | Vendor conflict | **PASS** | `r25-workflow` representation warning API |
| 11 | Generate packet | **PASS** | `r25-workflow` applications page |
| 12 | Validate packet | **PASS** | Validation workflow tests |
| 13 | Drive links | **BLOCKED** | Requires live Drive OAuth (R2.5 CONDITIONAL) |
| 14 | Manual apply | **PASS** | Apply readiness API test |
| 15 | Assisted apply fixture | **PASS** | `r26-assisted.spec.ts` |
| 16 | Stop-before-submit | **PASS** | Assisted submit 403 test |
| 17 | Application timeline | **PASS** | Workflow timeline service tests |
| 18 | Gmail sync | **PASS** (fixture) | `r27-gmail.spec.ts`; live **BLOCKED** without owner inbox |
| 19 | Recruiter/interview linkage | **PASS** (fixture) | Gmail lifecycle tests |
| 20 | Interview brief | **PASS** | `r28-interview.spec.ts` |
| 21 | Ask Aarohan | **PASS** | `r29-ask.spec.ts`; secret block in `test_ask_aarohan.py` |
| 22 | TTS | **PARTIAL** | API fallback test PASS; live OpenAI playback requires owner key + UI |
| 23 | UI/API reconciliation | **PASS** | Reports dashboard human-readable metrics |
| 24 | Backup/restore | **NOT RUN** | Scripts exist; owner must run `Backup-Aarohan.ps1` / `Restore-Aarohan.ps1` |
| 25 | Submitted-document immutability | **PASS** | `test_document_versions.py` |

## Defect IDs raised from UAT

| ID | Severity | Summary |
|----|----------|---------|
| UAT-B01 | — | Live Drive validation blocked — owner OAuth step |
| UAT-B02 | — | Live Gmail per-source validation blocked — owner inbox |
| UAT-B03 | Low | Backup/restore not executed in this validation run |

## Sign-off

| Role | Status |
|------|--------|
| Automated UAT | CONDITIONAL GO |
| Owner UAT | **Pending** |
