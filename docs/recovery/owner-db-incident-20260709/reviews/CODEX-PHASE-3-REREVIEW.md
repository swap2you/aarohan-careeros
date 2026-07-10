# Codex Phase 3 Rereview - Owner Candidate After Rework

Reviewer: Codex independent read-only reviewer  
Review date: 2026-07-10  
Repository: `C:\Development\Workspace\aarohan-careeros`  
Evidence root reviewed: `artifacts/recovery/incident-20260709/phase3-rework-20260710_171518`

## Verdict

NO GO

Cursor resolved several Phase 3 data-safety issues: the candidate is no longer empty, Gmail suppressors are versioned and replay-aware, workflow smoke passed and cleaned its validation rows, audit/recruiter orphans are zero, owner/validation row counts remain unchanged, cutover rehearsal ran on disposable clones, and CI is green at current HEAD.

However, the candidate is still not safe to cut over. The rework evidence itself records two open High defects: OAuth tokens decrypt but cannot refresh, Gmail/Drive read health is false, and Drive root resolution is blocking. Under the stated rules, any remaining High finding requires NO GO.

## High Findings

### CODEX-P3-HIGH-REWORK-001 - OAuth is decryptable but not operational

Status: Open.

Evidence:

- `OWNER-CANDIDATE-VALIDATION.json` has `passed=false`, `oauth_passed=false`, `oauth_requires_reconnect=true`, and two High defects.
- `OWNER-CANDIDATE-DEFECT-REGISTER.md:5` states that tokens decrypt but lack a valid refresh token and the owner must reconnect Google before cutover.
- `OAUTH-CANDIDATE-VALIDATION.json` records `passed=false`, `decryptable_owner_tokens=3`, `requires_owner_reconnect=true`, `selected_count=0`.
- Each redacted token row maps to `swapnilpatil.tech@gmail.com`, decrypts, has Gmail/Drive scopes, but has `has_refresh_token=false`, `refreshable=false`, `gmail_read_ok=false`, and `drive_read_ok=false`.
- The validator correctly converts this into a High defect when `requires_owner_reconnect` is true (`apps/api/scripts/phase3_rework_validate_candidate.py:89`, `apps/api/scripts/phase3_rework_validate_candidate.py:93`, `apps/api/scripts/phase3_rework_validate_candidate.py:95`).

Independent live metadata query confirmed the candidate still has three active Google token rows for the owner account with encrypted payloads and expected scopes. I did not expose token values. Metadata is not enough: the evidence proves decryptability but not usable refresh, Gmail read, or Drive read.

Required before GO:

- Owner reconnects Google on the candidate runtime.
- Re-run OAuth validation shows at least one selected owner token row, refresh succeeds, Gmail read health succeeds, and Drive read health succeeds.
- Evidence remains redacted and does not expose token material.

### CODEX-P3-HIGH-REWORK-002 - Drive root remains unresolved and blocking

Status: Open.

Evidence:

- `OWNER-CANDIDATE-DEFECT-REGISTER.md:6` records High `drive_root_blocking`.
- `DRIVE-ROOT-RESOLUTION.json` records `accessible=false`, `blocking=true`, `folder_id=null`, `candidates_found=0`, with reason `drive_token_error: Refresh token revoked or expired. Disconnect Google and reconnect with consent.`
- The cutover plan lists OAuth refresh, Gmail read, and Drive root resolution as a precondition (`OWNER-CANDIDATE-CUTOVER-PLAN.md:12`).

Independent live query confirmed the candidate still carries configured Drive settings, but the evidence does not prove those folders are accessible with current candidate credentials.

Required before GO:

- Reconnect or otherwise prove a valid candidate Drive token.
- Resolve exactly one existing Drive root or explicitly create/rebind one without duplicate roots.
- Verify required subfolders and restart persistence before cutover.

### CODEX-P3-HIGH-REWORK-003 - Identity promotion rehearsal does not prove final OWNER marker transition

Status: Open as a cutover-design risk.

Evidence:

