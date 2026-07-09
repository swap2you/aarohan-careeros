# Workflow Lock 01 — Fresh Jobs Discovery

**Status:** READY_FOR_OWNER_VALIDATION  
**Date:** 2026-07-09  
**Branch:** `main`  
**Scope:** Logic-only. UI/UX remains locked and unchanged.

---

## 1. Scope

Make Fresh Jobs trustworthy by enforcing:

- 48-hour effective freshness
- US / Central Pennsylvania geography eligibility
- Target role-family gates
- Policy-driven discovery (no hardcoded GitLab public feed)
- Gmail alert received-time propagation and digest normalization
- Connector run persistence and honest health states
- Existing-data audit (dry-run) before archive/reclassify

**Explicitly out of scope:** UI redesign, Workflow Lock 02, RC4 tag.

---

## 2. Policy

Canonical file: `config/job-discovery-policy.yml`

| Gate | Rule |
|------|------|
| Freshness | `max_age_hours: 48`; unknown automated timestamp → quarantine |
| Geography | US remote / US location / Harrisburg–Central PA hybrid accept; foreign-only reject; unspecified remote quarantine |
| Roles | Primary TPM / QE manager / Director QE / Architect / AI-QE / Performance; secondary EM/SDET; generic eng/PM reject |
| Salary | Published max below `$170,000` reject |
| Sources | Adzuna/Jooble/USAJOBS/Remotive/Remote OK/RSS when configured; Greenhouse/Lever/Ashby only with explicit `approved_boards` (default empty) |

Effective freshness timestamp order:

1. `provider_posted_at` / `posted_at`
2. else `source_received_at` (Gmail)
3. else `discovered_at` only for manual/user-forwarded jobs

---

## 3. Source matrix

| Source | Mode | Notes |
|--------|------|-------|
| LinkedIn / Indeed alerts | Gmail labels | One digest entry → one job; `received_at` → `source_received_at` |
| Adzuna / Jooble / USAJOBS | API campaign | Included when keys configured |
| Remotive / Remote OK | Public API | US eligibility required |
| RSS | Configured feeds | Policy gates applied |
| Greenhouse / Lever / Ashby | Company boards | **Not** default public feed; require `approved_boards` |
| Fixture | Test only | Hidden from owner Fresh Jobs |

`POST /api/workflows/ingest/public` now runs `discover_fresh_jobs` internally (UI button path preserved).

---

## 4. Tests

Focused suites:

- `tests/test_fresh_jobs_eligibility.py` — geography, freshness, roles, URLs
- `tests/test_gmail_fresh_jobs.py` — digest split + received_at
- `tests/test_connector_runs.py` — persistence + discovery endpoint
- `tests/test_jobs_list.py` — Fresh Jobs defaults + no GitLab hardcode

Full API suite run as part of lock validation (see CI).

---

## 5. Live results

Live connector results depend on owner `.env.local` keys. With empty ATS `approved_boards` and without Adzuna/Jooble/USAJOBS keys, discovery returns zero accepted campaigns and a clear message — **not** a GitLab flood.

Owner should run:

```powershell
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached
# then Ingest Public Feed from Fresh Jobs, or:
# POST /api/workflows/discover-fresh-jobs
```

And:

```powershell
pwsh .\scripts\local\Audit-FreshJobsData.ps1
```

Report path: `generated/job-discovery-audit/fresh-jobs-audit-*.json`

Execute (owner-approved only):

```powershell
pwsh .\scripts\local\Audit-FreshJobsData.ps1 -Execute -ConfirmationText "ARCHIVE STALE AND INELIGIBLE JOBS"
```

### Audit runner note (owner attempt before this fix)

Repository HEAD before the audit-runner repair was `3b36209`.

The first owner dry-run / execute attempts failed **before any database access** because `Audit-FreshJobsData.ps1` invoked host Python without a usable `DATABASE_URL` (`sqlalchemy.exc.ArgumentError: Could not parse SQLAlchemy URL from string ''`).

**No owner data was changed** by those failed attempts (the process never opened PostgreSQL).

The repair runs the audit **inside the API container** via `docker compose exec` (same `.env.local` compose wrapper as `Start-Aarohan.ps1`), so `DATABASE_URL` and the `postgres` hostname are valid. Host Python is not used.

---

## 6. Before / after

| Metric | Before | After (expected) |
|--------|--------|------------------|
| Public ingest | Hardcoded `GreenhouseAdapter("gitlab")` | Policy campaign / empty boards |
| Fresh Jobs list | All owner historical rows | Eligible + ≤48h + not archived/quarantined |
| Overview `total_jobs` | Raw job count | Fresh eligible count (`fresh_jobs` + `historical_jobs` also returned) |
| Connector HEALTHY | Config READY | Only after successful live fetch with records |
| Gmail jobs | No received time on Job | `source_received_at` / `effective_freshness_at` |

Exact owner DB before/after counts come from the audit dry-run report.

---

## 7. Known limitations

1. Existing owner rows are **not** auto-archived until owner runs audit `-Execute`.
2. Company ATS boards stay empty until owner adds approved boards to policy.
3. Remotive/Remote OK live volume still depends on provider APIs and US text quality.
4. Overview card **label** still says “Total Jobs”; backend value is now fresh-eligible count (no UI redesign).
5. Dice/Glassdoor/USAJOBS email parsers remain first-URL oriented; LinkedIn/Indeed are multi-entry.

---

## 8. Owner acceptance checklist

- [ ] Fresh Jobs shows only US-eligible target roles
- [ ] Every visible row is ≤48 hours by effective freshness
- [ ] No GitLab-only public ingestion remains
- [ ] LinkedIn/Indeed digests create one job per posting
- [ ] Audit dry-run reviewed; optional `-Execute` applied if desired
- [ ] Live source report reviewed (configured vs HEALTHY)
- [ ] Automated tests / CI green
- [ ] Owner confirms Fresh Jobs output acceptable → mark **LOCKED**

---

## 9. Commit / CI

- Starting commit (pre Lock 01 logic): `812fe70ede865b2f3a9a5eb88ef6f7ddc23b583d`
- UI lock commit (preserved, no redesign in Lock 01): `c08d60890d1ed7301eb21c8b79f81886de93ae6b`
- Lock 01 discovery tip (pre audit-runner fix): `3b36209cf16ad01a76df9ef378039b8b7ce66cb2`
- Prior green CI: https://github.com/swap2you/aarohan-careeros/actions/runs/29030690427
- Audit-runner repair commit / CI: _(filled after push)_

**Status remains READY_FOR_OWNER_VALIDATION. Do not mark LOCKED until owner checklist is complete.**
