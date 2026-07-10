# Codex Phase 1 Review - Owner DB Incident 20260709

Reviewer: Codex independent read-only reviewer
Review date: 2026-07-09
Repository: `C:\Development\Workspace\aarohan-careeros`
Phase state reviewed: `PHASE_1_AWAITING_CODEX_REVIEW`

## Verdict

GO

No Critical or High findings remain for Phase 1. Backups, checksums, restore verification, database inventory, row counts, and no-write guarantees were reproducible from the canonical evidence set and read-only catalog checks.

Phase 2 should proceed only under the documented next step: permanent owner/E2E database isolation before any owner cutover.

## Scope and commands

Read:

- `docs/recovery/owner-db-incident-20260709/00-START-HERE.md`
- `docs/recovery/owner-db-incident-20260709/02-CODEX-MASTER-REVIEWER.md`
- `docs/recovery/owner-db-incident-20260709/RECOVERY-ORCHESTRATION-STATE.md`
- `scripts/recovery/Invoke-IncidentPhase1Snapshot.ps1`
- Canonical Phase 1 evidence under `artifacts/recovery/incident-20260709/20260709_172617/`

Independent checks performed:

- `git status --short --branch`
- `rg --files docs/recovery/owner-db-incident-20260709 artifacts/recovery/incident-20260709/20260709_172617 scripts/recovery`
- `Get-FileHash -Algorithm SHA256` over all canonical dump files
- JSON parsing of `BACKUP-MANIFEST.json`, `DATABASE-INVENTORY.json`, and `TABLE-ROW-COUNTS.json`
- Read-only PostgreSQL catalog query: `SELECT datname FROM pg_database WHERE datistemplate=false ORDER BY datname;`
- Read-only PostgreSQL table-count queries for `career_os`, `career_os_validation`, and `career_os_e2e`
- Secret-pattern scan over recovery reports, recovery docs, and recovery scripts
- `git check-ignore -v` for canonical recovery artifacts

Not performed:

- No tests were run.
- No restore was run by Codex.
- No database was written or mutated by Codex.
- No commit, staging, branch switch, cleanup, or deployment was performed.

## Changed-file validation

The repository state file reports untracked `docs/recovery/`, `scripts/recovery/`, and `apps/web/tsconfig.tsbuildinfo` with no committed changes at `75f64285a7110d8f7811fa85db1eea1e7f9a511b` (`RECOVERY-ORCHESTRATION-STATE.md:29`). My `git status --short --branch` check reproduced the same untracked set before this review file was created.

The canonical artifact tree is ignored by Git through `.gitignore:12` (`artifacts/`), confirmed with `git check-ignore -v` for dump and report files.

## Evidence validation

### Phase state

- Current state is `PHASE_1_AWAITING_CODEX_REVIEW` (`RECOVERY-ORCHESTRATION-STATE.md:3`, `RECOVERY-ORCHESTRATION-STATE.md:5`).
- Canonical evidence timestamp is `20260709_172617` (`RECOVERY-ORCHESTRATION-STATE.md:43`).
- Evidence root is `artifacts/recovery/incident-20260709/20260709_172617/` (`RECOVERY-ORCHESTRATION-STATE.md:60`).

### Database inventory

`DATABASE-INVENTORY.json` lists exactly these non-template databases:

- `career_os` (`DATABASE-INVENTORY.json:5`)
- `career_os_e2e` (`DATABASE-INVENTORY.json:12`)
- `career_os_validation` (`DATABASE-INVENTORY.json:19`)
- `postgres` (`DATABASE-INVENTORY.json:26`)

My independent read-only catalog query returned the same set:

- `career_os`
- `career_os_e2e`
- `career_os_validation`
- `postgres`

No `recovery_verify_*` database remains.

### Backups and checksums

`BACKUP-MANIFEST.json` records dumps and checksums for `globals`, `career_os`, `career_os_e2e`, `career_os_validation`, and `postgres` (`BACKUP-MANIFEST.json:183`, `BACKUP-MANIFEST.json:189`, `BACKUP-MANIFEST.json:195`, `BACKUP-MANIFEST.json:201`, `BACKUP-MANIFEST.json:207`).

Independent file hash verification matched the manifest exactly:

| Dump | Size bytes | SHA-256 |
|---|---:|---|
| `career_os.sql` | 2265321 | `83b8242324aaf5f2ca20f36adf40019d7c22b4bb1f21274995296d195899ab70` |
| `career_os_e2e.sql` | 205261 | `4d7f326c0fd60330448474e7aafd085fdb842d79f740e1fc840668aedd68c381` |
| `career_os_validation.sql` | 2088441 | `d44d2c57357f52ba296283601a6a2ab45b1ccd9ad68f95d8833b95fe3d7eddac` |
| `globals.sql` | 673 | `dabc689e27ab1befe4df36e1f9edf3845d01cdf81034ed3bc82d20ae36ca38ed` |
| `postgres.sql` | 643 | `6cd4c5434c68af0dc53ec8a492edad6d7da56d052b46b736b1b1d228fa09de85` |

### Restore verification

The manifest records successful restore verification for all database dumps:

