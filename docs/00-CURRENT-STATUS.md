# Aarohan CareerOS — Current Status

Last updated: 2026-06-29  
Branch: `main`  
Latest RC tag: `r2.13.0-rc1` (`edb540d`)  
Program: **R2 IN_VALIDATION** — feature freeze; validation and UAT phase

## Product state

Local-first CareerOS RC is code-complete through R2.13:

- Docker stack: postgres, api, web, n8n
- Auth: HttpOnly session cookies, Remember Me, logout revocation
- Google OAuth: live mode when `OAUTH_FIXTURE_MODE=false` (owner Settings)
- Job connectors, trust/fit, duplicate protection, packets, assisted apply
- Gmail lifecycle (fixture + classification)
- Interview intelligence, Ask Aarohan, TTS
- Modern UI design tokens

## Validation status

| Area | Status |
|------|--------|
| Automated gate | 112 API + 19 Playwright (local); 8 Postgres in Docker |
| R2.5 Drive | **CONDITIONAL_GO** — live upload pending |
| R2.7 Gmail | **CONDITIONAL_GO** — live per-source pending |
| R2.13 RC | **IN_VALIDATION** — reviews done; owner UAT pending |
| Final `r2.13.0` tag | **Not created** — criteria not met |

## Commands

```powershell
scripts/local/Start-Aarohan.ps1
scripts/validation/Verify-Full-R2.ps1
scripts/validation/Live-RC-Validation.ps1   # after Start-Aarohan
scripts/local/Stop-Aarohan.ps1
```

## Canonical docs

- Program board: `docs/Program/R2-PROGRAM-BOARD.md`
- Defects: `docs/validation/FINAL-DEFECT-REGISTER.md`
- UAT results: `docs/validation/uat/UAT-RESULTS.md`
