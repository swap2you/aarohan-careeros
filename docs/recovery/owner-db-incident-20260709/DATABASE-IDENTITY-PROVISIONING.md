# Database identity provisioning

## Immutable marker

Migration `0013_database_identity_meta` creates:

- schema: `aarohan_meta`
- table: `aarohan_meta.database_identity`
- trigger: blocks UPDATE/DELETE and enforces a single row

The marker stores:

- `purpose` — `OWNER`, `E2E`, `CI`, or `RECOVERY`
- `identity_uuid` — immutable UUID v4 bound to the environment
- `schema_version` — provisioning metadata
- `created_at` — provisioning timestamp

## Roles

| Stack | Bootstrap (provisioning only) | Migrate | Runtime |
|---|---|---|---|
| Owner | `career_os` | `career_os_migrate` | `career_os_runtime` |
| E2E/CI test | `career_os_e2e` / `career_os` | `*_migrate` | `*_runtime` |

Runtime roles are `NOSUPERUSER`, have no DDL privileges, and cannot modify `aarohan_meta.database_identity`.

## One-time owner provisioning

```powershell
pwsh scripts/local/Sync-EnvLocal.ps1 -GenerateMissing
pwsh scripts/local/Invoke-ProvisionOwnerDatabase.ps1 -RunMigrations
docker compose --env-file .env.local up -d --build api
```

Required `.env.local` keys:

- `AAROHAN_OWNER_DB_IDENTITY_UUID`
- `POSTGRES_MIGRATE_PASSWORD`
- `POSTGRES_RUNTIME_PASSWORD`

## E2E / local test provisioning

```powershell
pwsh scripts/local/Invoke-ProvisionE2EDatabase.ps1 -RunMigrations
pwsh scripts/local/Start-Aarohan-E2E.ps1
```

## Recovery note

If the owner database is restored from backup, re-run provisioning only when:

1. migration `0013` is present, and
2. the marker row is missing or must be re-bound to a new recovery UUID.

Never overwrite an existing marker with a different UUID. Recovery cutover uses a dedicated `RECOVERY` purpose in later phases.
