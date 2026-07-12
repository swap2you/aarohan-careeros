# Workflow 01.5 — Discovery Control Center and Source Coverage

**State:** `WORKFLOW_01_5_READY_FOR_OWNER_UAT`
**Recovery:** `COMPLETE` (unchanged). **Workflow Lock 01:** provisionally complete, **NOT LOCKED** (unchanged).
**Scope:** discovery transparency, Gmail coverage, provider coverage, configurable criteria, and manual-opportunity visibility. **No** UI redesign, **no** document-engine work, **no** LinkedIn/Indeed scraping, **no** CAPTCHA/Cloudflare bypass, **no** application submission.

This phase makes discovery **observable and configurable** by the owner without changing the visual style or navigation structure, and preserves/distinguishes manually added opportunities.

---

## 1. Deferred UAT backlog
Recorded in `docs/workflow-locks/STEP-01-DEFERRED-UAT-BACKLOG.md` — functional vs. flaky/test-infrastructure kept strictly separate; development proceeds because no finding invalidates the Lock 01 guarantees.

## 2. Discovery source inventory
`app/services/discovery_source_inventory.py` → `build_source_inventory(db)` reports, per source, policy-enabled / technically-configured / credentials-present / OAuth health / last attempted & successful run / decision counts / parser & provider failures / exact skip reason, across three classes:
- **Email alert sources** (LinkedIn, Indeed, Dice, USAJOBS, Glassdoor): marked `connector_kind = not_a_public_feed_connector`, orchestrated via Gmail discovery — never silently skipped.
- **Public/API sources** (Adzuna, Jooble, USAJOBS, Remotive, Remote OK, RSS).
- **ATS sources** (Greenhouse, Lever, Ashby): enabled but require explicit approved boards; report `approved_boards_count` and exact boards. Default is empty → `enabled_no_approved_boards` (no random boards added).

Evidence: `DISCOVERY-SOURCE-INVENTORY.json` (live: 2 email alerts enabled, 6 public ready, 0 ATS boards).

## 3. Gmail alert coverage audit
`app/scripts/gmail_alert_coverage_audit.py` — **read-only**, never mutates processed state, emits **redacted** message-id prefixes and subject classifications only (no bodies/tokens).
Live result (`GMAIL-ALERT-COVERAGE-AUDIT.json`): 241 processed messages (COMPLETE 95, FAILED 94, REPLAY_REQUIRED 22, LEGACY 30); by type JOB_ALERT 60, QUARANTINE 94, APPLICATION_CONFIRMATION 27, INTERVIEW 22, RECRUITER_OUTREACH 6, REJECTION 2; 189 with job output, 116 replay_required; 2 gmail-provenance jobs, **0 with a persisted `gmail_message_id` linkage** (see defect W015-004). Live sender search returns 0 new because the fetch path skips already-processed messages (limitation W015-L1).

## 4. Unified discovery orchestration
`app/services/discovery_orchestration.py` → `run_all_discovery(db, actor)` runs, in sequence: Gmail alert discovery/replay → public/API providers → approved ATS boards → (normalization/dedup/eligibility/persistence inside each connector) → source-result summary. Returns per-stage `attempted/skipped/fetched/parsed/accepted/owner_review/quarantined/rejected/duplicate/errors` and reason distributions. The legacy "Ingest Public Feed" path remains internally supported (`discover_fresh_jobs`, public+ATS only); the UI never implies public discovery includes Gmail. Labels: **Run All Discovery**, **Sync Gmail Alerts**, **Run Public Sources**, **Review Source Status**.

## 5. Discovery Control Center (Settings → Job Discovery)
`apps/web/src/app/settings/job-discovery/page.tsx`, added to nav under **Records → Job Discovery**, reusing the existing global CSS design system (`.card`, `.data-table`, bare form elements, `.status`/`.muted`) — no redesign. Shows: (A) active policy summary; (B) editable owner settings (freshness 3/7/14/30, visible tiers, primary role-family toggles, secondary inclusion, title include/exclude phrases, domain exclusions, US-remote & remote-unspecified policy, local/hybrid locations, salary target/strong bands, provider & Gmail-source enable/disable, OWNER_REVIEW sensitivity); (C) presets Strict / Balanced (default) / Broad; (D) preview with before/after deltas and examples; (E) governance (version, changed by/at, activate, restore defaults, history).

