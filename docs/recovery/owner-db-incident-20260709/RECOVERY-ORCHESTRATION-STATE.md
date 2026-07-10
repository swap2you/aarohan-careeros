# Recovery Orchestration State

## Current state

`GATE_2_OWNER_CUTOVER_APPROVAL_REQUIRED`

Allowed values:

- NOT_STARTED
- PHASE_1_RUNNING
- PHASE_1_AWAITING_CODEX_REVIEW
- PHASE_1_REWORK
- PHASE_2_RUNNING
- PHASE_2_AWAITING_CODEX_REVIEW
- PHASE_2_REWORK
- PHASE_3_RUNNING
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

## Database identities

| Purpose | Compose project | Service | Host | Database | Runtime user | Migrate user | Volume |
|---|---|---|---|---|---|---|---|
| Owner | aarohan-careeros | postgres | 127.0.0.1:5432 | career_os | career_os_runtime | career_os_migrate | aarohan-careeros_postgres_data |
| Validation | aarohan-careeros | postgres | 127.0.0.1:5432 | career_os_validation | n/a (recovery source) | n/a | aarohan-careeros_postgres_data |
| Recovery staging | aarohan-careeros | postgres | 127.0.0.1:5432 | career_os_recovery | career_os_recovery_runtime | career_os_recovery_migrate | aarohan-careeros_postgres_data |
| Owner candidate | aarohan-careeros | postgres | 127.0.0.1:5432 | career_os_owner_candidate | career_os_candidate_runtime | career_os_candidate_migrate | aarohan-careeros_postgres_data |
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

### Phase 3 — owner candidate

- Status: **COMPLETE — Gate 2 owner approval required**
- Evidence root: `artifacts/recovery/incident-20260709/phase3-20260710_154015/`
- Source backup: `artifacts/recovery/incident-20260709/20260709_172617/dumps/career_os_validation.sql` (sha256 `d44d2c57357f52ba296283601a6a2ab45b1ccd9ad68f95d8833b95fe3d7eddac`)
- Recovery identity UUID: `aecb0652-98a8-4fb8-ac20-cad8724fcbb9`
- Candidate identity UUID: `78010e56-041c-4fec-b8f7-0f9ca313d267`
- Schema upgrade (recovery): `0009_r28_interview_intel` → `0013_database_identity_meta`
- Candidate validation: **passed** (backup restore verified)
- Cutover: **NOT PERFORMED**

## Owner business row counts (unchanged)

| Table | Count |
|---|---:|
| jobs | 75 |
| applications | 2 |
| oauth_tokens | 0 |
| processed_gmail_messages | 0 |
| users | 2 |

## Validation database (unchanged — not modified)

| Table | Count |
|---|---:|
| jobs | 124 |
| applications | 3 |
| oauth_tokens | 9 |
| processed_gmail_messages | 59 |
| users | 2 |

## Next action

**Owner Gate 2 review** — review `OWNER-CANDIDATE-VALIDATION-REPORT.md`, `AMBIGUOUS-ROWS-REPORT.md`, and `JOB-RECONSTRUCTION-REPORT.json`. Issue `APPROVE OWNER CANDIDATE CUTOVER` only after explicit approval. Do not start Phase 4 or Cowork UAT until cutover is approved.
