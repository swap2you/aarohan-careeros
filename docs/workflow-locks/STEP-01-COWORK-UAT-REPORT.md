# Workflow Lock 01 — Fresh Jobs — Owner/Cowork UAT Report

**Status of Workflow Lock 01:** `READY_FOR_OWNER_VALIDATION` (NOT marked LOCKED — per instruction)
**UAT verdict:** **CONDITIONAL PASS** — all core Lock 01 guarantees verified against the live owner stack; 0 Critical, 0 High, 5 Medium, 9 Low findings. No finding invalidates eligibility/parity logic; two Medium findings (freshness data-trust FJ-UAT-004, broken source link FJ-UAT-005) warrant owner decision before LOCKED.
**Date executed:** 2026-07-11 (local)
**Tester:** Claude (Cowork), acting as owner UAT agent
**Application:** http://127.0.0.1:3000 (Next.js dashboard) · **API:** http://127.0.0.1:8000 (FastAPI)
**Session:** Owner session `swapnilpatil.tech@gmail.com`, `OWNER LOCAL` badge, `LOCAL_DEV_AUTH_BYPASS=true`
**Constraints honored:** no UI/UX redesign, no Docker/DB/infra changes, no recovery-script or OAuth changes, no migrations, no job deletion/archival, no `audit -Execute`, no Workflow Lock 02 work, no direct fixes — report only.

**Data disclosure:** UAT intentionally created **one** clearly labeled test job via New Opportunity intake — job **184** "Quality Engineering Manager (UAT Intake Test)" / "UAT Validation Co (Cowork Test)" / `ad_hoc` / `data_provenance=manual`. It was required by scope items 15–16 and was **not** removed (deletion/archival prohibited). Owner may archive it. No other owner data was modified.

---

## 1. Summary of results

| Metric | Result |
|---|---|
| Accepted jobs reviewed | **11 of 11** (ids 19, 21, 23, 24, 26, 28, 30, 32, 34, 136, 138) + UAT job 184 |
| OWNER_REVIEW jobs reviewed | **0 — none exist** (decision counts: ACCEPT=11, HISTORICAL=23, REJECT=141, `reject` lowercase=2; total 177 pre-UAT) |
| Scenarios passed | 17 of 20 fully; 3 passed with caveats (5, 6, 20) |
| Scenarios failed | 0 outright; defects filed against passing scenarios where behavior was wrong in part |
| Defects | Critical 0 · High 0 · **Medium 5** · Low 9 |
| Accepted count parity (UI ↔ API ↔ closure report) | **11 = 11 = 11** ✓ (12 after UAT intake job, as expected) |
| Stale `state=REJECTED` on eligible jobs | **0** ✓ (states: NORMALIZED=10, SHORTLISTED=1) |
| Duplicate job 31 (Blockstream syndicated) | `REJECT` / `eligible_for_owner=false` — correctly **excluded** ✓ |
| Console errors on /jobs | none ✓ |

---

## 2. Scenario results (scope items 1–20)

