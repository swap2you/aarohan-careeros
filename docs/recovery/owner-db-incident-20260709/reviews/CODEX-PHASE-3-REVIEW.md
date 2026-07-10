# Codex Phase 3 Review - Owner Recovery Candidate

Reviewer: Codex independent read-only reviewer  
Review date: 2026-07-10  
Repository: `C:\Development\Workspace\aarohan-careeros`  
Phase state reviewed: `GATE_2_OWNER_CUTOVER_APPROVAL_REQUIRED`

## Verdict

NO GO

Do not approve or perform owner cutover. Phase 3 stopped safely before cutover, created a verified backup of the candidate, and left `career_os` / `career_os_validation` key counts unchanged. However, the owner candidate is not a usable owner database and has unresolved Critical and High findings.

## Critical Findings

### CODEX-P3-CRITICAL-001 - Candidate has no usable career workflow corpus

The candidate contains zero companies, zero jobs, zero applications, and zero application document versions while reporting validation passed. The execution report records zero imported companies/jobs/applications/document versions and 50 processed Gmail messages, 30 recruiter signals, and 200 audit logs (`PHASE-3-EXECUTION-REPORT.md:31`). The data summary repeats this state (`OWNER-CANDIDATE-DATA-SUMMARY.json:33`, `OWNER-CANDIDATE-DATA-SUMMARY.json:34`, `OWNER-CANDIDATE-DATA-SUMMARY.json:35`, `OWNER-CANDIDATE-DATA-SUMMARY.json:37`, `OWNER-CANDIDATE-DATA-SUMMARY.json:38`, `OWNER-CANDIDATE-DATA-SUMMARY.json:43`, `OWNER-CANDIDATE-DATA-SUMMARY.json:45`, `OWNER-CANDIDATE-DATA-SUMMARY.json:47`).

Independent read-only query against `career_os_owner_candidate` confirmed:

- `companies=0`
- `jobs=0`
- `applications=0`
- `application_document_versions=0`
- `processed_gmail_messages=50`
- `oauth_tokens=3`
- `recruiter_signals=30`
- `audit_logs=200`

Impact: promoted owner runtime would have no Fresh Jobs, no applications, no packets, and no document history. This is not a recovered owner database.

Required correction: Gmail/API reconstruction must complete and be validated before cutover, or the cutover proposal must explicitly be reframed as an intentionally empty owner reset with owner acceptance of data loss. Current evidence does neither.

### CODEX-P3-CRITICAL-002 - Gmail idempotency rows can suppress future recovery of excluded jobs

The candidate imports 50 `processed_gmail_messages` while importing zero jobs (`OWNER-CANDIDATE-DATA-SUMMARY.json:43`, `OWNER-CANDIDATE-DATA-SUMMARY.json:70`, `OWNER-CANDIDATE-DATA-SUMMARY.json:71`). The reconstruction report evaluated 116 jobs but imported none: accepted 0, owner_review 0, quarantined 5, rejected 111 (`JOB-RECONSTRUCTION-REPORT.json:4`, `JOB-RECONSTRUCTION-REPORT.json:6`, `JOB-RECONSTRUCTION-REPORT.json:7`, `JOB-RECONSTRUCTION-REPORT.json:8`, `JOB-RECONSTRUCTION-REPORT.json:9`).

The implementation classifies every non-fixture Gmail processed row as `OWNER_CONFIRMED` without tying it to whether the message's parsed job was imported (`apps/api/app/services/recovery_row_classification.py:350`, `apps/api/app/services/recovery_row_classification.py:357`, `apps/api/app/services/recovery_row_classification.py:358`). The builder then copies those rows directly (`apps/api/scripts/phase3_build_candidate.py:124`, `apps/api/scripts/phase3_build_candidate.py:275`).

Impact: future Gmail sync may treat valid historical messages as already processed even though their jobs were excluded from the promoted database. That can permanently skip valid alerts.

Required correction: before cutover, prove idempotent rebuild semantics or reset/reclassify/replay processed Gmail rows using parser/version-aware recovery evidence. Do not promote processed Gmail rows that can block job reconstruction.

## High Findings

### CODEX-P3-HIGH-001 - Candidate validation is too weak and passes the unsafe empty candidate

`phase3_validate_candidate.py` counts users/jobs/applications/oauth/processed Gmail, checks duplicate OAuth/Gmail rows and a few orphan cases, then passes when there are no defects (`apps/api/scripts/phase3_validate_candidate.py:47`, `apps/api/scripts/phase3_validate_candidate.py:48`, `apps/api/scripts/phase3_validate_candidate.py:49`, `apps/api/scripts/phase3_validate_candidate.py:50`, `apps/api/scripts/phase3_validate_candidate.py:51`, `apps/api/scripts/phase3_validate_candidate.py:81`, `apps/api/scripts/phase3_validate_candidate.py:90`, `apps/api/scripts/phase3_validate_candidate.py:125`). It does not fail on zero jobs/applications, Gmail processed rows without imported jobs, OAuth decryptability/refresh viability, Drive folder usability, workflow smoke coverage, or audit resource references to absent jobs.

