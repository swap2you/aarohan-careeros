# R2 Program Board

Status values: `NOT_STARTED`, `IN_PROGRESS`, `IN_VALIDATION`, `CONDITIONAL_GO`, `FULL_GO`, `BLOCKED_EXTERNAL`, `DONE`, `DEFERRED`.

| Release | Status | Commit | Tag | Tests | External blockers | Notes |
|---|---|---|---|---|---|---|
| R2.0 Baseline/Governance | DONE | 98dae59 | r2.0.0 | gate PASS | | |
| R2.1 Duplicate Protection | DONE | 6a48438 | r2.1.0 | 37 passed | | |
| R2.2 Job Connectors | DONE | 81aef74 | r2.2.0 | 44 passed | | |
| R2.3 Trust/Matching | DONE | dfcc391 | r2.3.0 | 50 passed | | |
| R2.4 Document Quality | DONE | f06a5a9 | r2.4.0 | 58 passed | | |
| R2.5 Manual Workflow | **CONDITIONAL_GO** | 7a0a93b | r2.5.0 | 76 passed | Live Drive OAuth | Fixture/unit PASS; live upload pending owner |
| R2.6 Assisted Apply | DONE | 83bbe66 | r2.6.0 | 84 passed | | |
| R2.6.1 Auth Session | DONE | 353c330 | r2.6.1 | 108 API + Playwright | | |
| R2.7 Gmail Lifecycle | **CONDITIONAL_GO** | 3ead743 | r2.7.0 | 116 API + Playwright | Live inbox messages | Fixture/classification PASS; per-source live pending |
| R2.8 Interview Intelligence | DONE | 088c7ce | r2.8.0 | 112 API + Playwright | | |
| R2.9 Ask Aarohan/TTS | DONE | 3cf1099 | r2.9.0 | 112 API + Playwright | | Read-only; live TTS playback owner verify |
| R2.10 Modern UI | DONE | 27ab54d | r2.10.0 | build + Playwright | | |
| R2.11 Cloud Readiness | DONE | 6a785c0 | r2.11.0 | docs | | Architecture only |
| R2.12 Cleanup/Hardening | DONE | 4d9b99b | r2.12.0 | Verify-Full-R2 | | |
| R2.13 UAT/RC | **IN_VALIDATION** | edb540d | r2.13.0-rc1 | full gate | Reviews done; live Drive/Gmail; owner UAT | Package prep complete; **not** final sign-off |

## Validation phase (post-rc1)

- RC baseline: `docs/validation/RC-BASELINE-VERIFICATION.md`
- Live evidence: `docs/validation/LIVE-VALIDATION-EVIDENCE.md`
- Reviews: `docs/validation/review/CODEX-REVIEW-RESULTS.md`, `CLAUDE-CODE-REVIEW-RESULTS.md`
- UAT: `docs/validation/uat/UAT-RESULTS.md`
- Defects: `docs/validation/FINAL-DEFECT-REGISTER.md`

## Owner actions before `r2.13.0`

1. `Start-Aarohan.ps1` → live Drive packet v01/v02 proof
2. Gmail sync on real labeled messages (LinkedIn, Indeed, Dice, USAJOBS minimum)
3. Cowork UAT sign-off
4. Address or accept High defects in `FINAL-DEFECT-REGISTER.md`