- The cutover rehearsal passed for backup, clone, rename, and rollback mechanics.
- `CUTOVER-REHEARSAL-MANIFEST.json` shows the promoted clone still had `OWNER_CANDIDATE` purpose and notes that real promotion requires a fresh OWNER marker.
- The cutover plan says to provision a new immutable `OWNER` identity UUID after renaming (`OWNER-CANDIDATE-CUTOVER-PLAN.md:21`, `OWNER-CANDIDATE-CUTOVER-PLAN.md:22`, `OWNER-CANDIDATE-CUTOVER-PLAN.md:23`, `OWNER-CANDIDATE-CUTOVER-PLAN.md:30`, `OWNER-CANDIDATE-CUTOVER-PLAN.md:31`).

This is more explicit than the original Phase 3 plan, but the exact fail-closed promotion path is still not rehearsed because the immutable marker transition is only documented, not executed on the disposable promoted clone.

Required before GO:

- Rehearse the full identity transition on disposable clones, including the final `OWNER` marker creation/provisioning, runtime/migrate role rebind, and negative proof that the promoted database fails startup if the marker remains `OWNER_CANDIDATE`.

## Resolved Or Improved Findings

### Gmail suppressors and replay

Status: Resolved for suppression safety; replay still pending until OAuth reconnect.

Evidence:

- Live candidate has 50 processed Gmail rows: 21 `REPLAY_REQUIRED` job alerts and 29 `LEGACY` lifecycle rows.
- `GMAIL-REPLAY-CLASSIFICATION.json` classifies 21 `REPLAY_REQUIRED_JOB_ALERT` and 29 `NON_JOB_LIFECYCLE`.
- `OWNER-CANDIDATE-VALIDATION-REPORT.md:14` reports `gmail_replay_pending=21`.
- `OWNER-CANDIDATE-VALIDATION-REPORT.md:15` reports `gmail_suppressors_without_jobs=0`.
- Migration `0014_gmail_replay_state.py` adds parser/status/output fields to `processed_gmail_messages`.
- `gmail_replay.py` uses `parser_version`, `processing_status`, `produced_entity_type`, and `produced_entity_count` to determine replay need and idempotent completion.

The 21 pending rows cannot suppress missing job output because they remain replay-required instead of completed idempotency rows. Final replay still depends on OAuth reconnect.

### Candidate operational corpus

Status: Substantially improved.

Evidence:

- `OWNER-CANDIDATE-DATA-SUMMARY.json` records 102 companies, 131 jobs, 15 accepted fresh jobs, and 116 rejected jobs.
- Independent live query confirmed 102 companies, 131 jobs, zero applications, zero application document versions, three OAuth rows, 50 processed Gmail rows, 30 recruiter signals, and 240 audit logs.
- `CANDIDATE-LIVE-JOB-RECONSTRUCTION.json` records accepted 15, owner_review 0, quarantined 0, rejected 116.
- Manual sample inspection from the reconstruction evidence included accepted jobs from CVS Health, Wapa, 07 CMG Strategy, Westinghouse, and Virtual Vocations with titles, companies, locations, source URLs, freshness buckets, and recommended profiles.

This resolves the original "zero jobs" blocker. The candidate is operationally useful for Fresh Jobs, but it is still not cutover-safe while OAuth/Drive are blocked.

### Workflow smoke and validation-only cleanup

Status: Resolved.

Evidence:

- `CANDIDATE-WORKFLOW-SMOKE-EVIDENCE.json` reports `passed=true`.
- Smoke covered login, job detail, rescore/shortlist path, packet generation, document version creation, approval, manual application open, apply readiness, duplicate risk visibility, timeline, manual application state, cleanup, and job state restoration.
- `OWNER-CANDIDATE-VALIDATION-REPORT.md:19` reports `workflow_smoke_passed=true`.
- `OWNER-CANDIDATE-VALIDATION-REPORT.md:25` reports `validation_provenance_remaining=0`.

### Historical applications/documents

Status: Acceptable.

Evidence:

