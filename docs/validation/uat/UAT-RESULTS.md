# Cowork UAT results (R2.13 RC)

**Date:** 2026-06-27  
**Baseline:** `r2.13.0-rc3`  
**Overall:** **CONDITIONAL GO** — automated paths PASS; live Drive/Gmail **FAIL** until owner **Reconnect Google**; final sign-off pending.

| # | Scenario | Result | Notes |
|---|----------|--------|-------|
| 1–4 | Auth session | **PASS** | 19 Playwright tests |
| 5 | Google persistence | **PARTIAL** | DB rows present; `token_usable=false` until reconnect |
| 6–12 | Workflow / packet | **PASS** | Fixture + API tests |
| 13 | Drive links | **FAIL** | Live token decrypt |
| 14–17 | Apply / timeline | **PASS** | |
| 18–19 | Gmail | **PARTIAL** | Fixture PASS; live blocked |
| 20–21 | Interview / Ask | **PASS** | |
| 22 | TTS | **PARTIAL** | Unavailable without `Start-Aarohan.ps1` key load |
| 23 | UI cleanup | **PASS** | Settings plain-English validation; collapsed technical JSON |
| 24 | Backup/restore | **PASS** | Isolated `career_os_validation` |
| 25 | Immutable submitted | **PASS** | Unit tests |

## Sign-off

| Role | Status |
|------|--------|
| Automated UAT | **CONDITIONAL GO** |
| Owner Cowork UAT | **Pending** |
| Independent review | **CONDITIONAL GO** (rc3 security fixes applied) |
