# Second Review Handoff — Post Main Sync

Date: 2026-06-27

## Repository

- Remote: https://github.com/swap2you/aarohan-careeros.git
- Branch: `main`
- Initial commit: `e8eedaf` — "R1 complete local CareerOS baseline"
- Local HEAD equals `origin/main`

## Independent second-review command

```text
Read validation/SECOND_REVIEW_HANDOFF.md, validation/R1_REPOSITORY_AUDIT.md, validation/CURSOR_FIRST_REVIEW.md, and validation/CURSOR_TEST_EVIDENCE.md. Clone main, re-run tests independently. Return PASS or STOP. Do not deploy.
```

## Cowork UAT command

```text
Read validation/COWORK_UAT_PROMPT.md and execute all 14 user-journey scenarios against a running local stack. Record evidence under artifacts/uat/. Do not deploy or push.
```

## User actions to complete local proof

1. Install Docker Desktop (admin UAC): `choco install docker-desktop -y` or winget
2. Install GitHub CLI: `choco install gh -y` then `gh auth login`
3. `pwsh scripts/local/Bootstrap-Aarohan.ps1`
4. `pwsh scripts/local/Start-Aarohan.ps1 -Detached`
5. Connect Google at http://localhost:3000/settings as `swapnilpatil.tech@gmail.com`
6. `pwsh scripts/local/Test-Aarohan.ps1` and `cd apps/web; npm run test:e2e`
7. Verify CI: `gh run watch --repo swap2you/aarohan-careeros --exit-status`

## Excluded from Git (intentional)

- `docs/Swapnil/` — private personal documents
- `Aarohan - Keys & secrets.txt`
- `C:\AarohanSecrets\google-oauth-client.json`
- `.env.local`, generated output, artifacts