- Candidate still has zero persisted applications and zero document versions after validation cleanup.
- Smoke-created validation rows were removed.

No historical applications/documents appear fabricated. Owner acceptance is still needed if they expect prior real applications to exist, but the evidence is internally consistent.

### Recruiter/audit integrity

Status: Resolved.

Evidence:

- `AUDIT-RECRUITER-INTEGRITY.json` reports `orphan_count_after=0` and `passed=true`.
- Independent live SELECT checks found zero orphan recruiter job/application/company refs, zero missing numeric audit job refs, zero nonnumeric audit job refs, zero test jobs, and zero validation-provenance jobs.

### Backup and evidence integrity

Status: Partially resolved.

Evidence:

- `PHASE-3-REWORK-MANIFEST.json` records candidate dump `career_os_owner_candidate.sql`, SHA256 `7f2c441d5be537d451636aa404b2e687569762a297f8ec6c366f25857e6e0ee9`, size `2704938`.
- Independent `Get-FileHash` matched that SHA256.

The evidence proves checksum integrity. I did not find a separate restore-verification manifest for the rework candidate dump equivalent to Phase 1/initial Phase 3 restore checks. Because cutover is already NO GO on OAuth/Drive, this remains a pre-GO verification item.

### Owner and validation unchanged

Status: Verified.

Independent read-only row counts:

- `career_os`: jobs 75, applications 2, oauth_tokens 0, processed_gmail_messages 0, users 2.
- `career_os_validation`: jobs 124, applications 3, oauth_tokens 9, processed_gmail_messages 59, users 2.

These match `RECOVERY-ORCHESTRATION-STATE.md`.

### CI and isolated execution

Status: Verified.

Current HEAD is `41c3650cc9c29968173f22118613359c4a9d5c29`. CI run `29125417509` is successful at that SHA. Jobs completed successfully:

- `validation-scans`
- `api-tests`
- `web-build`
- `playwright-fixture`

The run includes owner-stack pytest scan, privileged owner helper scan, CI identity marker assertion, pytest, Playwright fixture execution, and the Playwright assertion that it is not using OWNER identity.

## Checklist Result

1. Processed Gmail records cannot suppress missing job outputs: verified for current candidate.
2. Replay is versioned, selective, and idempotent: verified by migration/code/evidence; replay remains pending until OAuth reconnect.
3. OAuth tokens decrypt and refresh against correct owner account: decrypt/account verified; refresh failed. High open.
4. Gmail and Drive read health proven: not proven; both false in evidence. High open.
5. Existing Drive root uniquely resolved or explicit blocker: explicit blocker remains. High open.
6. Current live jobs reconstructed and inspected: verified from report and samples.
7. Candidate operationally useful: partially yes for Fresh Jobs/workflow; not cutover-safe due integrations.
8. No historical applications/documents fabricated: verified.
9. Candidate workflow smoke proven and validation rows removed: verified.
10. Recruiter/audit zero orphan or test references: verified.
11. Candidate validation detects operational emptiness/missing integrations: verified; validation fails on missing integrations.
12. Cutover/rollback rehearsed on disposable clones: partially verified; rename/rollback rehearsed, final OWNER marker transition not rehearsed.
13. OWNER_CANDIDATE to OWNER transition explicit and fail-closed: documented but not fully rehearsed; High open.
14. Candidate backup verified and identity-bound: checksum verified; restore verification not found in rework evidence.
15. `career_os` and `career_os_validation` unchanged: verified.
16. CI green and tests isolated/candidate infrastructure: verified for CI; local candidate smoke used candidate runtime.

## Review Boundaries

I did not modify code, commit, mutate owner or validation databases, perform cutover, reconnect Google, run owner tests, or start Cowork. Database checks were read-only SELECTs. The only file created by this review is this rereview document.

## Gate Decision

NO GO.

Do not cut over until the High OAuth/Drive blockers are resolved, Gmail replay is completed or explicitly validated after reconnect, the full OWNER identity transition is rehearsed fail-closed on disposable clones, and the rework candidate backup has restore-verification evidence.
