# Cowork UAT package (R2.13)

Owner-driven user acceptance testing. Record results in `docs/validation/UAT-RESULTS-TEMPLATE.md`.

## Prerequisites

- Stack running: `scripts/local/Start-Aarohan.ps1`
- Admin credentials from SecretStore (`ADMIN_EMAIL` / `ADMIN_PASSWORD`)
- Optional: live Google OAuth for Drive/Gmail sections

## Scenarios

| # | Scenario | Steps | Pass criteria |
|---|----------|-------|---------------|
| 1 | Login | Open `/login`, sign in | Executive Overview loads |
| 2 | Remember Me | Check Remember Me, login, restart Docker web+api | Still authenticated |
| 3 | Logout | Click Logout | Redirect login; protected routes blocked |
| 4 | Google persistence | Connect Google, restart stack | Status READY without re-consent |
| 5 | Job search | Run connector/fixture ingest | Jobs appear on Fresh Jobs |
| 6 | Connector health | Settings/Connectors | Status human-readable |
| 7 | Job trust/fit | Open job detail | Trust + fit scores visible |
| 8 | Duplicate warning | Ingest overlapping jobs | Warning surfaced |
| 9 | Vendor conflict | View representation conflicts | Clear messaging |
| 10 | Packet generation | Generate application packet | DOCX/PDF local paths |
| 11 | Validation | Run validation workflow | Pass/fail readable |
| 12 | Drive links | After live OAuth | Dashboard links open folder |
| 13 | Manual apply | Mark manual apply step | Timeline updates |
| 14 | Assisted apply | Fixture assisted flow | Stops before submit |
| 15 | Stop-before-submit | Confirm no auto-submit | No external send |
| 16 | Application timeline | Pipeline view | Status history |
| 17 | Gmail sync | Recruiter signals → Sync fixtures | Table populated |
| 18 | Recruiter linking | Classify/correct signal | Persists after refresh |
| 19 | Interview brief | Generate pack | Evidence-only STAR stories |
| 20 | Ask Aarohan | `/ask` question | Cited answer, no secrets |
| 21 | TTS | Read aloud | Audio or graceful fallback |
| 22 | UI reconciliation | Spot-check counts vs API | Numbers match |
| 23 | Backup/restore | `Backup-Aarohan.ps1` / `Restore-Aarohan.ps1` | Data restored |
| 24 | Unauthorized routes | Visit `/jobs` logged out | Redirect login, no flash |
| 25 | Immutable submitted | Submit packet v01, regenerate | v01 unchanged |

## Sign-off

- Tester name, date, overall GO / CONDITIONAL / NO GO