## 6. Policy storage architecture
- `config/job-discovery-policy.yml` remains **immutable application defaults**.
- `discovery_policy_versions` (PostgreSQL) stores versioned owner overrides as **validated data** (whitelisted keys; no arbitrary/executable expressions).
- **Effective policy = defaults + active owner override** (`app/services/discovery_policy.py` deep-merge). Single active version; drafts/archived retained for history, audit, and rollback. Cache invalidated on activate/restore; hot path stays DB-free via an in-memory active override refreshed at startup and on activation.
- Safety invariants enforced regardless of preset/input: `geography.foreign_only` and `relocation_required` stay `reject`; default `role_reject_patterns` / `domain_reject_patterns` are always preserved (owner input can only add exclusions); fixture/test rows stay owner-excluded. **Broad is wider, never unfiltered.**
- API: `GET /discovery/policy/effective|defaults|versions|active`, `POST /discovery/policy/preview|draft|{id}/activate|restore-defaults`, `GET /discovery/presets`.

## 7. Discovery diagnostics UI
Job Discovery page + `GET /discovery/sources`, `/discovery/runs?limit=20`, `/discovery/runs/{id}`, `/discovery/diagnostics` show source health, last run/success, fetched & decision counts, error/skip reasons, configuration status, Gmail parser coverage, and the last 20 runs (inspectable for reason distributions). No secrets/tokens displayed.

## 8. Manual opportunity visibility
Canonical `jobs.origin` (`OWNER_ADDED`/`GMAIL_ALERT`/`PUBLIC_CONNECTOR`/`ATS_BOARD`/`RECRUITER_MESSAGE`) + `added_by/added_at/owner_confirmed/manual_protected/manual_status`. Owner-added records show an "Added manually" badge, are protected from automated age-out, are listed via `GET /discovery/opportunities`, support manual status tracking (SAVED→…→CLOSED), and support already-applied jobs — without fabricating application history. See `MANUAL-OPPORTUNITY-MODEL.json`. UI recommendation: Fresh Jobs (eligible), My Opportunities (owner-added/tracked), Applications (with a record).

## 9. Source & policy explainability
`app/services/discovery_explain.py` → `build_job_explanation(db, job)` exposes origin, provider, redacted source message, policy version, decision, reason codes, freshness source + `timestamp_confidence`, location decision, role-profile match, and duplicate disposition. Job detail renders a **"Why am I seeing this?"** panel; excluded records are discoverable in diagnostics without appearing in Fresh Jobs.

## 10. Testing
New: `test_discovery_policy_service.py`, `test_discovery_origin.py`, `test_discovery_inventory.py` (effective-policy merge, validation, versioning, preview, cache invalidation, presets, Broad-not-unfiltered, Gmail separation, ATS empty-board, provider status, origin classification, manual persistence, protected-manual age-out). Existing eligibility/visibility regression suites unchanged and green. Full isolated suite (SQLite + Postgres + Playwright + scans + web build) — see closure report §Testing.

## 11. Evidence & stop condition
Local evidence (`artifacts/workflow-locks/step-01-5-20260712/`): `DISCOVERY-SOURCE-INVENTORY.json`, `GMAIL-ALERT-COVERAGE-AUDIT.json`, `DISCOVERY-POLICY-DEFAULTS.json`, `DISCOVERY-POLICY-EFFECTIVE.json`, `DISCOVERY-PRESET-PREVIEW.json`, `DISCOVERY-RUN-EVIDENCE.json`, `MANUAL-OPPORTUNITY-MODEL.json`, `DISCOVERY-DEFECT-REGISTER.md`. Workflow Lock 01 remains **NOT LOCKED**. Final state: **`WORKFLOW_01_5_READY_FOR_OWNER_UAT`**.

### Migration / deployment note
Additive migration `0015_discovery_control_center` (new `discovery_policy_versions` table + `jobs` origin/manual columns + deterministic origin backfill) was applied to canonical `career_os` via the superuser migrate path (tables are owned by `career_os_candidate_migrate` from the Phase 4 promotion; runtime `career_os_runtime` was granted DML on the new table). Owner API restarted healthy on head `0015`. `career_os_validation` and the archived rollback DB were not touched.

### Owner UAT starting point
1. Open **Settings → Job Discovery** (`/settings/job-discovery`).
2. Review Active policy + Source status (Gmail listed as a separate stage; ATS shows 0 approved boards).
3. Try a preset (Strict/Balanced/Broad) → **Preview impact** → confirm before/after deltas.
4. Edit a setting (e.g., freshness 3 days) → Preview → **Save & activate** → verify effective policy + Fresh Jobs update; then **Restore defaults**.
5. Open a job detail → **"Why am I seeing this?"** → confirm origin/provider/decision/freshness/timestamp-confidence.
6. Confirm manual job 184 shows "Added manually" and is protected from age-out.
7. Run **Sync Gmail Alerts** / **Run Public Sources** and review the run summary + last-20-runs diagnostics.

### Recommended next phase
**Professional Application Document Engine** (deferred by scope this phase).
