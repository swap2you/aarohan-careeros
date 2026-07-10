# Codex Phase 2 Re-review - Permanent Test Isolation

Reviewer: Codex independent read-only reviewer
Review date: 2026-07-10
Repository: `C:\Development\Workspace\aarohan-careeros`
Phase state reviewed: `PHASE_2_AWAITING_CODEX_REVIEW`
Rework evidence: `artifacts/recovery/incident-20260709/phase2-rework-20260709_225953/`
Current HEAD reviewed: `8d6007abd9c820e23172e8782899ea2932f75101`

## Verdict

NO GO

Most Phase 2 remediation is now reproducible: owner/E2E services are physically separate, runtime/migration roles are split, runtime roles lack DDL privileges, DB identity is stored in an immutable marker table, API startup validates URL plus marker, backup creation now performs checksum and restore verification, CI is green at current HEAD, and owner/validation business row counts remain unchanged.

One High finding remains: destructive owner helpers still do not validate the owner DB identity purpose/UUID/marker before using bootstrap access for the protected cleanup path. That leaves a bypass of the requested "destructive helpers enforce purpose + UUID" control.

## Scope and Checks

Read:

- `docs/recovery/owner-db-incident-20260709/RECOVERY-ORCHESTRATION-STATE.md`
- `docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-2-REVIEW.md`
- `docs/recovery/owner-db-incident-20260709/DATABASE-IDENTITY-PROVISIONING.md`
- newest Phase 2 rework evidence under `artifacts/recovery/incident-20260709/phase2-rework-20260709_225953/`
- committed diff from `75f64285a7110d8f7811fa85db1eea1e7f9a511b..HEAD`

Independent checks performed:

- `git status --short --branch` and `git diff --stat 75f64285a7110d8f7811fa85db1eea1e7f9a511b..HEAD`
- read-only Docker inspection for owner/test compose project, service, network, and volume separation
- read-only PostgreSQL catalog queries for roles, privileges, marker row, trigger, schema ownership, and row counts
- read-only cross-stack invalid-role connection probes
- owner container env/pytest block check
- GitHub Actions check via `gh run list` and `gh run view`

Not performed:

- No owner tests were run.
- No restore was run by Codex.
- No database was written or mutated by Codex.
- No commit, staging, branch switch, cleanup, migration, or deployment was performed.

## Prior Finding Disposition

### CODEX-P2-HIGH-001 - Resolved

Owner runtime DB role is no longer the bootstrap superuser. Live catalog evidence:

- `career_os_runtime`: `rolsuper=f`, `rolcreatedb=f`, `rolcreaterole=f`, `rolreplication=f`, `rolbypassrls=f`
- `career_os_migrate`: `rolsuper=f`, `rolcreatedb=f`, `rolcreaterole=f`, `rolreplication=f`, `rolbypassrls=f`
- runtime CREATE privileges: database `career_os` = false, schema `public` = false, schema `aarohan_meta` = false
- migrate CREATE privileges: database `career_os` = true, schema `public` = true, schema `aarohan_meta` = true

Provisioning creates/updates roles with `NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS` (`apps/api/scripts/provision_database_roles.py:63`, `apps/api/scripts/provision_database_roles.py:70`), grants runtime DML but revokes schema CREATE (`apps/api/scripts/provision_database_roles.py:88`, `apps/api/scripts/provision_database_roles.py:94`), and grants migrate CREATE (`apps/api/scripts/provision_database_roles.py:151`).

### CODEX-P2-HIGH-002 - Resolved for API/runtime/migrations/tests

API DB initialization now validates both URL identity and the DB-side marker before returning the engine (`apps/api/app/database.py:21`, `apps/api/app/database.py:28`, `apps/api/app/database.py:31`). Startup lifespan calls `get_engine()` before serving (`apps/api/app/main.py:53`, `apps/api/app/main.py:56`). Alembic invokes pre-migration validation when marker state exists (`apps/api/alembic/env.py:26`, `apps/api/alembic/env.py:35`).

The identity guard rejects mismatched purpose/database/user/host and validates marker UUID (`apps/api/app/services/database_identity.py:131`, `apps/api/app/services/database_identity.py:211`, `apps/api/app/services/database_identity.py:240`, `apps/api/app/services/database_identity.py:245`).

### CODEX-P2-HIGH-003 - Partially Resolved