| # | Scenario | Result | Notes / evidence |
|---|---|---|---|
| 1 | Login and Overview | **PASS** (caveat) | Overview loads; cards Total Jobs=11, Shortlisted=1, Packets Ready=0, Submitted=0. Sign out fires `POST /api/auth/logout` (200) → `/login?returnTo=%2F` → auto `POST /api/auth/local-admin-login` (200) → back to Overview. Login page is unreachable while bypass enabled (FJ-UAT-013, Low, local-dev by design). Evidence: screenshots ss_0731svt69, ss_83072fp9j (network log). |
| 2 | Fresh Jobs navigation | **PASS** | Sidebar "Fresh Jobs" → `/jobs`; quick-action card also present on Overview. |
| 3 | Fresh Jobs list loads without errors | **PASS** | "11 jobs (fixture/test data hidden in owner mode)"; table renders; zero console errors/exceptions. Evidence: ss_6837bsbrv. |
| 4 | Accepted count matches backend evidence | **PASS** | UI 11 = `GET /api/jobs` total 11 = closure-report canonical 11; identical ids and titles to closure report §5. |
| 5 | TODAY / FRESH / RECENT labels | **PASS with caveat** | Tiers exist and are correct **at API level** (`freshness_bucket`: TODAY×4 — 138, 32, 34, 28; FRESH×1 — 23; RECENT×6 — 26, 24, 136, 19, 21, 30). The web UI renders **no freshness label anywhere** (no `freshness` reference in `apps/web/src`) → FJ-UAT-002. Stored bucket drifts stale (FJ-UAT-003). |
| 6 | Filters and sorting | **PASS with caveat** | Title search ✓ (e.g. "QA Engineering Manager" → 2: Blockstream 24, Finite State 26). Sort Newest ✓ / Company ✓ (07 CMG→…→Subway) / Salary ✓ (BCC first, nulls last). Page-size options ✓. Defects: stale page on filter apply (FJ-UAT-001), work-mode filter always empty (FJ-UAT-007). |
| 7 | Title, company, location, salary presentation | **PASS** | Rows show title, "Company · Location", salary "$140,000 – $150,000" (28) or "Not disclosed", family, fit, trust, PASS/FAIL, state. Salary under-capture vs provider pages → FJ-UAT-008. |
| 8 | Official/traceable source links | **PASS with caveat** | 10 of 11 links resolve to live Jooble listings matching title/company/location (see §3). Job 30 `/desc/` link returns empty content → FJ-UAT-005. All links are **aggregator** (Jooble) pages, not employer domains; detail-page label says "official employer URL" → FJ-UAT-006. |
| 9 | Job detail page | **PASS** | `/jobs/138`: header, meta line (company · location · Workplace TBD · state), Posted + Source, duplicate-risk panel, fit & trust with reasons, application mode (ATS unsupported → Manual), actions, description. Raw HTML entities in description → FJ-UAT-009. |
| 10 | Duplicate handling | **PASS** | All 11 detail endpoints return duplicate_risk GREEN "No known conflict". Syndicated duplicate job 31 (`Remote QA Engineering Manager for Blockchain & FinTech`, Blockstream) is `REJECT`/ineligible and absent from Fresh Jobs; accepted twin 24 visible. Search "QA Engineering Manager" returns 24 and 26 only — no dupe leak. |
| 11 | Non-software quality exclusions | **PASS** | Sampled rejected set includes TACOM "QUALITY ASSURANCE SPECIALIST" (Army depot, id 140), Westinghouse "Principal Supplier Quality Engineer" (22), warehouse/bottling QA rows — all REJECT. All 11 accepted are software/digital QE roles (verified per-job in §3). |
| 12 | Foreign-only exclusions | **PASS** | Rejected set contains UK/Australia/Canada/Perú rows (ids 174, 172, 171, 160–163, 89, 90 …) — none accepted. All 11 accepted have US locations; `location_eligibility` ∈ {ELIGIBLE_US, ELIGIBLE_LOCAL}. Value semantics oddity (Dallas TX / Tulsa OK / "United States" tagged ELIGIBLE_LOCAL) → FJ-UAT-014 (Low; outcome unaffected). |
| 13 | Malformed digest exclusions | **PASS** | Zero rows (accepted or rejected) with digest-style titles ("job alert", "N new jobs", digest). No malformed digest job is accepted. |
| 14 | No stale rejected status for eligible jobs | **PASS** | 0 eligible rows with `state ∈ {REJECTED, CLOSED}`; eligible states = NORMALIZED×10 + SHORTLISTED×1. Note: `JobScore.recommendation=REJECT` exists on all 11 but is correctly **not** surfaced as a status anywhere in UI (this is the Lock 01 semantic: fit/trust ≠ eligibility). BCC row shows honest "Hard filters failed — review before proceeding" with FILTER=FAIL, state NORMALIZED — correct semantics. |
| 15 | New Opportunity URL/text intake | **PASS** | Empty submit → clear dismissible error "Provide a URL, pasted text, or manual job details." Manual text intake → "Review before create" panel (source ad_hoc, extracted fields, matched pattern "quality engineering manager", recommended profile Quality Engineering Manager) → "Create job only" → job 184 created, detail page loads. Evidence: ss_9248r9rwf, ss_4479adwy2, ss_4116vxue4. |
| 16 | Manually confirmed opportunities remain visible | **PASS** | Job 184: `ACCEPT`, `eligible_for_owner=true`, bucket TODAY (`freshness_source=discovered_at`), `data_provenance=manual` — appears at top of Fresh Jobs (count 12). No pre-existing manual jobs existed to regress. Its "Open official application" link is an inert `adhoc://` URI → part of FJ-UAT-006. |
| 17 | Shortlist action and return navigation | **PASS with caveat** | `/shortlist` lists job 34 (Reveal Technology, SHORTLISTED, 50.18). Return navigation ✓: detail "← Back to jobs" and error-page "Back to Jobs" both land on `/jobs`. However **no owner-facing control exists to shortlist/unshortlist a job**, and Shortlist rows don't link to detail → FJ-UAT-010 (Low; UI is locked, log for backlog). |
| 18 | Loading, empty and error states | **PASS with caveat** | Missing job (`/jobs/99999`) → "Job detail unavailable / This job was not found." + Retry + Back to Jobs ✓ (ss_86929tc8d). Intake empty-input error ✓. Empty result set → bare "0 jobs" with empty table, no message → FJ-UAT-011 (Low). API-down state not tested (stopping services prohibited). |
| 19 | Pagination | **PASS** | 10/page → "Page 1 of 2", Next → page 2 shows the 11th row (Virtual Vocations 23), Previous ✓, Next disabled on last page ✓. Interaction bug with filters → FJ-UAT-001. |
| 20 | Responsive behavior (no design changes) | **PASS with caveat** | Verified structurally: `meta viewport width=device-width`, `@media (max-width: 960px)` rule present, table wrapper `overflow-x: auto` (scrolls instead of breaking), reduced-motion media query present. Visual narrow-width verification was **not possible**: the OS window manager refused programmatic resize (window stayed 2400px). No horizontal overflow at desktop width. Re-verify manually on a phone-sized window. |

