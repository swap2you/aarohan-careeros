# R2 Program Board

Status values: `NOT_STARTED`, `IN_PROGRESS`, `BLOCKED_EXTERNAL`, `BLOCKED_TECHNICAL`, `DONE`, `DEFERRED`.

| Release | Status | Commit | Tag | Tests | External blockers | Notes |
|---|---|---|---|---|---|---|
| R2.0 Baseline/Governance | DONE | 98dae5921668e8b2fed5a8aa84835c61d28943c8 | r2.0.0 | gate PASS | | |
| R2.1 Duplicate Protection | DONE | 6a484383929bf6b4f1f5c378341a7d1240baa203 | r2.1.0 | 37 passed, 1 skipped | | ledger + duplicate engine |
| R2.2 Job Connectors | DONE | 81aef74c73b783dd34117674ff0e0aca15940bf1 | r2.2.0 | 44 passed, 1 skipped | | provider registry + UI |
| R2.3 Trust/Matching | DONE | dfcc391 | r2.3.0 | 50 passed, 1 skipped | | trust + hard filters |
| R2.4 Document Quality | DONE | f06a5a9 | r2.4.0 | 58 passed, 1 skipped | | ATS diagnostics + answer sheet |
| R2.5 Manual Workflow | DONE | 7a0a93b | r2.5.0 | 76 passed (CI Postgres) | Drive OAuth owner step | CONDITIONAL GO |
| R2.6 Assisted Apply | DONE | 83bbe66 | r2.6.0 | 84 passed, 8 skipped | | assisted API + ATS detection |
| R2.6.1 Auth Session | DONE | (pending tag) | r2.6.1 | 108 API + 7 Playwright | Drive OAuth owner step | patch on r2.6.0 |
| R2.7 Gmail Lifecycle | NOT_STARTED | | | | | paused until r2.6.1 green |
| R2.8 Interview Intelligence | NOT_STARTED | | | | | |
| R2.9 Ask Aarohan/TTS | NOT_STARTED | | | | | |
| R2.10 Modern UI | NOT_STARTED | | | | | |
| R2.11 Cloud Readiness | NOT_STARTED | | | | | |
| R2.12 Cleanup/Hardening | NOT_STARTED | | | | | |
| R2.13 UAT/RC | NOT_STARTED | | | | | |

## Per-release evidence

Recorded in `docs/releases/R2.x.0.md` for each completed release.