Evidence shows the validator returned `passed=True` with jobs 0 and applications 0 (`OWNER-CANDIDATE-VALIDATION-REPORT.md:8`, `OWNER-CANDIDATE-VALIDATION-REPORT.md:13`, `OWNER-CANDIDATE-VALIDATION-REPORT.md:14`, `OWNER-CANDIDATE-VALIDATION-REPORT.md:15`, `OWNER-CANDIDATE-VALIDATION-REPORT.md:17`).

Required correction: expand validation gates so an empty or functionally unusable owner candidate cannot pass.

### CODEX-P3-HIGH-002 - OAuth token selection is not proven operational

The source had 9 OAuth token rows classified as owner-confirmed, but the builder silently deduplicates to 3 by `(provider, service, account_email)` in descending id order (`apps/api/scripts/phase3_build_candidate.py:208`, `apps/api/scripts/phase3_build_candidate.py:214`, `apps/api/scripts/phase3_build_candidate.py:217`, `apps/api/scripts/phase3_build_candidate.py:225`, `apps/api/scripts/phase3_build_candidate.py:226`). The manifest evidence only states `provider='google'` for all OAuth rows; it does not prove account identity, refresh viability, token decryptability with the current key, fixture exclusion beyond email substring checks, or that the latest row is the right row (`ROW-RECOVERY-MANIFEST.json:3`, `apps/api/app/services/recovery_row_classification.py:337`, `apps/api/app/services/recovery_row_classification.py:346`).

Independent metadata query showed selected rows for `swapnilpatil.tech@gmail.com`, services `google`, `gmail`, and `drive`, active, with Gmail/Drive scopes and non-null encrypted payloads. I did not decrypt token values and did not expose secrets. That confirms metadata shape only, not that the promoted app can refresh or use them.

Required correction: provide non-secret proof that the selected tokens decrypt with the current production key, contain required refresh/access material, are not fixtures, map to the intended Google account, and can be refreshed or safely require reconnect before cutover.

### CODEX-P3-HIGH-003 - Drive recovery is metadata-only and unvalidated

The candidate has no standalone Drive metadata recovery evidence. It carries `system_settings` for `drive_active_root_folder_id`, `drive_root_source=configured`, and `drive_subfolder_ids`, but no proof that the app can reuse those folders after restart, that OAuth Drive access can reach them, or that duplicate root creation is prevented.

The cutover plan only says to smoke-test OAuth metadata, Gmail idempotency, applications, and Fresh Jobs after redirect (`OWNER-CANDIDATE-CUTOVER-PLAN.md:21`, `OWNER-CANDIDATE-CUTOVER-PLAN.md:23`). It does not define a pre-cutover Drive root restoration/rebind check.

Required correction: prove either safe reuse of the existing app-created Drive root or a one-time reconnect/rebind process that avoids duplicate roots and survives restart.

### CODEX-P3-HIGH-004 - Audit history references absent jobs

The builder imports 200 owner-confirmed audit logs independent of whether referenced entities survived (`apps/api/scripts/phase3_build_candidate.py:128`, `apps/api/scripts/phase3_build_candidate.py:279`). Classification marks non-E2E/non-fixture audit logs as owner-confirmed based on event type only (`apps/api/app/services/recovery_row_classification.py:391`, `apps/api/app/services/recovery_row_classification.py:403`, `apps/api/app/services/recovery_row_classification.py:404`).

Independent read-only query found 131 `audit_logs` with `resource_type` job/jobs and non-null `resource_id` while the candidate has zero jobs. Audit event counts included 119 `job.ingested` job events and 11 `job.deduplicated` job events.

Impact: promoted history would assert job activity for records that do not exist. UI/API audit readers may mislead the owner or fail if they expect resources to resolve.

Required correction: either exclude/quarantine audit rows tied to excluded jobs or mark them as historical recovery-only evidence outside the promoted owner runtime path.

### CODEX-P3-HIGH-005 - Cutover identity transition is not specified enough for promotion