Backup generation now checks `pg_dump` exit code (`scripts/local/Invoke-VerifiedOwnerBackup.ps1:62`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:63`), copies the dump with exit-code checks (`scripts/local/Invoke-VerifiedOwnerBackup.ps1:66`), checks file presence/header/checksum, restores into a disposable DB, and compares table count plus critical row counts (`scripts/local/Invoke-VerifiedOwnerBackup.ps1:80`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:85`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:86`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:92`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:96`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:103`).

Evidence manifest confirms a verified backup: `verified=true`, size `2268287`, SHA-256 `bcd92e43a40b20d49861ff010aa979de1fa208ba0a6cccac91a32349d7114a9c`, and 63/63 restored tables (`BACKUP-GATE-EVIDENCE.json`).

Remaining issue is tracked as `CODEX-P2-HIGH-004`: destructive helpers still lack identity marker validation.

### CODEX-P2-MEDIUM-001 - Resolved

Migration `0013_database_identity_meta` creates `aarohan_meta.database_identity`, a UUID uniqueness constraint, and an immutable trigger blocking UPDATE/DELETE and multiple rows (`apps/api/alembic/versions/0013_database_identity_meta.py:17`, `apps/api/alembic/versions/0013_database_identity_meta.py:28`, `apps/api/alembic/versions/0013_database_identity_meta.py:36`, `apps/api/alembic/versions/0013_database_identity_meta.py:37`, `apps/api/alembic/versions/0013_database_identity_meta.py:40`, `apps/api/alembic/versions/0013_database_identity_meta.py:41`, `apps/api/alembic/versions/0013_database_identity_meta.py:51`, `apps/api/alembic/versions/0013_database_identity_meta.py:52`).

Live owner marker evidence:

- `marker|OWNER|2bfda5fc-3a2b-4dd4-a7a9-65e8432f7c03|0013|1`
- trigger `trg_database_identity_immutable` enabled
- `aarohan_meta` and `public` owned by `career_os_migrate`

Live E2E marker evidence:

- `marker|E2E|11b68036-f0fc-47c3-9ab6-59701d72e10b|0013|1`

### CODEX-P2-MEDIUM-002 - Resolved

CI now provisions and validates a per-run CI identity marker before tests and Playwright. API tests set CI purpose/UUID and runtime/migration URLs (`.github/workflows/ci.yml:43`, `.github/workflows/ci.yml:50`, `.github/workflows/ci.yml:51`, `.github/workflows/ci.yml:55`, `.github/workflows/ci.yml:68`, `.github/workflows/ci.yml:69`, `.github/workflows/ci.yml:72`, `.github/workflows/ci.yml:75`, `.github/workflows/ci.yml:76`, `.github/workflows/ci.yml:80`, `.github/workflows/ci.yml:81`).

Playwright fixture also provisions CI identity and asserts it is not OWNER (`.github/workflows/ci.yml:149`, `.github/workflows/ci.yml:156`, `.github/workflows/ci.yml:157`, `.github/workflows/ci.yml:161`, `.github/workflows/ci.yml:172`, `.github/workflows/ci.yml:177`, `.github/workflows/ci.yml:178`, `.github/workflows/ci.yml:189`, `.github/workflows/ci.yml:190`, `.github/workflows/ci.yml:191`, `.github/workflows/ci.yml:192`, `.github/workflows/ci.yml:197`, `.github/workflows/ci.yml:216`, `.github/workflows/ci.yml:217`, `.github/workflows/ci.yml:218`, `.github/workflows/ci.yml:222`).

GitHub Actions current HEAD `8d6007abd9c820e23172e8782899ea2932f75101` has successful CI run `29067219900`; jobs `api-tests`, `validation-scans`, `web-build`, and `playwright-fixture` all completed successfully.

## Additional Verification

### Separate services, projects, networks, volumes

Live Docker inspection confirmed:

- owner: `/aarohan-careeros-postgres-1|aarohan-careeros|postgres|aarohan-careeros_postgres_data:/var/lib/postgresql/data|aarohan-careeros_career_os`
- E2E: `/aarohan-careeros-test-postgres-e2e-1|aarohan-careeros-test|postgres-e2e|aarohan-careeros-test_postgres_e2e_data:/var/lib/postgresql/data|aarohan-careeros-test_career_os_test`

