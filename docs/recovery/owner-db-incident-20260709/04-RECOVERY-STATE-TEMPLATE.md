# Recovery Orchestration State

## Current state

`NOT_STARTED`

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

- Branch:
- Start SHA:
- Current SHA:
- Working tree:

## Database identities

| Purpose | Compose project | Service | Host | Database | User | Volume | Identity |
|---|---|---|---|---|---|---|---|
| Owner | | | | | | | |
| E2E | | | | | | | |
| Recovery staging | | | | | | | |
| Owner candidate | | | | | | | |

## Verified backups

| Database | Dump | Size | SHA-256 | Restore verified |
|---|---|---:|---|---|

## Phase evidence

### Phase 1

- Status:
- Evidence:
- Codex review:
- Findings disposition:

### Phase 2

- Status:
- Evidence:
- Codex review:
- Findings disposition:

### Phase 3

- Status:
- Recovery manifest:
- Candidate validation:
- Cutover approval:

### Final

- Backup/restore:
- Workflow Lock 01:
- Codex final verdict:
- Cowork UAT:

## Open risks

| ID | Severity | Risk | Owner | Resolution |
|---|---|---|---|---|