The candidate correctly carries `OWNER_CANDIDATE` identity UUID `78010e56-041c-4fec-b8f7-0f9ca313d267` (`RECOVERY-ORCHESTRATION-STATE.md:83`, `RECOVERY-ORCHESTRATION-STATE.md:84`; live query confirmed the same marker). The cutover plan proposes redirecting owner runtime to `career_os_owner_candidate` and rerunning identity preflight (`OWNER-CANDIDATE-CUTOVER-PLAN.md:21`, `OWNER-CANDIDATE-CUTOVER-PLAN.md:22`), but it does not specify how `OWNER_CANDIDATE` becomes canonical `OWNER`, what the final UUID/purpose must be, whether marker immutability permits that transition, or how roles are reprovisioned without bypassing identity controls.

Required correction: define and test an authorized promotion mechanism with final expected identity purpose/UUID, role ownership, rollback identity restoration, and explicit prohibition of unsupported database rename/URL-only promotion.

## Medium Findings

### CODEX-P3-MEDIUM-001 - Zero ambiguous rows is not credible without stronger sampling evidence

The ambiguous report says total ambiguous is 0 (`AMBIGUOUS-ROWS-REPORT.md:5`) while the classifier processed 717 rows and classified 343 as live-source-reconstructable, 297 as owner-confirmed, 45 excluded, 22 test, 5 fixture, and 5 system-required (`PHASE-3-EXECUTION-REPORT.md:26`). The rules classify all non-fixture processed Gmail rows as owner-confirmed and all non-E2E/non-fixture audit logs as owner-confirmed, which explains the zero ambiguous outcome but is too broad for owner recovery.

Required correction: provide category-by-category sampling evidence with row-level rationale, especially for processed Gmail, OAuth, audit, application_events, representation_records, and recruiter_signals.

### CODEX-P3-MEDIUM-002 - Application exclusions look plausible but need owner-level confirmation

All three applications were excluded because their linked jobs were classified as PG test/E2E test (`ROW-EXCLUSION-MANIFEST.json:193`, `ROW-EXCLUSION-MANIFEST.json:205`, `ROW-EXCLUSION-MANIFEST.json:217`). The row-level reasons are plausible. However, because all application workflow rows disappear, owner acceptance should explicitly confirm that no real manual opportunity, submitted packet, interview, or document version was lost.

### CODEX-P3-MEDIUM-003 - Backup/restore is structurally verified but does not prove candidate correctness

The backup manifest records candidate dump SHA256 `dbd092cfea58d1742f6019f36dbaafc233af180498a2ca22012afcec051dc862`, size 246,612 bytes, and `restore_verified=true` with 31/31 tables and no row-count mismatches (`OWNER-CANDIDATE-BACKUP-MANIFEST.json:10`, `OWNER-CANDIDATE-BACKUP-MANIFEST.json:15`). Independent `Get-FileHash` matched that SHA256.

This proves the empty/unsafe candidate can be backed up and restored. It does not prove it is safe to promote.

## Verified Controls

- Phase state is Gate 2 and cutover is not performed (`RECOVERY-ORCHESTRATION-STATE.md:5`, `RECOVERY-ORCHESTRATION-STATE.md:87`).
- Phase 3 commit under review is `cd344be`; current `main` is `1af3145`, with only the orchestration state SHA update after `cd344be`.
- `career_os` and `career_os_validation` key table counts matched the orchestration state: owner jobs 75, applications 2, OAuth 0, processed Gmail 0; validation jobs 124, applications 3, OAuth 9, processed Gmail 59 (`RECOVERY-ORCHESTRATION-STATE.md:89`, `RECOVERY-ORCHESTRATION-STATE.md:99`).
- Candidate/recovery runtime and migrate roles are not superusers in live PostgreSQL.
- CI run `29119930595` is green at `1af31456ea522f33d42bd078169188ff633c4948`. API tests ran with `AAROHAN_DB_IDENTITY_PURPOSE=CI` and reported 266 passed, 2 skipped. Playwright fixture job also completed successfully on an ephemeral GitHub Actions PostgreSQL service with CI identity checks.
- I did not run tests against `career_os`, did not mutate databases, did not reconnect Google, did not perform cutover, and did not start Phase 4/Cowork UAT.

## Review Commands

Representative read-only commands used:

- `git status --short --branch`
- `git rev-parse HEAD`
- `git diff --stat cd344be..HEAD`
- `git show --stat --oneline cd344be`
- `Get-Content` / `ConvertFrom-Json` over Phase 3 report manifests
- read-only `psql SELECT` queries against `career_os_owner_candidate`, `career_os`, and `career_os_validation`
- `Get-FileHash` on `career_os_owner_candidate.sql`
- `gh run view 29119930595 --json ...`
- `gh run view 29119930595 --log --job ...`

## Gate Decision

NO GO. Critical and High findings remain. The candidate is safe to retain as evidence, but not safe to promote as the owner runtime database.
