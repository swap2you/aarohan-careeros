# Aarohan CareerOS — Current Status

Last updated: 2026-06-28  
Branch: `main`  
Baseline checkpoint: `aed228d583e0b6a7760eb6091c82883cda5e5426`  
Active program: **R2** (see `docs/program/R2-PROGRAM-BOARD.md`)

## Product state

Local-first CareerOS is operational:

- Docker stack: postgres, api, web, n8n
- Auth: local admin login (`swapnilpatil.tech@gmail.com`)
- Google OAuth: connected with `drive.file` + `gmail.readonly`
- Drive: app-created root `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr`
- Job ingest (fixture, Greenhouse, Lever), scoring, packet generation
- Approval queue, interviews, consulting, audit log
- Schedules disabled; external email send disabled; autonomous apply locked (R2)

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