- `career_os`: verified true, 62/62 tables, zero mismatches (`BACKUP-MANIFEST.json:216`, `BACKUP-MANIFEST.json:217`, `BACKUP-MANIFEST.json:220`)
- `career_os_e2e`: verified true, 30/30 tables, zero mismatches (`BACKUP-MANIFEST.json:224`, `BACKUP-MANIFEST.json:225`, `BACKUP-MANIFEST.json:228`)
- `career_os_validation`: verified true, 60/60 tables, zero mismatches (`BACKUP-MANIFEST.json:232`, `BACKUP-MANIFEST.json:233`, `BACKUP-MANIFEST.json:236`)
- `postgres`: verified true, 0/0 tables, zero mismatches (`BACKUP-MANIFEST.json:240`, `BACKUP-MANIFEST.json:241`, `BACKUP-MANIFEST.json:244`)

The Phase 1 script performs restore verification by creating disposable `recovery_verify_*` databases, replaying each dump with `ON_ERROR_STOP=1`, comparing table counts and row counts, and dropping the verification database afterward (`Invoke-IncidentPhase1Snapshot.ps1:173`, `Invoke-IncidentPhase1Snapshot.ps1:174`, `Invoke-IncidentPhase1Snapshot.ps1:180`, `Invoke-IncidentPhase1Snapshot.ps1:187`, `Invoke-IncidentPhase1Snapshot.ps1:188`, `Invoke-IncidentPhase1Snapshot.ps1:213`).

### Row counts and no-write guarantee

The manifest records owner and validation unchanged after snapshot (`BACKUP-MANIFEST.json:247`, `BACKUP-MANIFEST.json:249`, `BACKUP-MANIFEST.json:253`). The orchestration state also says baseline and post-snapshot row counts are identical for `career_os` and `career_os_validation`, and that no disposable verification databases remain (`RECOVERY-ORCHESTRATION-STATE.md:53`).

Independent read-only table-count checks reproduced the recorded totals:

| Database | Tables | Total rows |
|---|---:|---:|
| `career_os` | 62 | 523 |
| `career_os_validation` | 60 | 938 |
| `career_os_e2e` | 30 | 351 |

The JSON row-count evidence contains baseline and post-snapshot sections for all three application databases. Key owner-relevant values support the recovery assessment: `career_os` has zero OAuth tokens and zero processed Gmail messages (`TABLE-ROW-COUNTS.json:1239`, `TABLE-ROW-COUNTS.json:1250`), while `career_os_validation` has 9 OAuth tokens and 59 processed Gmail messages (`TABLE-ROW-COUNTS.json:1264`, `TABLE-ROW-COUNTS.json:1275`).

### Recovery source assessment

The assessment correctly distinguishes:

- `career_os` as contaminated owner runtime, not source of truth (`RECOVERY-CANDIDATE-ASSESSMENT.md:29`)
- `career_os_validation` as primary recovery candidate source (`RECOVERY-CANDIDATE-ASSESSMENT.md:30`)
- `career_os_e2e` as fixture/test data to exclude (`RECOVERY-CANDIDATE-ASSESSMENT.md:91`)

The recommended path is to build an owner candidate from the verified `career_os_validation` snapshot after schema upgrade and row-level exclusion of test/fixture rows (`RECOVERY-CANDIDATE-ASSESSMENT.md:96`). It explicitly prohibits direct restore over `career_os` without Gate 2 owner approval (`RECOVERY-CANDIDATE-ASSESSMENT.md:98`).

### Secret handling

No common secret-token patterns were found in recovery reports, recovery docs, or recovery scripts. The canonical SQL dumps are raw database backups and contain sensitive recovery data by design; they are under ignored `artifacts/` storage and must not be committed or published.

## Findings

### CODEX-P1-LOW-001

Severity: Low

File and line: `artifacts/recovery/incident-20260709/20260709_172617/reports/RECOVERY-CANDIDATE-ASSESSMENT.md:73`, `artifacts/recovery/incident-20260709/20260709_172617/reports/RECOVERY-CANDIDATE-ASSESSMENT.md:75`

Evidence: The human-readable recovery assessment renders missing `career_os_validation` owner-relevant tables as blank values for `public.connector_runs` and `public.gmail_ingest_reviews`. The structured row-count JSON shows these as `null` (`TABLE-ROW-COUNTS.json:1280`, `TABLE-ROW-COUNTS.json:1281`).

Failure or exploit path: A reader could mistake blank Markdown values for a report generation failure rather than absent tables in the validation schema.

Required correction: In the next report generation, render absent tables explicitly as `absent` or `null`, not blank Markdown values.

Validation required: Regenerate or amend the assessment display and confirm the structured JSON still distinguishes real zero counts from absent tables.

Phase gate impact: Does not block Phase 1. The full structured row-count evidence is complete and reproducible.

### CODEX-P1-LOW-002

Severity: Low

File and line: `docs/recovery/owner-db-incident-20260709/RECOVERY-ORCHESTRATION-STATE.md:29`

Evidence: The working tree includes unrelated untracked `apps/web/tsconfig.tsbuildinfo` alongside the intentional untracked recovery docs and scripts.

Failure or exploit path: Generated build state can obscure recovery-specific status review or be accidentally included in future repository hygiene work.

Required correction: Remove or ignore the build-info file after recovery review coordination, without touching database artifacts.

Validation required: Re-run `git status --short --branch` and confirm only intentional recovery files remain, or that generated build-info is ignored.

Phase gate impact: Does not block Phase 1. It is unrelated to backup integrity, restore verification, row counts, and no-write guarantees.

## Phase 1 gate conclusion

GO.

Proceed to Phase 2 permanent test isolation. Do not perform owner cutover, direct owner restore, cleanup execute, migration downgrade, or owner-stack tests as part of this Phase 1 approval.
