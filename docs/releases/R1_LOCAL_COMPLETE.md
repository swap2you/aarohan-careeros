# R1 Local Complete — Checkpoint

Date: 2026-06-28  
Status: **LOCAL CHECKPOINT COMPLETE** — live OAuth, Drive app-root, and core validation proven locally. CI and expanded UAT remain.

## What R1 delivers

Local-first Aarohan CareerOS with:

- Secure admin login and Alembic migrations (`0001`, `0002`, `0003`)
- Job ingestion (fixture, Greenhouse, Lever, manual, Gmail read-only)
- Transparent scoring, deduplication, Career Vault evidence grounding
- Three resume profiles with DOCX/PDF generation and approval queue
- Interview Grilling Machine and consulting lead workflow
- Google OAuth (connect, callback, token storage, refresh, disconnect)
- Google Drive app-owned root + idempotent subfolder tree + packet upload
- Full dashboard IA (15 pages)
- AI budget controls, audit log, validation center
- No scheduling, no external submit, no bulk email, no auto-apply

## Local login (proven)

| Item | Value |
|------|-------|
| URL | http://localhost:3000 |
| Settings | http://localhost:3000/settings |
| Email | `swapnilpatil.tech@gmail.com` |
| Password | `TempLocal123!` (local only) |
| Reset | `powershell -File scripts/local/Reset-LocalAdmin.ps1 -Force` |

## Services

| Service | URL |
|---------|-----|
| Web | http://localhost:3000 |
| API health | http://localhost:8000/health |
| n8n | http://localhost:5678 |

## Google integration (proven)

| Item | Value |
|------|-------|
| OAuth account | `swapnilpatil.tech@gmail.com` |
| Configured manual root | `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr` (inaccessible with `drive.file`) |
| App-created root | `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr` (`aarohan-careeros`) |

### Subfolder IDs (app-created root)

| Folder | ID |
|--------|-----|
| `01_Career_Vault` | `1V0xcP90y2XZPH7cABm4ByOJmvfFXy7B9` |
| `02_Application_Packets` | `1___eJy4-j8bhDHtPXzHljNkkmbkpyXmj` |
| `03_Interview_Preparation` | `1cI1GdpOSxAaZqz1uOwLFBMIldaSkVOLm` |
| `04_Consulting` | `1mcg_J6mhQzyn3u9Og9waPkbNisHjp8oR` |
| `05_Reports` | `1dp1k0kYhJp8fgHfKznZ5tbK0s58T9PCO` |
| `99_Archive` | `1WWMbm0yyu2aAN8LU4f2SQ-TATbbWXUsQ` |

Subfolder sync run twice: **idempotent** (same IDs).

## Validation evidence (2026-06-28)

| Gate | Result |
|------|--------|
| Docker stack (4 services) | PASS |
| Alembic current/check/cycle | PASS |
| pytest | 29 passed, 1 skipped |
| Secret + prohibited scans | PASS |
| Live Google OAuth | PASS |
| Drive app-root + subfolders | PASS |
| Packet + Drive upload | PASS |
| Gmail sync (dedup ready) | PASS (0 labeled messages in mailbox) |
| Playwright smoke | 1 passed |
| Backup/restore | PASS (Career OS data; n8n schema noise) |
| GitHub Actions | **NOT VERIFIED** |

Full evidence: `validation/CURSOR_TEST_EVIDENCE.md`

## Restart commands

```powershell
docker compose ps
docker compose up -d
docker compose down
powershell -File scripts/local/Start-Aarohan.ps1 -Detached
powershell -File scripts/local/Test-Aarohan.ps1
```

## Known gaps (tomorrow)

- Document quality needs improvement
- ATS templates need validation
- Real Gmail content still needs more test data
- GitHub Actions needs verification
- Playwright coverage needs expansion
- Backup/restore n8n schema noise
- UI polish pending

No deploy, schedule enablement, or auto-apply was performed.
