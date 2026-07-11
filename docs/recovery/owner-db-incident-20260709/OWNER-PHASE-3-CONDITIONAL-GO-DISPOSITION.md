# Owner Phase 3 Conditional GO — OAuth Side-Effect Disposition

**Status:** CLOSED (owner decision recorded)  
**Recorded:** 2026-07-11  
**Gate state:** `GATE_2_OWNER_CUTOVER_APPROVAL_REQUIRED` (cutover not performed)  
**Codex finding:** M1 in `reviews/CODEX-PHASE-3-FINAL-REREVIEW.md`

## Owner decision (exact)

The owner accepts the **three OAuth token rows** written to the damaged pre-cutover canonical database `career_os` when Google reconnect initially hit the canonical runtime (`http://127.0.0.1:8000`) instead of the isolated candidate runtime (`http://127.0.0.1:8002`).

These rows are a **documented post-incident side effect**. They must **not** be deleted, modified, or re-synced into the candidate.

## Side-effect reconnect timestamp

| Field | Value |
|---|---|
| Event | `oauth.connected` |
| Actor | `swapnilpatil.tech@gmail.com` |
| Timestamp (UTC) | **2026-07-10T22:06:38.128471** |
| Token `connected_at` (UTC) | **2026-07-10T22:06:38.093009** – **2026-07-10T22:06:38.121735** |
| Side-effect row IDs | `1` (google), `2` (gmail), `3` (drive) |
| Evidence | `artifacts/recovery/incident-20260709/phase3-final-20260710_221530/reports/OAUTH-CANDIDATE-SYNC-FROM-OWNER.json` |

## OAuth counts

### Damaged canonical `career_os`

| Point in time | `oauth_tokens` count | Notes |
|---|---:|---|
| Before side-effect reconnect | **0** | Documented in orchestration state pre-remediation |
| Immediately after side-effect reconnect | **3** | Rows 1–3 for `swapnilpatil.tech@gmail.com` |
| At disposition closure (read-only, 2026-07-11) | **9 total** (3 active, 6 inactive superseded) | Side-effect triple (ids 1–3) **preserved**; additional canonical-runtime reconnect cycles on 2026-07-11 added rows 4–9. No remediation mutation. |

The disposition scope is the **documented side-effect triple** (ids 1–3). All OAuth rows in `career_os` remain preserved per the no-deletion policy.

### Authoritative candidate `career_os_owner_candidate`

| Point in time | `oauth_tokens` count | Notes |
|---|---:|---|
| After Phase 3 final validation | **3** active | Rows 10–12; validated in `OAUTH-CANDIDATE-FINAL-VALIDATION.json` |
| At disposition closure (read-only, 2026-07-11) | **3** active | One row each for `google`, `gmail`, `drive`; account `swapnilpatil.tech@gmail.com` |

## Why deletion was rejected

1. **Audit integrity** — Removing rows would destroy evidence of the misrouted reconnect and complicate incident reconstruction.
2. **Rollback fidelity** — Pre-cutover backup and archived rollback database must reflect the damaged owner state exactly as captured.
3. **Owner explicit instruction** — Owner disposition accepts the side effect; deletion is out of scope.
4. **No candidate safety impact** — Candidate OAuth is independently validated and operational; canonical side-effect rows do not block cutover readiness.

## Authoritative OAuth source

| Phase | Authoritative database | Authoritative OAuth rows |
|---|---|---|
| **Before cutover** | `career_os_owner_candidate` | 3 validated rows for `swapnilpatil.tech@gmail.com` (refresh/Gmail/Drive healthy) |
| **After successful cutover** | `career_os` (promoted from candidate) | Same 3 operational rows carried forward with candidate promotion — **not** merged from damaged canonical OAuth |
| **Non-authoritative after cutover** | `career_os_rollback_<timestamp>` (archived damaged owner) | All OAuth rows in archived DB, including side-effect triple — **rollback/audit evidence only** |

The damaged canonical OAuth rows (including ids 1–3 and any superseded copies) are **never** the post-cutover operational OAuth source.

## Rollback interpretation

If rollback is required after cutover:

1. Stop owner API.
2. Restore the archived damaged owner database from `career_os_rollback_<timestamp>` **exactly as captured** in the verified pre-cutover backup (including all OAuth rows present at backup time).
3. OAuth in the restored damaged database is **non-authoritative** for live operations until owner reconnects on the restored canonical runtime.
4. Do **not** copy archived canonical OAuth into a future candidate rebuild without explicit owner approval.

## Duplicate-prevention expectations

| Rule | Requirement |
|---|---|
| No re-sync into candidate | `phase3_final_sync_oauth_to_candidate.py` is a one-time Phase 3 remediation step; **must not run again** before or after cutover |
| No merge at cutover | Cutover promotes candidate DB rename only; damaged canonical OAuth is archived, not merged |
| Single active triple per account | Post-cutover operational DB must have exactly one active `(provider, service, account_email)` triple for Google |
| Archived DB isolation | Archived `career_os_rollback_*` databases are forensics/rollback only; owner API must not bind to them after successful cutover |

## Confirmation: no remediation business-data writes to `career_os`

Phase 3 final remediation scripts targeted `career_os_owner_candidate` only. The OAuth side effect originated from **owner Google reconnect on the canonical runtime**, not from remediation script DML on business tables.

Read-only operations during remediation:

- `phase3_final_sync_oauth_to_candidate.py` — read from `career_os`, write to candidate only (one-time)

`career_os_validation` was not modified during remediation (verified unchanged counts).

## Verification snapshot (read-only, 2026-07-11)

| Check | Result |
|---|---|
| Side-effect triple (ids 1–3) preserved in `career_os` | **PASS** |
| Candidate has 3 active validated OAuth rows | **PASS** |
| Candidate `(provider, service, account_email)` uniqueness | **PASS** (1 each: google/gmail/drive) |
| No duplicate reconnect required on candidate | **PASS** |
| `career_os_validation` unchanged | **PASS** (jobs=124, oauth=9, processed_gmail=59) |
| Database rows modified during this disposition closure | **NONE** (documentation only) |

## Related documents

- `RECOVERY-ORCHESTRATION-STATE.md`
- `OWNER-CANDIDATE-CUTOVER-PLAN.md`
- `OWNER-CANDIDATE-ROLLBACK-PLAN.md`
- `reviews/CODEX-PHASE-3-FINAL-REREVIEW.md`
- Evidence: `artifacts/recovery/incident-20260709/phase3-final-20260710_221530/reports/`

## Next action

**Codex closure review** — confirm M1 disposition is recorded; proceed to owner Gate 2 only after Codex accepts closure and owner phrase `APPROVE OWNER CANDIDATE CUTOVER`.
