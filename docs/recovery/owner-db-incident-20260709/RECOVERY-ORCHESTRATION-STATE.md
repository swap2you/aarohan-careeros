# Recovery Orchestration State

## Current state

`FINAL_AWAITING_CODEX_REVIEW`

Allowed values:

- NOT_STARTED
- PHASE_1_RUNNING
- PHASE_1_AWAITING_CODEX_REVIEW
- PHASE_1_REWORK
- PHASE_2_RUNNING
- PHASE_2_AWAITING_CODEX_REVIEW
- PHASE_2_REWORK
- PHASE_3_RUNNING
- PHASE_3_REWORK
- GATE_2_OWNER_CUTOVER_APPROVAL_REQUIRED
- CUTOVER_APPROVED
- FINAL_VALIDATION_RUNNING
- FINAL_AWAITING_CODEX_REVIEW
- COMPLETE
- BLOCKED

## Repository

- Branch: main
- Start SHA: 75f64285a7110d8f7811fa85db1eea1e7f9a511b
- Phase 2 identity guard SHA: 81b1034b6bbce9d852996db7992cfee52d2dda25
- Phase 3 owner candidate SHA: cd344be
- Phase 3 rework SHA: 3672fdc
- Phase 3 final SHA: 87b9944
- Phase 3 disposition SHA: a57d589
- Phase 4 cutover SHA: 8e66d3e

## Database identities

| Purpose | Compose project | Service | Host | Database | Runtime user | Migrate user | Volume |
|---|---|---|---|---|---|---|---|
| Owner | aarohan-careeros | postgres | 127.0.0.1:5432 | career_os | career_os_runtime | career_os_migrate | aarohan-careeros_postgres_data |
| Validation | aarohan-careeros | postgres | 127.0.0.1:5432 | career_os_validation | n/a (recovery source) | n/a | aarohan-careeros_postgres_data |
| Recovery staging | aarohan-careeros | postgres | 127.0.0.1:5432 | career_os_recovery | career_os_recovery_runtime | career_os_recovery_migrate | aarohan-careeros_postgres_data |
| Owner candidate | aarohan-careeros-candidate | api-candidate | 127.0.0.1:5432 | career_os_owner_candidate | career_os_candidate_runtime | career_os_candidate_migrate | aarohan-careeros_postgres_data |
| E2E/Test | aarohan-careeros-test | postgres-e2e | 127.0.0.1:5433 | career_os_e2e | career_os_e2e_runtime | career_os_e2e_migrate | aarohan-careeros-test_postgres_e2e_data |

Immutable marker table: `aarohan_meta.database_identity` (migration `0013`).

## Phase evidence

### Phase 1

- Status: **COMPLETE — Codex GO**
- Evidence root: `artifacts/recovery/incident-20260709/20260709_172617/`
- Codex review: `docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-1-REVIEW.md` — **GO**

### Phase 2 (initial)

- Status: **NO GO — Codex review**
- Evidence root: `artifacts/recovery/incident-20260709/phase2-20260709_182613/`
- Codex review: `docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-2-REVIEW.md` — **NO GO**

### Phase 2 rework + final identity guard

- Status: **COMPLETE — Codex GO**
- Evidence roots:
  - `artifacts/recovery/incident-20260709/phase2-rework-20260709_225953/`
  - `artifacts/recovery/incident-20260709/phase2-final-identity-20260710_150438/`
- Reviews:
  - `docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-2-REREVIEW.md`
  - `docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-2-FINAL-REREVIEW.md` — **GO**

#### Codex finding disposition (Phase 2)

| ID | Severity | Disposition |
|---|---|---|
| CODEX-P2-HIGH-001 | High | **Resolved** |
| CODEX-P2-HIGH-002 | High | **Resolved** |
| CODEX-P2-HIGH-003 | High | **Resolved** |
| CODEX-P2-HIGH-004 | High | **Resolved** |
| CODEX-P2-MEDIUM-001 | Medium | **Resolved** |
| CODEX-P2-MEDIUM-002 | Medium | **Resolved** |

### Phase 3 — owner candidate (initial)

- Status: **NO GO — Codex review**
- Evidence: `artifacts/recovery/incident-20260709/phase3-20260710_154015/`
- Codex review: `docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-3-REVIEW.md` — **NO GO**

### Phase 3 rework

- Status: **COMPLETE — awaiting Codex re-review**
- Evidence root: `artifacts/recovery/incident-20260709/phase3-rework-20260710_171518/`
- Candidate runtime: API http://127.0.0.1:8002, Web http://127.0.0.1:3002
- Candidate identity UUID: `78010e56-041c-4fec-b8f7-0f9ca313d267`
- Cutover: **NOT PERFORMED**

### Phase 3 final remediation

- Status: **COMPLETE — Codex CONDITIONAL GO; M1 disposition closed**
- Evidence root: `artifacts/recovery/incident-20260709/phase3-final-20260710_221530/`
- Prior rework evidence: `artifacts/recovery/incident-20260709/phase3-rework-20260710_171518/`
- Codex review: `docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-3-FINAL-REREVIEW.md` — **CONDITIONAL GO**
- Owner disposition: `docs/recovery/owner-db-incident-20260709/OWNER-PHASE-3-CONDITIONAL-GO-DISPOSITION.md`
- Phase 3 final SHA: 87b9944
- Validation passed: **true** (0 defects)
- Cutover rehearsal: **passed** (OWNER marker promotion on disposable DB)
- Backup restore verification: **passed**

#### Phase 3 final disposition

