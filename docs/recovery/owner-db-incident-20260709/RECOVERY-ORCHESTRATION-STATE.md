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

- Status: **COMPLETE — awaiting Codex final rereview**
- Evidence root: `artifacts/recovery/incident-20260709/phase3-final-20260710_221530/`
- Prior rework evidence: `artifacts/recovery/incident-20260709/phase3-rework-20260710_171518/`
- Codex review: `docs/recovery/owner-db-incident-20260709/reviews/CODEX-PHASE-3-REREVIEW.md` — prior **NO GO**
- Phase 3 final SHA: 87b9944
- Validation passed: **true** (0 defects)
- Cutover rehearsal: **passed** (OWNER marker promotion on disposable DB)
- Backup restore verification: **passed**

#### Phase 3 final disposition

| Area | Result |
|---|---|
| OAuth on candidate | Passed — swapnilpatil.tech@gmail.com, refresh/Gmail/Drive healthy, restart persistence verified |
| OAuth note | Owner reconnect initially landed on `career_os`; remediated via read-only sync to candidate |
| Drive root | Bound `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr`, subfolders complete |
| Gmail replay | 156 scanned, 72 replayed, 0 suppressors |
| Manual job review | 9 accepted, 1 supplier/nuclear false positive rejected, 1 Blockstream duplicate removed |
| Cutover rehearsal | Full OWNER identity promotion rehearsed on disposable clones |
| Backup/restore | Passed with schema + row-count verification |

#### Remaining owner-action blockers (pre-cutover)

| ID | Severity | Action |
|---|---|---|
| *(none — technical blockers cleared)* | | Codex Phase 3 final rereview + owner Gate 2 approval phrase |

## Owner business row counts (unchanged schema; oauth side effect from reconnect)

| Table | Count |
|---|---:|
| jobs | 75 |
| applications | 2 |
| oauth_tokens | 3 |
| processed_gmail_messages | 0 |
| users | 2 |

Note: `career_os` gained 3 OAuth rows when owner reconnect initially hit canonical runtime (2026-07-10); remediation scripts did not write business data to `career_os`. `career_os_validation` unchanged.

## Validation database (unchanged — not modified)

| Table | Count |
|---|---:|
| jobs | 124 |
| applications | 3 |
| oauth_tokens | 9 |
| processed_gmail_messages | 59 |
| users | 2 |

## Next action

**Codex Phase 3 final rereview** — candidate validation passed with zero High/Critical defects. Do not cut over until Codex GO and owner Gate 2 phrase `APPROVE OWNER CANDIDATE CUTOVER`.
