# Aarohan CareerOS — Current Status

Last updated: 2026-06-28  
Branch: `main`  
Latest tag: `r2.3.0` (`dfcc391`)  
Baseline checkpoint: `aed228d583e0b6a7760eb6091c82883cda5e5426`  
Active program: **R2** (see `docs/program/R2-PROGRAM-BOARD.md`)

## Product state

Local-first CareerOS is operational:

- Docker stack: postgres, api, web, n8n
- Auth: local admin login (`swapnilpatil.tech@gmail.com`)
- Google OAuth: connected with `drive.file` + `gmail.readonly`
- Drive: app-created root `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr`
- Job ingest (fixture, Greenhouse, Lever), scoring, packet generation
- **R2.2:** job connector registry (10 providers), `/connectors` UI, NOT_CONFIGURED for missing API keys
- **R2.3:** trust/fit scores with reasons, hard filters, role-family classification, job cards on Fresh Jobs
- Approval queue, interviews, consulting, audit log
- Application modes: Manual and Assisted enabled; Autonomous locked (UI + API)
- Schedules disabled; external email send disabled

## Local URLs

| Service | URL |
|---------|-----|
| Dashboard | http://localhost:3000 |
| Settings | http://localhost:3000/settings |
| API health | http://localhost:8000/health |
| n8n | http://localhost:5678 |

## Verification

```powershell
powershell -File scripts/validation/Verify-R2-Release-Gate.ps1
```

## R2 progress

See `docs/program/R2-PROGRAM-BOARD.md` for per-release status, commits, and tags.

## Known gaps

- Document quality / ATS template validation
- Expanded Gmail labeled-message corpus
- GitHub Actions post-R2 verification
- Playwright coverage expansion
- Backup/restore n8n schema noise
- UI modernization (R2.10)
- Cloud deploy deferred (R2.11 design only)
