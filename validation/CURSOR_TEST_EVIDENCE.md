# Cursor Test Evidence — R1 Local Checkpoint

Date: 2026-06-28  
Checkpoint: **LOCAL VALIDATION COMPLETE** (CI / expanded UAT pending)

## Local login

| Item | Value |
|------|-------|
| URL | http://localhost:3000 |
| Settings | http://localhost:3000/settings |
| Email | `swapnilpatil.tech@gmail.com` |
| Password | `TempLocal123!` (local only) |
| Reset | `powershell -File scripts/local/Reset-LocalAdmin.ps1 -Force` |

## Git safety (pre-commit)

| Step | Command | Result |
|------|---------|--------|
| Secret scan | `python scripts/validation/secret_scan.py` | **PASSED** |
| Prohibited source scan | `python scripts/validation/prohibited_source_scan.py` | **PASSED** |
| pytest | `cd apps/api && pytest -q` | **29 passed**, 1 skipped |

## Docker stack

| Service | Status | Endpoint |
|---------|--------|----------|
| postgres | healthy | `:5432` |
| api | healthy | http://localhost:8000/health |
| web | healthy | http://localhost:3000 |
| n8n | healthy | http://localhost:5678/healthz |

OAuth JSON: `/run/secrets/google-oauth-client.json` in API container.

## Database migrations

| Step | Result |
|------|--------|
| `alembic current` | `0003_fk_not_null (head)` |
| `alembic check` | **PASSED** |
| downgrade base → upgrade head | **PASSED** |

## Live Google integration

| Check | Result |
|-------|--------|
| OAuth connected | `swapnilpatil.tech@gmail.com` |
| Encrypted tokens | 3 rows (google/gmail/drive) |
| Configured root `1yqQixjo6GGBcjwIXEfHx1STeaJHz_qOI` | **Inaccessible** with `drive.file` (expected) |
| App-created root | `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr` |
| Subfolder sync ×2 | **Idempotent** |
| Gmail sync ×2 | **PASS** (0 messages; dedup table ready) |
| Packet + Drive upload | **PASS** after app root active |

### Subfolder IDs

| Folder | ID |
|--------|-----|
| `01_Career_Vault` | `1V0xcP90y2XZPH7cABm4ByOJmvfFXy7B9` |
| `02_Application_Packets` | `1___eJy4-j8bhDHtPXzHljNkkmbkpyXmj` |
| `03_Interview_Preparation` | `1cI1GdpOSxAaZqz1uOwLFBMIldaSkVOLm` |
| `04_Consulting` | `1mcg_J6mhQzyn3u9Og9waPkbNisHjp8oR` |
| `05_Reports` | `1dp1k0kYhJp8fgHfKznZ5tbK0s58T9PCO` |
| `99_Archive` | `1WWMbm0yyu2aAN8LU4f2SQ-TATbbWXUsQ` |

## Frontend E2E

```
cd apps/web && npm run test:e2e → 1 passed
```

## Backup / restore

Career OS data restores correctly. Full dump includes n8n schema → duplicate-object noise on in-place restore (known gap).

## GitHub Actions

**NOT VERIFIED** on validation host (`gh` unavailable).

## Known gaps

- Document quality needs improvement
- ATS templates need validation
- Real Gmail content still needs more test data
- GitHub Actions needs verification
- Playwright coverage needs expansion
- Backup/restore n8n schema noise
- UI polish pending

## Verdict

**LOCAL CHECKPOINT READY** — commit documents proven local state. Production signoff requires CI watch + Cowork UAT.
