# Owner Candidate Rollback Plan

**Updated:** 2026-07-11 (OAuth side-effect disposition recorded)  
**Gate:** `GATE_2_OWNER_CUTOVER_APPROVAL_REQUIRED`

## Trigger

Any post-cutover failure in login, OAuth, Drive, Fresh Jobs, or application integrity within the rollback window.

## Archived damaged owner database

At cutover, the pre-cutover damaged `career_os` is renamed to:

`career_os_rollback_<timestamp>`

This archive **must retain all OAuth rows exactly as captured** in the verified pre-cutover backup, including:

- Documented side-effect triple from 2026-07-10T22:06:38Z (ids 1–3)
- Any superseded or additional canonical OAuth rows present at backup time

The archived database is **not** the authoritative OAuth source after successful cutover. It exists for rollback and audit only.

## Rollback procedure

1. Stop owner API
2. Rename current promoted `career_os` → `career_os_failed_promotion_<timestamp>`
3. Rename `career_os_rollback_<timestamp>` → `career_os`
4. Restore original `OWNER` identity marker from before-cutover manifest
5. Reprovision runtime/migrate roles for restored database
6. Start owner API; verify health and row counts match before-cutover manifest (including `oauth_tokens` count)
7. Retain failed promotion database for forensics only

## OAuth interpretation on rollback

| Database | OAuth role after rollback |
|---|---|
| Restored `career_os` (from archive) | Returns to pre-cutover damaged state; OAuth rows are **non-authoritative for fresh operations** until owner reconnects on canonical runtime |
| Failed promotion DB | Forensics only — contains promoted candidate OAuth; do not bind owner API to this DB |

On rollback:

- Do **not** delete OAuth rows from the restored archive
- Do **not** merge archived canonical OAuth into candidate
- Do **not** re-run `phase3_final_sync_oauth_to_candidate.py`

## Restore fidelity requirement

Rollback restores the damaged owner database **exactly as captured** in the verified pre-cutover backup. No row-level OAuth cleanup is permitted during rollback.

## Rehearsal evidence

Disposable clone rehearsal: `artifacts/recovery/incident-20260709/phase3-final-20260710_221530/reports/CUTOVER-FINAL-REHEARSAL-MANIFEST.json`

Final rehearsal validated rename, identity promotion, and rollback mechanics without modifying live canonical or candidate databases.

## Related disposition

See `OWNER-PHASE-3-CONDITIONAL-GO-DISPOSITION.md` for owner acceptance of canonical OAuth side-effect rows and duplicate-prevention rules.
