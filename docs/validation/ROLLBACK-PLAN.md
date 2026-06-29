# Rollback plan (R2.13 RC)

## Application rollback

```powershell
git fetch origin --tags
git checkout r2.6.1   # or any prior immutable tag
docker compose build api web
docker compose up -d
```

## Database rollback

- Prefer restore from backup: `scripts/local/Restore-Aarohan.ps1`
- Do **not** downgrade Alembic across major R2 releases without restore — forward-only in production usage

## Tag policy

Release tags `r2.x.x` are immutable. Corrections require patch tags (e.g. r2.6.2), never force-push tags.

## Data preservation

Rollback commands must not use `docker compose down -v` unless intentionally wiping local Postgres.
