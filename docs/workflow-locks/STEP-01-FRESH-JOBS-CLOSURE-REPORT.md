# Workflow Lock 01 — Fresh Jobs Closure Report

**Status:** `READY_FOR_OWNER_VALIDATION` (not LOCKED)
**Date:** 2026-07-12
**Branch:** `main`
**Scope:** Backend parity + eligibility/lifecycle semantics. UI/UX/CSS unchanged. No Workflow Lock 02. No RC4.
**Local evidence root:** `artifacts/workflow-locks/step-01-20260712_021300/`

This report closes the two Low advisories carried out of the Phase 4 recovery
(`CODEX-PHASE-4-FINAL-REVIEW.md`): the audit/production accepted-count mismatch
(P4-LOW-003, 12 vs 11) and stale `state=REJECTED` values on owner-eligible jobs
(P4-LOW-004). Recovery itself is `COMPLETE` (Codex GO); this task prepares Fresh Jobs
for owner/Cowork UAT.

---

## 1. Field semantics — single documented source of truth

| Field | Meaning | Source of truth for |
|---|---|---|
| `eligible_for_owner` (bool) | Canonical owner eligibility gate | **Owner visibility** |
| `ingest_decision` (`ACCEPT`/`REJECT`/`OWNER_REVIEW`/`HISTORICAL`/`DUPLICATE`) | Eligibility-engine classification (+ dedupe/manual override) | **Owner visibility** |
| `JobScore.recommendation`, `JobScore.hard_filter_passed`, scores | Fit/trust ranking | **Ranking / review only** |
| `state` (`WorkflowState`) | Application **lifecycle** (INGESTED→NORMALIZED→SHORTLISTED→PACKET_*→SUBMITTED…; terminal REJECTED/CLOSED) | **Workflow lifecycle only** |
| `freshness_tier` / `effective_freshness_at` | Freshness classification (TODAY/FRESH/RECENT/HISTORICAL) | Freshness window |

**Rule:** owner visibility = `eligible_for_owner = true` AND `ingest_decision = ACCEPT`
AND not archived/expired AND fresh (or a protected lifecycle state). Fit/trust and the
lifecycle `state` field are **not** eligibility inputs. Salary is ranking/review, never a
hard rejection.

---

## 2. Audit ↔ production eligibility parity (P4-LOW-003)

**Root cause of 12 vs 11:** the Fresh Jobs audit recompute called the stateless
single-row `evaluate_eligibility()` per job. Job **31** (`Blockstream — "Remote QA
Engineering Manager for Blockchain & FinTech"`) is a **syndicated near-duplicate** of the
accepted job **24** (`Blockstream — "QA Engineering Manager"`). Production had persisted
job 31 as `ingest_decision=REJECT` with reason `DUPLICATE_SYNDICATED` (a cross-row dedupe
result the single-row engine cannot re-derive), so the audit re-accepted it → 12, while
the canonical owner-eligible count was 11.

**Fix — one canonical decision model:** `evaluate_owner_decision()` =
`evaluate_eligibility()` + `reconcile_persisted_disposition()`. The reconciliation folds a
persisted duplicate/override disposition (`DUPLICATE_*` reason codes or a persisted
`DUPLICATE` decision) back to `DUPLICATE`. The audit (`audit_fresh_jobs.py`) now uses this
model for its decision counts and proposals, and reports an explicit parity block.

**Result (fixed evaluation timestamp `2026-07-12T00:13:56`):**

| Metric | Value |
|---|---:|
| Canonical owner-eligible (`eligible_for_owner=true`) | **11** |
| Audit recompute `ACCEPT` | **11** |
| Audit `proposed_fresh_jobs` | **11** |
| Production `/api/jobs` (live) | **11** |
| `parity_ok` / `parity_delta` | `true` / `0` |
| Job 31 canonical decision | `DUPLICATE` (correctly excluded) |

Regression test `test_audit_recompute_matches_canonical_eligible_with_syndicated_duplicate`
reproduces the prior 12-vs-11 discrepancy and asserts parity.

---

## 3. Stale `state=REJECTED` on eligible jobs (P4-LOW-004)

**Root cause:** `score_job()` (fit) and `trust_matching.apply_analysis_to_models()`
(hard-filter) wrote a fit/trust recommendation into the lifecycle `state` field
(`REJECTED`/`SECONDARY_REVIEW`/`SHORTLISTED`) on every ingest and rescore. The Fresh Jobs
read path then hid `state IN (REJECTED, CLOSED)`, so **10 of 11** owner-eligible jobs
(low fit score, `eligible_for_owner=true`, `ingest_decision=ACCEPT`) were hidden. Live
`/api/jobs` returned only 1 (job 34, `SHORTLISTED`, protected).

**Fix (code):**
1. `scoring.py` / `trust_matching.py` no longer mutate `job.state`. Fit/trust
   recommendation is recorded only on `JobScore` (`recommendation`, `hard_filter_passed`).
2. `routers/jobs.py` Fresh Jobs default filter no longer excludes by `state`; visibility is
   gated by `eligible_for_owner` + `ingest_decision=ACCEPT` + not archived/expired +
   freshness. Genuine eligibility rejections already set `eligible_for_owner=false`.