| Area | Result |
|---|---|
| OAuth on candidate | Passed — swapnilpatil.tech@gmail.com, refresh/Gmail/Drive healthy, restart persistence verified |
| OAuth note | Side-effect triple on damaged `career_os` accepted — see owner disposition doc |
| Drive root | Bound `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr`, subfolders complete |
| Gmail replay | 156 scanned, 72 replayed, 0 suppressors |
| Manual job review | 9 accepted, 1 supplier/nuclear false positive rejected, 1 Blockstream duplicate removed |
| Cutover rehearsal | Full OWNER identity promotion rehearsed on disposable clones |
| Backup/restore | Passed with schema + row-count verification |

#### Codex Phase 3 final finding disposition

| ID | Severity | Disposition |
|---|---|---|
| CODEX-P3-FINAL-M1 | Medium | **Closed** — owner accepts canonical OAuth side-effect rows; see `OWNER-PHASE-3-CONDITIONAL-GO-DISPOSITION.md` |
| CODEX-P3-FINAL-L1 | Low | Open — dispose older disposable restore DBs before/at cutover |

#### Remaining owner-action blockers (pre-cutover)

| ID | Severity | Action |
|---|---|---|
| *(none — Gate 2 approved)* | | |

### Phase 4 — canonical cutover

- Status: **COMPLETE — awaiting Codex final review**
- Owner approval phrase: verified (`APPROVE OWNER CANDIDATE CUTOVER`)
- Evidence roots:
  - `artifacts/recovery/incident-20260709/phase4-cutover-20260711_042500/`
  - `artifacts/recovery/incident-20260709/phase4-resume-20260711_043000/`
- Cutover: **PERFORMED** (not rolled back — resume promotion completed)
- New canonical OWNER UUID: `8651fd13-3f74-479e-b20f-e433b5d6b87c`
- Pre-cutover damaged owner UUID: `2bfda5fc-3a2b-4dd4-a7a9-65e8432f7c03`
- Candidate UUID (source): `78010e56-041c-4fec-b8f7-0f9ca313d267`
- Archived rollback DB: `career_os_rollback_resume_20260711_043000`
- Backup/restore post-cutover: **passed**

#### Phase 4 open defects

| ID | Severity | Action |
|---|---|---|
| P4-HIGH-001 | High | **Resolved** — owner reconnected Google on canonical runtime; OAuth refresh/Gmail/Drive healthy, restart persistence verified |

### Phase 4 — final post-cutover validation

- Status: **COMPLETE — awaiting Codex final review**
- Evidence root: `artifacts/recovery/incident-20260709/phase4-final-20260711_194500/`
- Canonical database: `career_os` — OWNER `8651fd13-3f74-479e-b20f-e433b5d6b87c` (unambiguous)
- Owner reconnected Google via canonical app (web :3000 / API :8000)
- Canonical state: runtime user non-privileged, DDL denied, migrate user separate — **PASS**
- OAuth: `swapnilpatil.tech@gmail.com`, 3 active tokens decrypt/refresh, Gmail+Drive read, no archived-DB token copy, restart persistence — **PASS**
- Drive: root `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr`, six subfolders, no duplicate root, restart-preserved — **PASS**
- Gmail: 120 scanned, second sync idempotent, 0 duplicate jobs, 0 suppressors — **PASS**
- Fresh Jobs: **11 accepted, 0 OWNER_REVIEW** (corrected 13→11; jobs 139/175 domain-rejected); audit dry-run only (no `-Execute`) — **PASS**
- Owner workflow: all areas OK, validation-only records removed (0 remain) — **PASS**
- Backup: `pg_dump` exit 0, SHA256 `b67c156f...`, restore-verified into disposable DB (dropped), no fixture rows — **PASS**
- Automated: secret/prohibited/owner-stack/privileged scans PASS; SQLite 258 passed/23 skipped; Postgres integration 57 passed; Playwright 6 teardown-flake failures → targeted `--workers=1` rerun 6 passed; web build PASS; `git diff --check` PASS
- Defects: Critical 0 / High 0 / Medium 0 / Low-open 1 (P4-LOW-003 audit recompute delta, non-blocking)

#### Phase 4 final finding disposition

| ID | Severity | Disposition |
|---|---|---|
| P4-HIGH-001 | High | **Resolved** — owner reconnected Google; `oauth/PHASE-4-OAUTH-FINAL-VALIDATION.json` |
| P4-MED-001 | Medium | **Resolved** — eligibility engine title/domain/HTML fix + regression tests |
| P4-LOW-001 | Low | **Resolved** — privileged-helper PowerShell invocation fix |
| P4-LOW-002 | Low | **Resolved** — Playwright teardown flake (targeted rerun passed) |
| P4-LOW-003 | Low | **Open** — audit-tool recompute delta (12 vs 11); dry-run advisory only, non-blocking |

## Owner business row counts (post-final-validation canonical)

| Table | Count |
|---|---:|
| jobs | 175 |
| applications | 0 |
| oauth_tokens | 6 (active 3) |
| processed_gmail_messages | 241 |
| users | 1 |
| accepted (eligible) | 11 |

Archived damaged owner (`career_os_rollback_resume_20260711_043000`): marker `OWNER|2bfda5fc-3a2b-4dd4-a7a9-65e8432f7c03`, OAuth side-effect rows preserved; unchanged; non-authoritative.

## Validation database (unchanged — not modified)

| Table | Count |
|---|---:|
| jobs | 124 |
| applications | 3 |
| oauth_tokens | 9 |
| processed_gmail_messages | 59 |
| users | 2 |

## Next action

**Codex Phase 4 final review** — cutover performed and canonical `career_os` promoted (OWNER `8651fd13-3f74-479e-b20f-e433b5d6b87c`); owner reconnected Google and final post-cutover validation passed (see `artifacts/recovery/incident-20260709/phase4-final-20260711_194500/PHASE-4-FINAL-VALIDATION-REPORT.md`). Do not declare `COMPLETE` until Codex GO.
