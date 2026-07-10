# Codex Phase 2 Review - Permanent Test Isolation

Reviewer: Codex independent read-only reviewer
Review date: 2026-07-09
Repository: `C:\Development\Workspace\aarohan-careeros`
Phase state reviewed: `PHASE_2_AWAITING_CODEX_REVIEW`

## Verdict

NO GO

Phase 2 proves meaningful physical isolation for the new local test stack, and the owner runtime blocks direct `pytest`. However, three High findings remain:

- The owner PostgreSQL role is still a superuser and can perform DDL.
- Database identity spoofing protection exists as helper code but is not enforced by app database initialization/startup.
- Destructive cleanup can proceed after a non-empty backup file even if `pg_dump` exits unsuccessfully or produces a partial dump.

Do not proceed to Phase 3 owner recovery/cutover until the High findings are corrected and revalidated.

## Scope and Commands

Read:

- `docs/recovery/owner-db-incident-20260709/02-CODEX-MASTER-REVIEWER.md`
- `docs/recovery/owner-db-incident-20260709/RECOVERY-ORCHESTRATION-STATE.md`
- Phase 2 evidence under `artifacts/recovery/incident-20260709/phase2-20260709_182613/`
- Changed compose, owner image, identity guard, test runner, audit, cleanup, and CI files

Independent checks performed:

- `git status --short --branch`
- `git diff` for Phase 2 implementation files
- Read-only Docker inspection for compose projects, services, networks, and volumes
- Read-only PostgreSQL catalog queries for roles, databases, ownership, and privileges
- Read-only negative connection checks using invalid cross-stack roles
- Owner runtime `pytest`/`python -m pytest` checks
- `python scripts/validation/owner_stack_pytest_scan.py`
- Review of Phase 2 test log

Not performed:

- No tests were run by Codex except the static owner-stack pytest scan.
- No restore was run by Codex.
- No database was written or mutated by Codex.
- No commit, staging, branch switch, cleanup, migration, or deployment was performed.

## Verified Phase 2 Controls

### Separate owner and E2E PostgreSQL services

Owner compose uses service `postgres`, database `career_os`, user `career_os`, and volume `postgres_data` (`docker-compose.yml:6`, `docker-compose.yml:8`, `docker-compose.yml:10`, `docker-compose.yml:136`).

Test compose uses project `aarohan-careeros-test`, service `postgres-e2e`, database `career_os_e2e`, user `career_os_e2e`, port `127.0.0.1:5433`, network `career_os_test`, and volume `postgres_e2e_data` (`docker-compose.test.yml:8`, `docker-compose.test.yml:11`, `docker-compose.test.yml:15`, `docker-compose.test.yml:17`, `docker-compose.test.yml:19`, `docker-compose.test.yml:21`, `docker-compose.test.yml:22`, `docker-compose.test.yml:87`, `docker-compose.test.yml:90`).

Live Docker inspection independently confirmed:

- `/aarohan-careeros-postgres-1|aarohan-careeros|postgres|aarohan-careeros_postgres_data:/var/lib/postgresql/data|aarohan-careeros_career_os`
- `/aarohan-careeros-test-postgres-e2e-1|aarohan-careeros-test|postgres-e2e|aarohan-careeros-test_postgres_e2e_data:/var/lib/postgresql/data|aarohan-careeros-test_career_os_test`

### Separate credentials and cross-stack connection rejection

Owner compose sets owner identity and owner DB URL (`docker-compose.yml:29`, `docker-compose.yml:30`, `docker-compose.yml:37`). Test compose sets E2E identity and E2E DB URL (`docker-compose.test.yml:35`, `docker-compose.test.yml:36`, `docker-compose.test.yml:41`).

Read-only role inventory showed:

- Owner postgres roles matching `career_os%`: `career_os`
- Test postgres roles matching `career_os%`: `career_os_e2e`

Negative connection checks failed as required:

- E2E role to owner postgres: `FATAL: role "career_os_e2e" does not exist`
- Owner role to test postgres: `FATAL: role "career_os" does not exist`

### Owner runtime cannot run pytest

The owner image replaces `/usr/local/bin/pytest` with a blocking script (`apps/api/Dockerfile.owner:22`, `apps/api/Dockerfile.owner:24`, `apps/api/Dockerfile.owner:25`) and the owner entrypoint also blocks `pytest`/`py.test` argv (`apps/api/entrypoint-owner.sh:4`, `apps/api/entrypoint-owner.sh:5`).

Independent owner-container check returned:

- `pytest --version`: blocked with `ERROR: pytest is blocked on the owner runtime image`
- `python -m pytest --version`: failed with `No module named pytest`

`requirements-owner.txt` does not include pytest.

### Audit dry-run is read-only

The Fresh Jobs audit sets PostgreSQL transaction read-only in non-execute mode (`apps/api/scripts/audit_fresh_jobs.py:117`, `apps/api/scripts/audit_fresh_jobs.py:122`) and only commits inside the execute branch (`apps/api/scripts/audit_fresh_jobs.py:258`, `apps/api/scripts/audit_fresh_jobs.py:297`).

### Isolated tests evidence

The canonical test runner documents and implements isolated execution: unit tests use SQLite (`scripts/local/Run-Aarohan-Tests.ps1:42`, `scripts/local/Run-Aarohan-Tests.ps1:43`), and Postgres integration tests use `127.0.0.1:5433/career_os_e2e` with E2E identity (`scripts/local/Run-Aarohan-Tests.ps1:58`, `scripts/local/Run-Aarohan-Tests.ps1:60`, `scripts/local/Run-Aarohan-Tests.ps1:61`, `scripts/local/Run-Aarohan-Tests.ps1:62`, `scripts/local/Run-Aarohan-Tests.ps1:64`, `scripts/local/Run-Aarohan-Tests.ps1:65`).

The Phase 2 log shows:

- Owner-stack pytest scan ran (`run-aarohan-tests.log:9`)
- Backend unit tests ran under SQLite (`run-aarohan-tests.log:15`)
- 215 unit tests passed, 8 skipped (`run-aarohan-tests.log:663`)
- Postgres integration tests ran against isolated `career_os_e2e` on `:5433` (`run-aarohan-tests.log:665`)
- 19 Postgres tests passed (`run-aarohan-tests.log:818`)
- The runner ended with `owner career_os not used` (`run-aarohan-tests.log:820`)

I also ran the owner-stack pytest scan independently; it passed.

## Findings

### CODEX-P2-HIGH-001

Severity: High

File and line: `docs/recovery/owner-db-incident-20260709/RECOVERY-ORCHESTRATION-STATE.md:114`; live PostgreSQL catalog

Evidence: The state file downgrades runtime/migrate role split to a Low future-hardening risk, but read-only catalog checks show the owner role is still a superuser with DDL privileges:

`owner_role_attrs|career_os|t|t|t|t|t`

`owner_privs|t|t|t`

This means role `career_os` has `rolsuper`, `rolcreatedb`, `rolcreaterole`, `rolreplication`, and `rolbypassrls`; it also has CREATE privilege on both database `career_os` and schema `public`.

Failure or exploit path: Any compromise, bug, migration path, or misrouted command running with the owner runtime DB credentials can create, alter, drop, or otherwise mutate schema and bypass row-level/data-level guard intent. This directly fails the Phase 2 requirement that the owner runtime DB role cannot perform DDL.

Required correction: Split owner DB access into at least two roles: a migration/admin role with DDL used only for controlled migrations, and an owner runtime role without superuser/createdb/createrole/replication/bypassrls and without schema/database CREATE privileges. Reassign runtime application ownership/privileges so normal API operations still work without DDL.

Validation required: Read-only catalog proof showing the owner runtime role has all dangerous role attributes false and cannot CREATE on database/schema, plus an app smoke validation using the non-DDL runtime role. Migration operations must use a separate explicit migration role.

### CODEX-P2-HIGH-002

Severity: High

File and line: `apps/api/app/database.py:6`, `apps/api/app/services/database_identity.py:96`

Evidence: The database identity guard is implemented in `assert_connection_matches_identity()` (`apps/api/app/services/database_identity.py:96`) but app database initialization directly creates the SQLAlchemy engine from `settings.database_url` without calling the guard (`apps/api/app/database.py:6`). Repository search found no app runtime call to `assert_connection_matches_identity`, `assert_identity_configured`, or equivalent outside tests and test helpers.

Failure or exploit path: A misconfigured or spoofed `DATABASE_URL` can be used by the app runtime without the identity guard ever executing. The compose files currently set the expected URLs, but the requested Phase 2 property is that database identity spoofing cannot bypass protections. As implemented, the protection is not enforced in the app's actual connection path.

Required correction: Enforce identity validation before creating the engine or during application startup, and fail closed when the declared purpose/UUID does not match the database URL and expected stack. The validation must cover owner, E2E, CI, and recovery identities.

Validation required: Tests and an actual app/container startup proof showing mismatched owner/E2E purpose, host, user, database, or UUID prevents startup before any DB operation.