---

## 3. Per-job inspection — all 11 accepted jobs (+ UAT job)

Freshness tier is the stored `freshness_bucket` (see FJ-UAT-003); "Link result" from live fetch on 2026-07-11. All sources `jooble_api`, `freshness_source=provider_posted_at`, `source_verified=false`, duplicate risk GREEN "No known conflict", visible status in UI = state (no rejected status shown), `ingest_decision=ACCEPT`, `eligible_for_owner=true` for every row.

| ID | Title | Company | Location | Tier | Effective | Software/digital relevance | Link result | State |
|---:|---|---|---|---|---|---|---|---|
| 138 | Senior Manager, Quality Engineering | Subway | Doral, FL | TODAY | 07-11 | ✓ Digital/Guest Engineering QE (mobile/web/API, Azure DevOps) | ✓ Live. Note: Jooble body says "Posted Tuesday, June 23, 2026" but "Vacancy posted 21 hours ago" (re-post; see FJ-UAT-004) | NORMALIZED |
| 32 | Sr. Manager, Quality Engineering — GES Technology Center | Deloitte LLP | Texas | TODAY | 07-10 | ✓ SaaS/cloud QE leadership (CI/CD, contract/API testing, AWS) | ✓ Live, "1 day ago". Salary $167.3k–$278.9k on page, not captured (FJ-UAT-008) | NORMALIZED |
| 34 | Head of Quality Assurance Engineering | Reveal Technology | New York, NY | TODAY | 07-10 | ✓ Software QA leadership (Playwright/TS, Unity3D, CI/CD) | ✓ Live, "1 day ago". $140k–160k on page, not captured | **SHORTLISTED** (protected) |
| 28 | Quality Assurance Engineering Manager | BCC Software | Rochester, NY | TODAY | 07-10 | ✓ Desktop+SaaS QE management | ✓ Live, "1 day ago". Salary $140k–150k captured ✓. FILTER=FAIL (fit 30) shown as review flag, not rejection ✓ | NORMALIZED |
| 23 | Principal Quality Engineer | Virtual Vocations Inc | United States | FRESH | 07-09 | ✓ Clinical-platform QE (automation, CI/CD) | ✓ Live, "2 days ago" | NORMALIZED |
| 26 | QA Engineering Manager | Finite State | United States | RECENT | 07-07 | ✓ Product-security software QE (AI-first, CI/CD) | ✓ Live, "4 days ago". $210k–240k on page, not captured | NORMALIZED |
| 24 | QA Engineering Manager | Blockstream | Tulsa, OK | RECENT | 07-07 | ✓ Blockchain/fintech software QE | ✓ Live, "4 days ago". Syndicated twin (job 31) correctly rejected as duplicate ✓ | NORMALIZED |
| 136 | Senior Manager, Quality Engineering | CFA Institute | Charlottesville, VA | RECENT | 07-07 | ✓ Platform QE (Playwright/TS, AI quality stack) | ✓ Live, "4 days ago". $140k–190k on page, not captured | NORMALIZED |
| 19 | Remote Senior Manager, ACAS Quality Engineering | CVS Health Corporation | Hartford, CT | RECENT | 07-06 | ✓ Healthcare-tech QE (claims platform, automation) | ✓ Live, "21 hours ago" (re-posted; app shows 07-06) | NORMALIZED |
| 21 | Senior Manager, Quality Engineering (Intelligent Automation) | 07 CMG Strategy Co., LLC | Columbus, OH | RECENT | 07-06 | ✓ Software QE (Chipotle IT; Playwright/Cypress, cloud) | ⚠ Live, but Jooble states "**posted more than 2 months ago**" — freshness materially older than tier implies (FJ-UAT-004). Company name is an aggregator artifact (actual employer Chipotle) | NORMALIZED |
| 30 | Quality Engineering Manager | Business Centric Technology | Dallas, TX | RECENT | 07-06 | ✓ per stored description (software QE manager role) | ✗ **`/desc/` URL returns empty content** — not verifiable (FJ-UAT-005) | NORMALIZED |
| 184 | Quality Engineering Manager (UAT Intake Test) | UAT Validation Co (Cowork Test) | Harrisburg, PA | TODAY | 07-12 (UTC) | ✓ (UAT-authored software QE text) | N/A — inert `adhoc://` URI rendered as "Open official application" (FJ-UAT-006) | NORMALIZED |