3. Re-accept paths (`phase3_final_manual_job_review.py`, audit `--execute`) advance a stale
   terminal `state` to `NORMALIZED`.

**Effect:** live `/api/jobs` now returns all 11 owner-eligible jobs. `No rejected job
becomes eligible` — eligibility is unchanged; only the read path and lifecycle-writing
behavior changed. Regression tests: `test_fresh_jobs_visibility.py` (eligible + stale
`REJECTED` is visible; ineligible stays hidden).

**Residual data:** 10 eligible rows still store `state=REJECTED` (legacy value). They are
now correctly **visible**, but the stored lifecycle value is reconciled by the gated
Step-4 operation below so the stored field matches eligibility.

---

## 4. Bounded eligibility-state reconciliation (GATED — awaiting owner phrase)

A deterministic, bounded repair is **prepared but not executed**. It aligns the stored
lifecycle `state` with canonical eligibility for the affected rows. It does **not** change
eligibility and does **not** delete or archive any job.

- **Targets:** 10 rows — ids `19, 21, 23, 24, 26, 28, 30, 32, 136, 138`
  (`eligible_for_owner=true` AND `ingest_decision=ACCEPT` AND `state=REJECTED`,
  not protected). Job 34 (`SHORTLISTED`) and duplicate job 31 are excluded.
- **Change:** `state: REJECTED → NORMALIZED` (one transaction, count/decision validated,
  rollback on any unexpected result).
- **Dry-run manifest:** `WORKFLOW-01-STATE-RECONCILIATION.json`.
- **Same-run verified canonical backup:** `backup/BACKUP-MANIFEST.json`
  (SHA256 `0a139119172d810a6b3a771846127553547e74ab217f4b919a23e4917168f273`,
  restore-verified, OWNER identity confirmed, disposable verify DB dropped).
- **Runner:** `apps/api/scripts/workflow01_state_reconcile.py`.
- **Confirmation phrase required:** `APPROVE WORKFLOW 01 ELIGIBILITY STATE RECONCILIATION`.

To apply (owner-approved only):

```powershell
docker exec aarohan-careeros-api-1 python scripts/workflow01_state_reconcile.py \
  --execute --confirmation-text "APPROVE WORKFLOW 01 ELIGIBILITY STATE RECONCILIATION"
```

The functional defect (hidden eligible jobs) is already resolved in code; this reconciliation
is data hygiene so the stored lifecycle field matches the canonical eligibility decision.

---

## 5. Final accepted jobs (11)

| ID | Title | Company |
|---:|---|---|
| 19 | Remote Senior Manager, ACAS Quality Engineering | CVS Health Corporation |
| 21 | Senior Manager, Quality Engineering (Intelligent Automation) | 07 CMG Strategy Co., LLC |
| 23 | Principal Quality Engineer | Virtual Vocations Inc |
| 24 | QA Engineering Manager | Blockstream |
| 26 | QA Engineering Manager | Finite State |
| 28 | Quality Assurance Engineering Manager | BCC Software |
| 30 | Quality Engineering Manager | Business Centric Technology |
| 32 | Sr. Manager, Quality Engineering — Global Employer Services Technology Center | Deloitte LLP |
| 34 | (SHORTLISTED) Quality Engineering leadership | — |
| 136 | Senior Manager, Quality Engineering | CFA Institute |
| 138 | Senior Manager, Quality Engineering | Subway |

All are software/digital QE-management/leadership roles with FRESH/RECENT/TODAY freshness
and traceable Jooble URLs. No non-software quality, foreign-only, malformed digest,
GitLab-flood, or syndicated-duplicate rows are accepted.

---

## 6. Backend validation

| Check | Result |
|---|---|
| Secret scan | PASS |
| Prohibited-source scan | PASS |
| Owner-stack pytest scan | PASS |
| Privileged-helper scan | PASS |
| SQLite unit tests | **265 passed, 23 skipped** |
| Isolated Postgres integration (`career_os_e2e` :5433) | **57 passed** |
| Playwright (isolated E2E :3001/:8001) | 19 passed; 4 teardown-flake failures → single-worker rerun **10 passed** |
| Web production build | PASS |
| `git diff --check` | PASS |
| Audit dry-run parity | `parity_ok=true` (11 == 11) |
| pytest against owner `career_os` | Not run (prohibited) |

No non-software false positives, no syndicated-duplicate accepted jobs, no malformed digest
or foreign-only accepted jobs, no GitLab flood; manual opportunities preserved; salary
remains ranking/review.

---

## 7. Defects by severity

- Critical: 0
- High: 0
- Medium: 0
- Low: 1 open — stored lifecycle `state` cleanup for 10 eligible rows is a prepared, gated
  reconciliation awaiting the owner phrase (functional visibility already fixed in code).

---

## 8. Status

Workflow Lock 01 remains **`READY_FOR_OWNER_VALIDATION`** (not LOCKED). Owner/Cowork UAT
starts at Fresh Jobs (`http://127.0.0.1:3000/jobs`), where all 11 owner-eligible roles are
now visible. Optionally apply the gated state reconciliation with the confirmation phrase.
