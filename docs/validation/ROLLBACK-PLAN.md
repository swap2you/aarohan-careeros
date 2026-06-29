# Rollback plan (R2.13 RC)

## Safe rollback on `main` (preferred)

Do **not** use detached HEAD as the primary rollback procedure for owners.

```powershell
git switch main
git pull --ff-only
git revert --no-commit r2.6.1..r2.13.0-rc1
git commit -m "Revert Aarohan R2 release candidate"
git push origin main
```

Rebuild and restart:

```powershell
docker compose build api web
docker compose up -d
```

## Inspection only (read-only)

```powershell
git switch --detach r2.6.1
```

Use for diff inspection only — not for daily operation.

## Database rollback

- **Always backup first:** `scripts/local/Backup-Aarohan.ps1`
- Alembic downgrade across R2 releases is **not** automated for owner rollback
- Restore from backup: `scripts/local/Restore-Aarohan.ps1`
- Requires explicit owner approval before any destructive DB operation

If API fails after image rebuild with `relation already exists`:

```powershell
docker compose run --rm api alembic stamp head
docker compose up -d api
```

## Tag policy

Tags `r2.x.x` and `r2.13.0-rc*` are immutable. Corrections use new patch/rc tags only.

## Data preservation

Never use `docker compose down -v` unless intentionally wiping local Postgres.
