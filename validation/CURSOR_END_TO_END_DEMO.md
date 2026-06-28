# Cursor End-to-End Demo — R1 Local Checkpoint

Date: 2026-06-28

## Login

| Item | Value |
|------|-------|
| Dashboard | http://localhost:3000 |
| Settings | http://localhost:3000/settings |
| Email | `swapnilpatil.tech@gmail.com` |
| Password | `TempLocal123!` |
| Reset admin | `powershell -File scripts/local/Reset-LocalAdmin.ps1 -Force` |

## Restart stack

```powershell
docker compose ps
docker compose up -d
docker compose down
powershell -File scripts/local/Start-Aarohan.ps1 -Detached
powershell -File scripts/local/Test-Aarohan.ps1
```

## Proven demo path (2026-06-28)

| Step | Result |
|------|--------|
| Sign in at dashboard | PASS |
| Connect Google as `swapnilpatil.tech@gmail.com` | PASS |
| OAuth tokens stored (encrypted) | PASS |
| Configured manual root inaccessible | Expected (`drive.file`) |
| Create Aarohan Drive Root | PASS → `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr` |
| Sync subfolders ×2 | PASS (idempotent) |
| Fixture ingest + packet + Drive upload | PASS |
| Gmail sync ×2 | PASS (0 messages; dedup ready) |

## Drive layout (app-created root)

Root: `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr` (`aarohan-careeros`)

Subfolders: `01_Career_Vault`, `02_Application_Packets`, `03_Interview_Preparation`, `04_Consulting`, `05_Reports`, `99_Archive` — IDs in `validation/CURSOR_TEST_EVIDENCE.md`.

## Sample packet paths

- `/app/generated/job_1/Example_Health_Tech_Director_of_Quality_Engineering_qe_leadership_20260628.docx`
- `/app/generated/job_1/Example_Health_Tech_Director_of_Quality_Engineering_qe_leadership_20260628.pdf`

## Automated script

```powershell
python scripts/validation/r1_local_demo.py
```

Results: `artifacts/r1_demo_results.json` (gitignored).

## Known gaps

- Document quality / ATS templates
- More real Gmail labeled messages for sync proof
- GitHub Actions verification
- Expanded Playwright coverage
- UI polish