### CODEX-P2-HIGH-003

Severity: High

File and line: `scripts/local/Cleanup-Owner-TestData.ps1:92`, `scripts/local/Cleanup-Owner-TestData.ps1:93`, `scripts/local/Cleanup-Owner-TestData.ps1:136`

Evidence: Execute mode writes the backup through a pipeline:

`docker compose exec -T postgres pg_dump -U career_os career_os | Set-Content -Path $backupFile -Encoding utf8`

The next gate only verifies the backup file exists and has length greater than zero. It does not check the `pg_dump` process exit code, does not use `--file`/atomic write semantics, does not verify that the dump is complete/restorable, and does not block partial non-empty dumps. The destructive SQL is later executed at line 136.

Failure or exploit path: If `pg_dump` exits nonzero after writing partial output, or if the pipeline produces any non-empty invalid dump, the script can compute a SHA and proceed to destructive owner cleanup. This fails the Phase 2 requirement that backup failure blocks destructive operations.

Required correction: Capture `pg_dump` exit status explicitly, fail on any nonzero exit, write to a temp file then atomically rename, verify expected dump structure/trailer, and ideally perform a disposable restore or `pg_restore`/SQL parse validation before allowing destructive SQL.

Validation required: Negative test/evidence where a forced backup failure blocks before any destructive SQL, plus positive evidence where a verified same-run backup permits the next confirmation gate.

### CODEX-P2-MEDIUM-001

Severity: Medium

File and line: `apps/api/app/services/database_identity.py:104`, `apps/api/app/services/database_identity.py:109`, `apps/api/app/services/database_identity.py:113`, `apps/api/app/services/database_identity.py:122`

Evidence: The identity guard compares URL database, username, and limited host cases. It does not bind `AAROHAN_DB_IDENTITY_UUID` to any value stored in the database itself, and it only rejects selected host/port combinations.

Failure or exploit path: Even after wiring the guard into startup, a database or environment that reuses accepted database/user names could satisfy the string checks without proving it is the intended owner or E2E database identity.

Required correction: Store an immutable database identity marker in each DB, compare it to `AAROHAN_DB_IDENTITY_UUID` at startup, and fail closed on mismatch. Keep URL user/database/host checks as a secondary guard.

Validation required: Tests and live proof that an otherwise plausible DB URL with the wrong stored identity UUID is rejected.

### CODEX-P2-MEDIUM-002

Severity: Medium

File and line: `.github/workflows/ci.yml:113`, `.github/workflows/ci.yml:136`, `.github/workflows/ci.yml:145`, `.github/workflows/ci.yml:150`

Evidence: The CI Playwright fixture job uses an ephemeral GitHub Actions Postgres service, not owner infrastructure, but it does not set the new `AAROHAN_DB_IDENTITY_PURPOSE`, `AAROHAN_DB_IDENTITY_UUID`, or `AAROHAN_RUNTIME_PROFILE` variables when starting the API and seeding the E2E user. The API-test job does set CI identity (`.github/workflows/ci.yml:38`, `.github/workflows/ci.yml:39`, `.github/workflows/ci.yml:41`).

Failure or exploit path: Once startup identity validation is wired, the CI Playwright API path may continue unvalidated or start failing depending on how the guard is implemented. It also leaves incomplete evidence for "all tests ran only on isolated infrastructure" across all test jobs.

Required correction: Add explicit CI identity variables to the Playwright fixture API and seed steps, or move that job to the same isolated test-stack identity model.

Validation required: CI log proof that API tests and Playwright fixture tests run with `AAROHAN_DB_IDENTITY_PURPOSE=CI` or E2E-equivalent isolated identity, never owner identity.

## Non-blocking Notes

- `docker-compose.e2e.yml` is deprecated and now contains `services: {}` (`docker-compose.e2e.yml:1`, `docker-compose.e2e.yml:3`, `docker-compose.e2e.yml:10`), which removes the previous shared-owner-postgres E2E path.
- The legacy `career_os_e2e` database still exists inside owner postgres, as the state file says (`RECOVERY-ORCHESTRATION-STATE.md:113`). This is acceptable only because the new test stack uses a separate Postgres service and it remains excluded from Phase 3 recovery classification.

## Phase 2 Gate Conclusion

NO GO.

Phase 2 may be re-submitted after correcting the High findings and regenerating evidence. The re-review should include read-only catalog proof for the owner runtime role, startup-failure proof for spoofed DB identities, and forced backup-failure proof for destructive cleanup.