Compose files match that separation (`docker-compose.yml:30`, `docker-compose.yml:31`, `docker-compose.yml:39`, `docker-compose.yml:40`; `docker-compose.test.yml:11`, `docker-compose.test.yml:21`, `docker-compose.test.yml:36`, `docker-compose.test.yml:37`, `docker-compose.test.yml:43`, `docker-compose.test.yml:44`, `docker-compose.test.yml:47`).

Cross-stack invalid-role probes failed as required:

- owner Postgres rejected `career_os_e2e_runtime`: role does not exist
- E2E Postgres rejected `career_os_runtime`: role does not exist

### No owner tests and unchanged data

The canonical local runner uses SQLite for unit tests and `127.0.0.1:5433/career_os_e2e` for Postgres integration tests (`scripts/local/Run-Aarohan-Tests.ps1:8`, `scripts/local/Run-Aarohan-Tests.ps1:9`, `scripts/local/Run-Aarohan-Tests.ps1:12`, `scripts/local/Run-Aarohan-Tests.ps1:42`, `scripts/local/Run-Aarohan-Tests.ps1:43`, `scripts/local/Run-Aarohan-Tests.ps1:60`, `scripts/local/Run-Aarohan-Tests.ps1:61`, `scripts/local/Run-Aarohan-Tests.ps1:62`, `scripts/local/Run-Aarohan-Tests.ps1:68`, `scripts/local/Run-Aarohan-Tests.ps1:69`).

Rework evidence reports 224 SQLite unit tests and 41 isolated Postgres integration tests, with owner cleanup not executed and `career_os_validation` not modified (`ISOLATED-TEST-EVIDENCE.json`).

Live read-only row counts match the state file:

| Database | jobs | applications | oauth_tokens | processed_gmail_messages | users |
|---|---:|---:|---:|---:|---:|
| `career_os` | 75 | 2 | 0 | 0 | 2 |
| `career_os_validation` | 124 | 3 | 9 | 59 | 2 |

## Findings

### CODEX-P2-HIGH-004

Severity: High

File and line: `scripts/local/Cleanup-Owner-TestData.ps1:89`, `scripts/local/Cleanup-Owner-TestData.ps1:104`, `scripts/local/Cleanup-Owner-TestData.ps1:134`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:9`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:18`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:33`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:39`, `scripts/local/Invoke-VerifiedOwnerBackup.ps1:57`

Evidence: The destructive cleanup path calls `Invoke-VerifiedOwnerBackup.ps1` and then executes destructive SQL using direct bootstrap DB access. It imports `.env.local` and validates `AAROHAN_DESTRUCTIVE_TOKEN`, but it never validates `AAROHAN_DB_IDENTITY_PURPOSE`, `AAROHAN_DB_IDENTITY_UUID`, or the `aarohan_meta.database_identity` marker before the protected operation. `Invoke-VerifiedOwnerBackup.ps1` defaults to bootstrap user `career_os`, reads source counts via bootstrap access, runs `pg_dump` via bootstrap access, and creates/drops verification databases via bootstrap access, but also does not validate the marker/purpose/UUID first.

Failure or exploit path: If the owner compose context, environment, or restored database marker is wrong, the destructive helper can still produce a verified backup and proceed to destructive cleanup as long as the token is entered. That bypasses the explicit Phase 2 requirement that destructive helpers enforce purpose + UUID and weakens the database identity guard exactly where high-risk owner operations occur.

Required correction: Before backup and before destructive SQL, the helper must read `aarohan_meta.database_identity` from the target DB and require `purpose='OWNER'` plus equality to `AAROHAN_OWNER_DB_IDENTITY_UUID` or `AAROHAN_DB_IDENTITY_UUID`. It should fail closed if the marker table is missing, has zero/multiple rows, has a mismatched UUID/purpose, or if the env identity is absent. Prefer sharing the same validation logic used by `app.services.database_identity`, or an equivalent PowerShell/psql check, and record the verified marker in the backup/cleanup manifest.

Validation required: Rework evidence must include a positive owner-marker validation before backup/cleanup and negative proofs showing mismatched purpose, mismatched UUID, missing marker, or wrong target database block before backup and before any destructive SQL.

## Gate Conclusion

NO GO.

The remaining High finding is narrow but data-safety relevant. After adding identity-marker enforcement to the destructive owner helpers and regenerating evidence with negative proofs, this phase should be eligible for a focused re-review.
