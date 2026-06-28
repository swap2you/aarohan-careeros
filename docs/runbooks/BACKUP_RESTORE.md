# Backup and Restore

PostgreSQL backup for local Docker stack. Scripts live in `scripts/local/`.

## Prerequisites

- Stack running (`Start-Aarohan.ps1 -Detached`)
- `POSTGRES_PASSWORD` in PowerShell SecretStore
- Docker CLI available

Backups capture the `career_os` database only (jobs, applications, OAuth tokens, audit, etc.). They do **not** include:

- Docker volumes for n8n (`n8n_data`)
- Generated docs volume (`generated_docs`)
- Google Drive files
- SecretStore vault
- `career_vault/` source files (already in Git)

## Backup

```powershell
pwsh .\scripts\local\Backup-Aarohan.ps1
```

Default output: `artifacts\backups\career_os_YYYYMMDD_HHmmss.sql`

Custom directory:

```powershell
pwsh .\scripts\local\Backup-Aarohan.ps1 -OutputDir D:\Backups\Aarohan
```

**What it does:** Runs `pg_dump` via `docker compose exec -T postgres` against database `career_os` as user `career_os`. Password comes from SecretStore (falls back to `$env:POSTGRES_PASSWORD`).

**Verify:**

```powershell
Get-Item artifacts\backups\*.sql | Sort-Object LastWriteTime -Descending | Select-Object -First 1
```

File should be non-zero size and contain SQL `CREATE TABLE` statements.

## Restore

**Warning:** Restore overwrites current database contents.

```powershell
pwsh .\scripts\local\Restore-Aarohan.ps1 -BackupFile artifacts\backups\career_os_20260627_120000.sql
```

Prompts: type `RESTORE` to confirm.

**What it does:** Pipes SQL file into `psql` via `docker compose exec -T postgres` against `career_os`.

**After restore:**

1. Restart API if connections were stale: `Stop-Aarohan.ps1` then `Start-Aarohan.ps1 -Detached`.
2. Verify: http://localhost:8000/ready and sign in to dashboard.
3. Re-test OAuth if tokens were invalidated (unlikely from SQL restore alone).

## Recommended schedule (local)

| When | Action |
|------|--------|
| Before `Reset-Aarohan.ps1 -Volumes` | Backup |
| Before schema-changing Alembic upgrades | Backup |
| Weekly during active development | Backup to external drive |
| After major UAT data entry | Backup |

Automated cron backups are disabled in local-first mode. Enable only on future VPS deployment.

## Restore drill (release gate)

Per `docs/09_RELEASE_GATES.md`, a tested restore is required before release:

1. Backup production-like local data.
2. Run restore to a fresh volume or after reset.
3. Confirm job count, recent audit entries, and login still work.
4. Document evidence in `validation/`.

## Troubleshooting

| Issue | Fix |
|-------|-----|
| Empty backup file | Ensure postgres container is running; check `docker compose ps` |
| POSTGRES_PASSWORD not available | Run `Initialize-AarohanSecrets.ps1` |
| Restore cancelled | Re-run and type exactly `RESTORE` |
| Permission denied on output dir | Create `artifacts\backups` manually or use `-OutputDir` |
| OAuth broken after restore | Disconnect/reconnect Google in Settings |

## Security

- Backup files contain encrypted OAuth tokens and user data — store outside Git.
- Add `artifacts/backups/` to personal backup rotation; do not commit `.sql` files.
- Encrypt backup directory on shared machines.
