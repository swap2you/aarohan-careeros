# Owner Candidate Cutover Plan

**Updated:** 2026-07-11 (OAuth side-effect disposition recorded)  
**Gate:** `GATE_2_OWNER_CUTOVER_APPROVAL_REQUIRED`  
**Candidate identity UUID:** `78010e56-041c-4fec-b8f7-0f9ca313d267`

## Preconditions

1. Codex Phase 3 final rereview **GO** (M1 disposition closed — see `OWNER-PHASE-3-CONDITIONAL-GO-DISPOSITION.md`)
2. Owner Gate 2 phrase: `APPROVE OWNER CANDIDATE CUTOVER`
3. Verified backup of damaged canonical `career_os` (**must include all OAuth rows** as captured)
4. Verified backup of `career_os_owner_candidate` (SHA256 recorded)
5. Candidate validation passed with zero Critical/High defects
6. OAuth refresh, Gmail read, and Drive root resolved on **candidate** runtime only
7. Owner API stopped before database transition

## Pre-cutover backup of damaged owner database

The pre-cutover `pg_dump` of `career_os` **must capture the full database state**, including:

- All OAuth token rows (documented side-effect triple from 2026-07-10T22:06:38Z and any superseded copies)
- All business tables at their pre-cutover counts
- Identity marker `OWNER` with current UUID

Record SHA256, row counts, and `oauth_tokens` count in the cutover manifest. Do not strip or exclude OAuth rows from the backup.

## Guarded promotion procedure

1. Record before-manifest (row counts, identity UUIDs, OAuth counts for both databases)
2. Stop owner API (`docker compose` project `aarohan-careeros`)
3. `pg_dump` canonical `career_os` → timestamped backup (includes OAuth side-effect rows)
4. `pg_dump` `career_os_owner_candidate` → timestamped backup
5. Rename `career_os` → `career_os_rollback_<timestamp>` (**archive damaged owner; OAuth rows preserved**)
6. Rename `career_os_owner_candidate` → `career_os`
7. Provision new immutable `OWNER` identity UUID (never reuse candidate UUID)
8. Rebind `career_os_runtime` / `career_os_migrate` roles via `provision_database_roles.py --stack owner`
9. Start owner API; verify health, login, Fresh Jobs, applications
10. Record after-manifest; retain archived rollback database until owner confirms

## OAuth authority at cutover

| Source | Role at cutover |
|---|---|
| Promoted candidate (`career_os_owner_candidate` → `career_os`) | **Authoritative operational OAuth** (3 validated rows for `swapnilpatil.tech@gmail.com`) |
| Archived damaged owner (`career_os_rollback_<timestamp>`) | **Non-authoritative** — rollback/audit evidence only |
| `phase3_final_sync_oauth_to_candidate.py` | **Must not run again** — no re-merge from archived canonical OAuth |

After cutover, the owner API binds OAuth from the promoted database only. Archived canonical OAuth rows are never copied forward.

## Identity transition

- **Before:** `OWNER_CANDIDATE` UUID `78010e56-041c-4fec-b8f7-0f9ca313d267`
- **After:** new `OWNER` UUID (provisioned at cutover via guarded `promote_database_identity_marker.py`)

Rehearsal evidence: `artifacts/recovery/incident-20260709/phase3-final-20260710_221530/reports/CUTOVER-FINAL-REHEARSAL-MANIFEST.json`

## Not in scope

- No modification of `career_os_validation`
- No deletion of OAuth records in archived rollback database
- No automatic external email or application submission
- No Cowork / RC4
