# Recovery Orchestration State

## Current state

`PHASE_2_AWAITING_CODEX_REVIEW`

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
- Phase 2 rework evidence: `artifacts/recovery/incident-20260709/phase2-rework-20260709_225953/`

## Database identities

| Purpose | Compose project | Service | Host | Database | Runtime user | Migrate user | Volume |
|---|---|---|---|---|---|---|---|
| Owner | aarohan-careeros | postgres | 127.0.0.1:5432 | career_os | career_os_runtime | career_os_migrate | aarohan-careeros_postgres_data |
| Validation | aarohan-careeros | postgres | 127.0.0.1:5432 | career_os_validation | n/a (recovery source) | n/a | aarohan-careeros_postgres_data |
| E2E/Test | aarohan-careeros-test | postgres-e2e | 127.0.0.1:5433 | career_os_e2e | career_os_e2e_runtime | career_os_e2e_migrate | aarohan-careeros-test_postgres_e2e_data |
| Recovery staging | — | — | — | — | — | — | not created (Phase 3) |

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

### Phase 2 rework

- Status: **COMPLETE — awaiting Codex re-review**
- Evidence root: `artifacts/recovery/incident-20260709/phase2-rework-20260709_225953/`
- Provisioning guide: `docs/recovery/owner-db-incident-20260709/DATABASE-IDENTITY-PROVISIONING.md`

#### Codex finding disposition

| ID | Severity | Disposition |
|---|---|---|
| CODEX-P2-HIGH-001 | High | **Resolved** — owner API uses `career_os_runtime` (no superuser/DDL); migrate role `career_os_migrate` used only for Alembic; idempotent `provision_database_roles.py` + provisioning scripts |
| CODEX-P2-HIGH-002 | High | **Resolved** — `get_engine()` validates URL + immutable marker before serving; Alembic `env.py` validates when marker present; startup lifespan calls `get_engine()` |
| CODEX-P2-HIGH-003 | High | **Resolved** — `Invoke-VerifiedOwnerBackup.ps1` performs pg_dump, checksum, header check, disposable restore verification, manifest; cleanup execute path requires verified manifest |
| CODEX-P2-MEDIUM-001 | Medium | **Resolved** — UUID bound to `aarohan_meta.database_identity` with immutability trigger; runtime role cannot UPDATE/DELETE marker |
| CODEX-P2-MEDIUM-002 | Medium | **Resolved** — CI generates per-run UUID, provisions roles/marker, asserts CI purpose; Playwright uses CI runtime role and `ALLOW_E2E_LOGIN_ON_OWNER=false` |

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
| oauth_tokens | 9 |
| processed_gmail_messages | 59 |

## Next action

**Codex Phase 2 re-review** — do not start Phase 3 until Codex GO.
