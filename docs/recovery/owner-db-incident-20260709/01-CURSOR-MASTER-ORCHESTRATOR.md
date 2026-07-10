# Cursor Master Orchestrator — Owner DB Recovery

You are the primary implementation and execution agent for Aarohan CareerOS.

Repository:

`C:\Development\Workspace\aarohan-careeros`

Orchestration documents:

`docs/recovery/owner-db-incident-20260709/`

## Operating mode

You are the only agent allowed to modify code, scripts, Compose files, migrations,
documentation, or local databases during this recovery.

Codex is an independent reviewer and must not edit concurrently.

Do not execute all phases in one uncontrolled run. Execute phase-by-phase using the
state file and mandatory gates below.

## First action

Read all files under:

`docs/recovery/owner-db-incident-20260709/`

Then create or update:

`docs/recovery/owner-db-incident-20260709/RECOVERY-ORCHESTRATION-STATE.md`

Use the template in `04-RECOVERY-STATE-TEMPLATE.md`.

## Global rules

- Do not change the approved UI/UX/CSS.
- Do not create RC4.
- Do not begin Workflow Lock 02.
- Do not run tests against `career_os`.
- Do not modify `career_os_validation`.
- Do not use the two PG-test rows as owner data.
- Do not run audit `-Execute`.
- Do not delete Docker volumes.
- Do not expose secrets.
- Make the smallest safe changes.
- Validate every change with actual commands and generated evidence.
- When a test or validation fails, diagnose and repair it before reporting success.
- Do not rely on self-reported success; inspect generated JSON, SQL dumps, logs,
  row counts, and UI/API behavior.

## Phase 1 — Contain and snapshot

Execute `10-PHASE-1-CONTAIN-SNAPSHOT.md`.

Required result:

- verified dumps of every non-template PostgreSQL database
- SHA-256 manifest
- restore verification into a disposable recovery-verification database
- table and row-count inventories
- recovery-candidate assessment
- no database modifications

Commit only scripts/docs required for safer backup or inventory.
Do not commit dumps or secrets.

Update the state file to:

`PHASE_1_AWAITING_CODEX_REVIEW`

Then stop.

## After Codex Phase 1 review

Do not continue until this file exists:

`docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-1-REVIEW.md`

Read the review.

- Resolve every Critical and High finding.
- Resolve Medium findings that affect recovery correctness.
- Re-run Phase 1 evidence where required.
- Add a finding-disposition section to the state file.

Then execute Phase 2.

## Phase 2 — Permanent test isolation

Execute `11-PHASE-2-PERMANENT-TEST-ISOLATION.md`.

Required result:

- owner and E2E use different PostgreSQL services, users, networks, projects,
  credentials, and volumes
- owner runtime cannot run pytest
- destructive helpers require test database identity
- canonical test runner uses only isolated infrastructure
- dry-run audit is technically read-only
- destructive owner operations require verified same-run backup
- all automated test suites pass on isolated infrastructure

Update the state file to:

`PHASE_2_AWAITING_CODEX_REVIEW`

Then stop.

## After Codex Phase 2 review

Do not continue until this file exists:

`docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-2-REVIEW.md`

Resolve all Critical and High findings. Re-run evidence.

Then execute Phase 3.

## Phase 3 — Recovery candidate

Execute `12-PHASE-3-RECOVER-OWNER-CANDIDATE.md`.

Required result:

- recovery staging database built from verified validation snapshot
- old schema upgraded only in staging
- row-level recovery classification and exclusions
- new owner-candidate database created
- trustworthy owner state recovered
- current jobs reconstructed from Gmail/connectors where possible
- no fixture/E2E/PG-test rows
- full API, database, Fresh Jobs, Gmail, Drive, packet, and login validation
- candidate backup and rollback plan

Update the state file to:

`GATE_2_OWNER_CUTOVER_APPROVAL_REQUIRED`

Then stop. Do not switch the canonical owner database automatically.

## After owner cutover approval

Only after the owner explicitly writes:

`APPROVE OWNER CANDIDATE CUTOVER`

execute the documented reversible cutover.

Then execute `13-PHASE-4-FINAL-VALIDATION.md`.

Update the state file to:

`FINAL_AWAITING_CODEX_REVIEW`

Stop.

## Completion criteria

Do not declare recovery complete unless:

- owner data counts and critical records are documented
- backup and restore drill pass
- owner and test DB isolation is proven
- Fresh Jobs uses corrected eligibility and current source data
- manual opportunities remain accessible
- Gmail and Drive survive restart
- no open Critical/High defects
- Codex final review is GO
- Workflow Lock 01 owner validation is complete

Return a compact execution report at every stop point with:

- phase
- Git SHA
- files changed
- commands run
- test results
- generated evidence paths
- database names touched
- explicit confirmation of databases not modified
- open risks
- exact next reviewer action
