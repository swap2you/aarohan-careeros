# Codex Phase 2 Final Re-review - Permanent Test Isolation

Reviewer: Codex independent read-only reviewer
Review date: 2026-07-10
Repository: `C:\Development\Workspace\aarohan-careeros`
Phase state reviewed: `PHASE_2_AWAITING_CODEX_REVIEW`
Final identity evidence: `artifacts/recovery/incident-20260709/phase2-final-identity-20260710_150438/`
Current HEAD reviewed: `f8b79a70cf1c89ed5b2df48b1a49f9efa0c69740`

## Verdict

GO

Phase 2 permanent test isolation and owner protection are reproducible. The prior open High finding (`CODEX-P2-HIGH-004`) is resolved: privileged owner helpers now require a canonical owner identity preflight before bootstrap operations, verified backups bind the owner identity fingerprint, same-run backup manifests are validated before protected cleanup, and destructive SQL revalidates the owner marker inside the transaction.

No Critical or High findings remain.

## Scope and Checks

Read:

- `docs/recovery/owner-db-incident-20260709/RECOVERY-ORCHESTRATION-STATE.md`
- `docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-2-REREVIEW.md`
- final identity evidence under `artifacts/recovery/incident-20260709/phase2-final-identity-20260710_150438/`
- committed diff from `75f64285a7110d8f7811fa85db1eea1e7f9a511b..HEAD`

Independent checks performed:

- `git status --short --branch`
- `git diff --stat 75f64285a7110d8f7811fa85db1eea1e7f9a511b..HEAD`
- read-only PostgreSQL catalog queries for roles, privileges, identity marker, trigger, and row counts
- read-only Docker inspection for project/service/network/volume separation
- owner container pytest block check
- static privileged-owner-helper and owner-stack-pytest scans
- GitHub Actions status for current HEAD

Not performed:

- No owner tests were run.
- No restore was run by Codex.
- No database was written or mutated by Codex.
- No commit, staging, branch switch, cleanup, migration, or deployment was performed.

## Final Finding Disposition

### CODEX-P2-HIGH-001 - Resolved

Owner runtime DB role is not a superuser and cannot perform DDL. Live read-only catalog checks show:

- `career_os_runtime`: `rolsuper=f`, `rolcreatedb=f`, `rolcreaterole=f`, `rolreplication=f`, `rolbypassrls=f`
- runtime CREATE privileges: database `career_os` = false, schema `public` = false, schema `aarohan_meta` = false
- `career_os_migrate`: dangerous role attrs false, with CREATE privilege on database/schema for controlled migrations

The bootstrap `career_os` role still exists and is privileged, but the owner API runtime uses `career_os_runtime`; privileged helpers are now guarded before bootstrap use.

### CODEX-P2-HIGH-002 - Resolved

API startup and database creation enforce identity. `get_engine()` validates URL identity and the immutable marker before returning an engine. App startup calls `get_engine()` before serving. Alembic validates when the marker exists before migrations.

Spoofing coverage is now layered:

- URL checks reject wrong database, user, host, and purpose.
- DB-side marker checks require exactly one marker row with matching purpose/UUID.
- Owner privileged helpers also check database, compose project, service, container, host, and port before privileged access.

### CODEX-P2-HIGH-003 - Resolved

Backup gate now checks `pg_dump` exit code, dump presence, size, header, checksum, disposable restore, restored table count, and critical row counts.

Evidence confirms a verified owner backup with:

- `verified=true`
- `verification_result=restore_verified`
- 63/63 tables restored
- checksum recorded
- owner identity metadata bound into the manifest

Failed or corrupted backups are covered by unit tests for empty dump, missing header, checksum mismatch, restore inventory mismatch, row-count mismatch, corrupted manifest, wrong UUID, wrong database, and stale manifest.

### CODEX-P2-MEDIUM-001 - Resolved

Database identity is stored in `aarohan_meta.database_identity` with one-row immutability enforced by trigger. Live evidence:

- owner marker: `OWNER|2bfda5fc-3a2b-4dd4-a7a9-65e8432f7c03|0013|1`
- E2E marker: `E2E|11b68036-f0fc-47c3-9ab6-59701d72e10b|0013|1`
- trigger `trg_database_identity_immutable` is enabled