OWNER_REVIEW jobs: **none exist** in owner data (0 of 177) — nothing to inspect; scenario evidence retained from the full-decision scan.

---

## 4. Defects

Severity: Critical (breaks core guarantee/data loss) · High (wrong data shown to owner with no workaround) · Medium (wrong/misleading behavior with workaround or limited scope) · Low (cosmetic, hygiene, or backlog).

### Medium

**FJ-UAT-001 — Applying filters while on page > 1 keeps stale page index → empty list ("Page 2 of 1")**
- Repro: `/jobs` (10/page) → click **Next** (page 2) → enter Title/keyword `QA Engineering Manager` → **Apply filters**.
- Expected: results reset to page 1; matching rows shown.
- Actual: header "2 jobs" but table body empty; pager reads "Page 2 of 1". Clicking **Previous** recovers.
- Evidence: screenshot ss_6394f2dqp. Affected: `/jobs` page (client pagination state); API responds correctly.
- Blocks Lock 01? **No** (workaround exists) — should be fixed in the next logic pass.

**FJ-UAT-002 — Freshness tier (TODAY/FRESH/RECENT) is not visible anywhere in the owner UI**
- Repro: inspect `/jobs` list and `/jobs/{id}` detail; grep `apps/web/src` for `freshness` → no usage.
- Expected (UAT scope item 5): owner can see the tier per job. Actual: tier exists only in API (`freshness_bucket`); detail shows only "Posted: date (Nd ago)".
- Affected: `/jobs`, `/jobs/[id]`. Blocks Lock 01? **No** — tiers were validated via API; UI is design-locked, but the owner cannot currently confirm tiers without the API. Recommend a minimal text badge in a future logic-allowed change or accept API-level validation.

