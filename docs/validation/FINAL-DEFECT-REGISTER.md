# Final defect register (R2.13 RC)

**Date:** 2026-06-29  
**Baseline:** `r2.13.0-rc1`

## Open defects

### Critical (must be zero before `r2.13.0`)

| ID | Source | Summary | Status |
|----|--------|---------|--------|
| — | — | None open for local supervised scope | — |

*Codex C-01/C-02 are architectural risks for cloud/production hardening — tracked as High for rc2, not blocking local UAT if owner supervises assisted apply.*

### High (data integrity / security)

| ID | Source | Summary | Status | Owner decision |
|----|--------|---------|--------|----------------|
| D-H01 | Codex | JWT bearer parallel auth path | **OPEN** | Defer to post-rc1 patch; cookie is primary for UI |
| D-H02 | Codex | OAuth state in-memory | **OPEN** | Acceptable local single-container |
| D-H03 | Codex | Gmail sync race | **OPEN** | Defer rc2; fixture idempotency tested |
| D-H04 | Codex | Packet generation partial failure state | **OPEN** | Defer rc2 |
| D-H05 | Codex | ATS host substring matching | **OPEN** | Owner must verify URLs manually in assisted flow |
| D-H06 | Codex | Permanent duplicate override | **OPEN** | Documented; use overrides sparingly |
| D-H07 | Codex | Legacy recruiter-signals POST | **OPEN** | Defer rc2 deprecation |

### Medium

| ID | Source | Summary | Status |
|----|--------|---------|--------|
| D-M01 | Codex | Ask SQL mode config unused | OPEN — documented limitation |
| D-M02 | Codex | Silent OAuth decrypt failure | OPEN |
| D-M03 | Codex | Duplicate URL O(n) scan | OPEN |
| D-M04 | Gate | `Verify-Full-R2.ps1` pytest stderr false fail | **FIXED** rc2 |
| D-M05 | Ops | Missing `alembic_version` on rebuild | **MITIGATED** — stamp head runbook |

### Low

| ID | Source | Summary | Status |
|----|--------|---------|--------|
| D-L01 | Codex | No login rate limit | OPEN — local only |
| D-L02 | Codex | Hardcoded career email fallback | OPEN |
| D-L03 | UAT | Backup/restore not executed | OPEN — owner runbook |

### Validation blocked (not defects)

| ID | Summary |
|----|---------|
| V-B01 | Live Drive — owner OAuth + SecretStore session |
| V-B02 | Live Gmail per-source — owner inbox access |
| V-B03 | TTS live playback — owner UI verification |

## Fixed in rc2 validation commit

| ID | Fix |
|----|-----|
| D-M04 | `Verify-Full-R2.ps1` checks pytest exit code only |
| — | Added `Live-RC-Validation.ps1`, `live_rc_validation.py`, validation evidence docs |

## Release gate

| Criterion | Met? |
|-----------|------|
| Zero open Critical (data loss / secret exposure / auth bypass in validated paths) | **YES** for local scope |
| Zero open High data-integrity in validated paths | **NO** — owner acknowledgment required |
| Medium documented | **YES** |
| Live Drive FULL GO | **NO** |
| Live Gmail FULL GO | **NO** |
| Independent reviews complete | **YES** |
| Cowork UAT automated paths | **YES** |

**Cannot tag `r2.13.0` until V-B01/V-B02 complete and owner signs UAT.**
