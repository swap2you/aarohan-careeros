# Final defect register (R2.13 RC)

**Date:** 2026-06-27  
**Baseline:** `r2.13.0-rc3`

## Open defects

### Critical

| ID | Summary | Status |
|----|---------|--------|
| — | None open | — |

### High (security / data integrity)

| ID | Summary | Status |
|----|---------|--------|
| D-H01 | OAuth state in-memory (multi-worker) | **ACCEPTED** local single-container — see `KNOWN-LIMITATIONS.md` |
| — | Codex C-01, C-02, H-02–H-07 | **FIXED** in rc3 — see `SECURITY-DISPOSITION-R2.13-RC3.md` |

### Medium

| ID | Summary | Status |
|----|---------|--------|
| D-M01 | Ask SQL mode config unused | OPEN |
| D-M02 | OAuth decrypt failure UX | **MITIGATED** — `token_usable` flag; reconnect path documented |
| D-M03 | Duplicate URL O(n) scan | OPEN |
| D-M04 | Verify-Full-R2 pytest stderr | **FIXED** rc2 |
| D-M05 | Missing alembic_version on rebuild | **MITIGATED** |

### Low

| ID | Summary | Status |
|----|---------|--------|
| D-L01 | No login rate limit | OPEN — local |
| D-L02 | Hardcoded career email fallback | OPEN |
| D-L03 | Backup/restore | **FIXED** rc3 — isolated `career_os_validation` restore |

### Validation blocked (not code defects)

| ID | Summary |
|----|---------|
| V-B01 | Live Drive — **Reconnect Google** (token decrypt mismatch after key rotation) |
| V-B02 | Live Gmail per-source — same token blocker |
| V-B03 | TTS live playback — `AI_API_KEY` not in container unless `Start-Aarohan.ps1` |

## Release gate

| Criterion | Met? |
|-----------|------|
| Zero open Critical | **YES** |
| Zero open High (except accepted H-01 local) | **YES** |
| Automated tests | **YES** — 113 API, 19 Playwright |
| Live Drive FULL GO | **NO** |
| Live Gmail FULL GO | **NO** |
| Cowork owner UAT sign-off | **NO** |

**Do not tag `r2.13.0` until V-B01/V-B02 complete and owner signs UAT.**