**FJ-UAT-004 — Provider re-post timestamps inflate freshness (data-trust)**
- Evidence: job 21 — app `effective_freshness_at=2026-07-06` (RECENT), Jooble page states "Vacancy posted **more than 2 months ago**". Job 138 — tier TODAY from re-post ("21 hours ago") while body says originally posted Jun 23.
- Expected: visible jobs are genuinely fresh. Actual: implementation correctly follows the documented timestamp policy (`provider_posted_at` first), but the aggregator's re-post dates can make old postings appear TODAY/RECENT.
- Affected: eligibility engine input data (Jooble connector), not code correctness.
- Blocks Lock 01? **Owner decision.** The lock's owner-facing promise ("every visible row is fresh") is weakened for re-posted listings. Options: capture original posted date where the provider exposes it, tag re-posts LOW_TRUST, or accept the limitation and document it.

**FJ-UAT-005 — Job 30 source link is dead/unverifiable (`https://jooble.org/desc/3351767658277894220`)**
- Repro: open job 30's URL — response has no title/content (all 10 `jdp/` links resolve normally).
- Expected (lock requirement: traceable source links): link resolves to the listing. Actual: empty page.
- Affected: job 30 record; possibly the connector's URL normalization for `desc/` variants.
- Blocks Lock 01? **No** for the feature; **yes** for trusting job 30 specifically — owner should re-verify or let it age out.

**FJ-UAT-007 — Work-mode filter returns 0 results for every option**
- Repro: `/jobs` → Work mode = Remote (or Hybrid / Fully remote (US)) → Apply filters → "0 jobs".
- Cause: `workplace_type` is `null` on all 11 accepted rows — the Jooble connector does not map remote/hybrid (even for titles like "Remote Senior Manager…" or detail pages saying "Remote job"). Detail page shows "Workplace TBD".
- Expected: remote roles filterable. Actual: filter silently empties the list.
- Affected: `/jobs` filter, Jooble connector field mapping. Blocks Lock 01? **No**, but it is a visible dead control.

### Low