### CODEX-P2-MEDIUM-002 - Resolved

CI and Playwright now provision and validate CI identity. Latest GitHub Actions run for current HEAD `f8b79a70cf1c89ed5b2df48b1a49f9efa0c69740` is green:

- `api-tests`: success
- `validation-scans`: success
- `web-build`: success
- `playwright-fixture`: success

The CI run includes owner-stack pytest scan, privileged owner helper scan, CI marker assertion, pytest, and Playwright fixture execution under CI identity.

### CODEX-P2-HIGH-004 - Resolved

Privileged owner helpers now enforce purpose + UUID:

- `Assert-AarohanOwnerDatabaseIdentity.ps1` requires `AAROHAN_OWNER_DB_IDENTITY_UUID`, forces `AAROHAN_DB_IDENTITY_PURPOSE=OWNER`, rejects forbidden databases, rejects test compose/project/port/container, and calls `validate_owner_database_identity.py`.
- `owner_database_identity_preflight.py` validates target metadata, marker table existence, exactly one marker row, marker purpose, marker UUID, and current database.
- `Invoke-VerifiedOwnerBackup.ps1` runs the owner identity preflight before backup and writes identity purpose/UUID/fingerprint into the backup manifest.
- `Cleanup-Owner-TestData.ps1` runs the preflight at start, validates same-run backup manifest identity binding, and revalidates the marker inside the destructive transaction before any DELETE.
- `Audit-FreshJobsData.ps1`, `Backup-Aarohan.ps1`, `backup_postgres.py`, Phase 1 snapshot, and API audit execute path are covered by the same guard or equivalent identity revalidation.
- `python scripts/validation/privileged_owner_helper_scan.py` passed independently.

## Required Proofs

1. Owner runtime DB role is not a superuser and cannot perform DDL: **verified**.
2. Migration and runtime roles are separated: **verified**.
3. Database identity is a protected immutable DB-side marker: **verified**.
4. API startup, migrations, tests, and destructive helpers enforce purpose + UUID: **verified**.
5. DB-name, hostname, user, and password spoofing cannot bypass identity: **verified by code, tests, marker binding, and preflight checks**.
6. Backup gate verifies `pg_dump` exit code, integrity, checksum, and actual restore: **verified**.
7. Failed or corrupted backups block protected operations: **verified by tests and manifest gate**.
8. CI and Playwright provision and validate E2E/CI identity: **verified; CI green**.
9. Owner and E2E use separate services, projects, users, networks, and volumes: **verified**.
10. No tests ran against owner `career_os`: **verified by evidence and owner runtime pytest block**.
11. `career_os` and `career_os_validation` business data remained unchanged: **verified**.
12. Required source changes are committed and CI is green: **verified**.

## Live Read-only Evidence

Docker separation:

- owner: `/aarohan-careeros-postgres-1|aarohan-careeros|postgres|aarohan-careeros_postgres_data:/var/lib/postgresql/data|aarohan-careeros_career_os`
- E2E: `/aarohan-careeros-test-postgres-e2e-1|aarohan-careeros-test|postgres-e2e|aarohan-careeros-test_postgres_e2e_data:/var/lib/postgresql/data|aarohan-careeros-test_career_os_test`

Owner row counts:

| Table | Count |
|---|---:|
| jobs | 75 |
| applications | 2 |
| oauth_tokens | 0 |
| processed_gmail_messages | 0 |
| users | 2 |

Validation row counts:

| Table | Count |
|---|---:|
| jobs | 124 |
| applications | 3 |
| oauth_tokens | 9 |
| processed_gmail_messages | 59 |
| users | 2 |

Owner runtime pytest block:

- `pytest --version`: blocked with owner runtime error
- `python -m pytest --version`: failed because pytest module is absent

## Phase 2 Gate Conclusion

GO.

Phase 2 permanent test isolation and owner protection are reproducible. Phase 3 may proceed under the documented recovery process; no owner cutover or destructive owner operation should run without the same identity and backup gates.
