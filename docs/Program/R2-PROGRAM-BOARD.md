# R2 Program Board

Status values: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED_EXTERNAL`, `BLOCKED_TECHNICAL`, `DONE`, `DEFERRED`.

| Release | Status | Commit | Tag | Tests | External blockers | Notes |
|---|---|---|---|---|---|---|
| R2.0 Baseline/Governance | DONE | 98dae59 | r2.0.0 | gate PASS | | |
| R2.1 Duplicate Protection | DONE | 6a48438 | r2.1.0 | 37 passed | | ledger + duplicate engine |
| R2.2 Job Connectors | DONE | 81aef74 | r2.2.0 | 44 passed | | provider registry + UI |
| R2.3 Trust/Matching | DONE | dfcc391 | r2.3.0 | 50 passed | | trust + hard filters |
| R2.4 Document Quality | DONE | f06a5a9 | r2.4.0 | 58 passed | | ATS diagnostics + answer sheet |
| R2.5 Manual Workflow | DONE | 7a0a93b | r2.5.0 | 76 passed | Drive OAuth owner step | CONDITIONAL GO |
| R2.6 Assisted Apply | DONE | 83bbe66 | r2.6.0 | 84 passed | | assisted API + ATS detection |
| R2.6.1 Auth Session | DONE | 353c330 | r2.6.1 | 108 API + Playwright | Drive OAuth owner step | patch on r2.6.0 |
| R2.7 Gmail Lifecycle | DONE | 3ead743 | r2.7.0 | 116 API + Playwright | | fixture + classification |
| R2.8 Interview Intelligence | DONE | 088c7ce | r2.8.0 | 112 API + Playwright | | evidence-bound packs |
| R2.9 Ask Aarohan/TTS | DONE | 3cf1099 | r2.9.0 | 112 API + Playwright | | read-only Ask + TTS fallback |
| R2.10 Modern UI | DONE | 27ab54d | r2.10.0 | build + Playwright | | design tokens + reports |
| R2.11 Cloud Readiness | DONE | 6a785c0 | r2.11.0 | docs | | architecture only |
| R2.12 Cleanup/Hardening | DONE | 4d9b99b | r2.12.0 | Verify-Full-R2 | | validation script |
| R2.13 UAT/RC | DONE | (rc commit) | r2.13.0-rc1 | full gate | Drive OAuth owner | release candidate |

## Per-release evidence

Recorded in `docs/releases/R2.x.0.md` for each completed release.

## Owner actions

1. Live Google Drive OAuth — upgrade R2.5 to FULL GO
2. Cowork UAT — `docs/validation/uat/COWORK-UAT-PACKAGE.md`