**FJ-UAT-003 — Stored `freshness_bucket` computed at ingest, never refreshed** — jobs 34/28/32 (effective 07-10) still labeled TODAY ~30+ h later. The read-path visibility window is computed dynamically (correct); only the stored label drifts. Invisible today because of FJ-UAT-002; will mislead once tiers are surfaced. Fix: derive bucket at read time.
**FJ-UAT-006 — "Open official application" labeling** — the link text/copy claims "official employer URL" but targets the Jooble aggregator listing (all 11); for manual jobs it renders an inert `adhoc://…` href (job 184). Traceability OK; label inaccurate and the adhoc link is a dead click.
**FJ-UAT-008 — Salary under-capture** — provider pages show ranges for jobs 32 ($167–279k), 34 ($140–160k), 26 ($210–240k), 136 ($140–190k), 21 ($130–193k) yet the app has `salary_min/max=null` (only 28 captured). Salary is ranking-only, so no eligibility impact, but salary sort/bands lose signal.
**FJ-UAT-009 — Description renders raw HTML** — `/jobs/138` shows literal `&nbsp;` and `<b>…</b>` in the Description panel. Sanitize/strip on ingest or render.
**FJ-UAT-010 — No shortlist action in owner UI** — Shortlist page is read-only (SHORTLISTED or score ≥ 75), rows not clickable; no control anywhere to shortlist/unshortlist. Job 34's state predates UAT.
**FJ-UAT-011 — Bare empty state** — filtered "0 jobs" shows only the header row, no "no results, adjust filters" message.
**FJ-UAT-012 — Data hygiene in non-owner rows** — 2 rows with lowercase `reject` ingest_decision (case-inconsistent enum; still correctly excluded because visibility requires `ACCEPT`); mojibake in some rejected titles/locations ("PerÃº"); malformed locations on rejected rows ("Officer, ", "Nassau, ").
**FJ-UAT-013 — Sign out auto-re-authenticates** — with `LOCAL_DEV_AUTH_BYPASS=true`, `/login` immediately performs local-admin login; sign out appears to do nothing. Verified logout→login round-trip in the network log. Acceptable for local dev; ensure bypass is off in any non-local posture.
**FJ-UAT-014 — Minor semantics/doc issues** — (a) `location_eligibility=ELIGIBLE_LOCAL` on Dallas TX / Tulsa OK / "United States" rows (local should mean Central PA; outcome unaffected); (b) detail shows "(1d ago)" for a same-day posting (rounds up); (c) lock doc §6/§8 says "≤48 hours" while implementation uses the ≤7-day TODAY/FRESH/RECENT window (`_apply_fresh_jobs_defaults`) — align the document with the policy; (d) Overview card still labeled "Total Jobs" for the fresh-eligible count (known limitation #4, unchanged); (e) `07 CMG Strategy Co., LLC` is an aggregator company-name artifact (actual employer Chipotle).

---

## 5. Evidence index

| Ref | What |
|---|---|
| ss_0731svt69 | Overview, owner session, Total Jobs=11 |
| ss_83072fp9j + network log | logout 200 → /login → local-admin-login 200 → Overview (FJ-UAT-013) |
| ss_6837bsbrv | Fresh Jobs list, 11 jobs, fixture-hidden note |
| ss_6394f2dqp | FJ-UAT-001 "Page 2 of 1", 2 jobs, empty table |
| ss_1166w6d5w | Job 138 detail (duplicate GREEN, fit/trust, ATS, description) |
| ss_9248r9rwf / ss_4479adwy2 / ss_4116vxue4 | Intake form / Review-before-create / created job 184 |
| ss_5236ozah5 | Shortlist page (job 34) |
| ss_86929tc8d | Not-found error state `/jobs/99999` |
| ss_081261slx | Post-intake list, 12 jobs, job 184 on top |
| API probes | `GET /api/jobs` (11), `GET /api/jobs?include_all=true` (177; decisions ACCEPT=11/HISTORICAL=23/REJECT=141/`reject`=2; OWNER_REVIEW=0), `GET /api/jobs/{id}` and `/detail` for all 11 + 31 + 184 |
| Link fetches 2026-07-11 | all 11 source URLs (10 live Jooble listings, 1 empty `/desc/` response) |

Console: no errors on `/jobs`. Screenshots were captured in-session (Cowork does not persist them to repo); re-capture via the repro steps if archival copies are needed.

---

## 6. Verdict and next action

**Verdict: CONDITIONAL PASS.** The Lock 01 core guarantees hold on the live owner stack: 11/11 accepted-count parity across UI, API, and audit evidence; owner visibility driven solely by `eligible_for_owner + ingest_decision=ACCEPT` with zero stale `REJECTED` states; the syndicated duplicate stays excluded; non-software, foreign-only, and digest exclusions hold with zero false accepts; manual intake works end-to-end and manual opportunities stay visible. 0 Critical / 0 High.

**Do not mark LOCKED yet.** Exact next action, in order:

1. **Owner decision on FJ-UAT-004 (freshness data-trust):** decide whether re-posted aggregator listings (job 21 proven ≥2 months old, job 138 originally Jun 23) may count as TODAY/RECENT, or whether the connector/policy must prefer original posted dates / tag re-posts LOW_TRUST. This is the only finding that touches the lock's owner-facing promise.
2. **Re-verify or discard job 30** (dead `/desc/` source link, FJ-UAT-005) — no delete/archive was performed during UAT.
3. Schedule fixes for FJ-UAT-001 (filter/page reset), FJ-UAT-007 (workplace_type mapping), FJ-UAT-002/003 (surface + derive freshness tier) in the next logic-allowed change window; triage Lows to backlog.
4. Archive UAT job 184 at owner's convenience.
5. After items 1–2 are resolved to owner satisfaction, complete the §8 owner checklist in `STEP-01-FRESH-JOBS-LOCK.md` and only then mark Workflow Lock 01 **LOCKED**. Workflow Lock 02 remains not started.
