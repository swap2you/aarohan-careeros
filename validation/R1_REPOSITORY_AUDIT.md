# R1 Repository Audit

Date: 2026-06-27

## Root classification

| Path | Action | Reason |
|------|--------|--------|
| `apps/` | KEEP | Application code |
| `career_vault/` | KEEP | Approved evidence |
| `config/` | KEEP | Runtime configuration |
| `docs/` | KEEP | Canonical documentation |
| `n8n/` | KEEP | Workflow definitions |
| `scripts/` | KEEP | Local ops and validation |
| `validation/` | KEEP | Review artifacts |
| `.cursor/` | KEEP | Agent rules |
| `.github/` | KEEP | CI workflows |
| `AGENTS.md` | KEEP | Agent policy |
| `README.md` | KEEP | Entry point |
| `.env.example` | KEEP | Non-secret template |
| `.gitignore` | KEEP | Secret exclusion |
| `docker-compose.yml` | KEEP | Local stack |
| `manifest.json` | ARCHIVE | Pack metadata → merged into docs/releases |
| `PROJECT_CHARTER.md` | KEEP | Product charter |
| `START_HERE.md` | KEEP | Onboarding pointer |
| `Aarohan - Keys & secrets.txt` | LOCAL_ONLY | Credentials — never commit |
| `Aarohan_*.zip` | LOCAL_ONLY | Pack archives — gitignored |
| `AarohanSecrets/` | SECRET_RISK | OAuth JSON — outside repo |
| `.env.local` | LOCAL_ONLY | Non-secret local config — gitignored |
| `.local/` | GENERATED | Runtime scratch |
| `artifacts/` | GENERATED | Backups, Playwright — gitignored |
| `generated/` | GENERATED | Document output — gitignored |
| `aarohan_finalize_main_sync_pack/` | ARCHIVE | Moved to docs/archive/ai-prompts |
| `Aarohan_R1_Local_Execution_Pack_v2/` | ARCHIVE | Moved to docs/archive/execution-packs |
| `docs/archive/` | KEEP | Historical prompts and packs |

## Secret scan posture

- OAuth JSON: `C:\AarohanSecrets\google-oauth-client.json` (LOCAL_ONLY)
- PowerShell SecretStore for runtime secrets
- `.gitignore` blocks keys files, zips, env locals, secrets dirs

## Canonical root after cleanup

```text
apps/
career_vault/
config/
docs/
n8n/
scripts/
validation/
.cursor/
.github/
AGENTS.md
README.md
PROJECT_CHARTER.md
START_HERE.md
.env.example
.gitignore
docker-compose.yml
```
