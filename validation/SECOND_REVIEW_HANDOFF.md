# Second Review Handoff — R1 Local Checkpoint

Date: 2026-06-28

## Repository

- Remote: https://github.com/swap2you/aarohan-careeros.git
- Branch: `main`
- Checkpoint: R1 local Google Drive validation documented and committed

## Local login (for reviewers)

| Item | Value |
|------|-------|
| URL | http://localhost:3000 |
| Settings | http://localhost:3000/settings |
| Email | `swapnilpatil.tech@gmail.com` |
| Password | `TempLocal123!` (local only) |
| Reset | `powershell -File scripts/local/Reset-LocalAdmin.ps1 -Force` |

## Validation status

See `validation/CURSOR_TEST_EVIDENCE.md`.

**Local checkpoint: COMPLETE** — OAuth, Drive app-root, packet upload, pytest, scans.

**Still open:**

1. GitHub Actions `gh run watch` after push
2. Cowork UAT (14 journeys)
3. Expanded Playwright / Gmail labeled-message corpus

## Independent second-review command

```text
Read validation/SECOND_REVIEW_HANDOFF.md, validation/CURSOR_TEST_EVIDENCE.md, and docs/releases/R1_LOCAL_COMPLETE.md. Clone main, re-run pytest and scans independently. Return PASS or STOP. Do not deploy.
```

## Cowork UAT command

```text
Read validation/COWORK_UAT_PROMPT.md and execute all 14 user-journey scenarios against a running local stack. Record evidence under artifacts/uat/. Do not deploy or push.
```

## Operator quick reference

```powershell
docker compose ps
docker compose up -d
powershell -File scripts/local/Start-Aarohan.ps1 -Detached
powershell -File scripts/local/Test-Aarohan.ps1
```

Services: API http://localhost:8000/health · Web http://localhost:3000 · n8n http://localhost:5678

Drive active root (proven): `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr`

## Known gaps

- Document quality needs improvement
- ATS templates need validation
- Real Gmail content still needs more test data
- GitHub Actions needs verification
- Playwright coverage needs expansion
- Backup/restore n8n schema noise
- UI polish pending

## Excluded from Git

- `docs/Swapnil/`, `C:\AarohanSecrets\`, `.env.local`, `artifacts/`, generated output
