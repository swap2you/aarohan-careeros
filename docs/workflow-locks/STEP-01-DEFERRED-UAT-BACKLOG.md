# Workflow Lock 01 — Deferred UAT Backlog

**Source:** `docs/workflow-locks/STEP-01-COWORK-UAT-REPORT.md` (Cowork UAT, 2026-07-11, CONDITIONAL PASS — 0 Critical, 0 High, 5 Medium, 9 Low).
**Decision:** Workflow Lock 01 remains provisionally complete but **NOT LOCKED**. These findings are retained as backlog; product development (Workflow 01.5) proceeds without waiting on them.
**Why development proceeds now:** No finding invalidates the Lock 01 core guarantees (11/11 accepted-count parity across UI/API/audit, eligibility governed by `eligible_for_owner + ingest_decision=ACCEPT`, zero stale `REJECTED`, syndicated duplicate excluded, non-software/foreign/digest exclusions hold). All open items are Medium/Low with workarounds or are data-trust/UX polish. Workflow 01.5 (Discovery Control Center) directly improves several of them (freshness-tier visibility, source-link honesty, source transparency) without redesigning the UI.

The two classes below are kept strictly separate. **Functional defects are not described as flaky.**

---

## A. Functional backlog (real product defects)

| ID | Finding | Severity | Impact | Reproduction | Proposed fix | Planned workflow | Status |
|---|---|---|---|---|---|---|---|
| FJ-UAT-001 | Applying filters while on page > 1 keeps stale page index → "Page 2 of 1" empty list | Medium | Owner sees an empty list after filtering from a later page; recoverable via Previous | `/jobs` (10/page) → Next → enter Title `QA Engineering Manager` → Apply filters → header "2 jobs" but empty body, pager "Page 2 of 1" | Reset client pagination to page 1 whenever filter/search/sort inputs change | Workflow 02 (Fresh Jobs UX pass) | Deferred |
| FJ-UAT-002 | Freshness tier (TODAY/FRESH/RECENT) not visible anywhere in owner UI | Medium | Owner cannot confirm tier without the API | Inspect `/jobs` and `/jobs/[id]`; no `freshness` usage in `apps/web/src` | Surface a minimal text tier badge on list + detail | **Partially addressed in 01.5**: job detail now shows tier + freshness source via the "Why am I seeing this?" panel; list badge deferred to Workflow 02 | Partially addressed |
| FJ-UAT-004 | Provider re-post timestamps inflate freshness (data-trust): job 21 shows RECENT while Jooble says ">2 months"; job 138 TODAY from a re-post | Medium | The lock's "every visible row is fresh" promise is weakened for re-posted aggregator listings | Compare app `effective_freshness_at` vs the live provider page for jobs 21 and 138 | Capture original posted date where exposed; tag re-posts LOW_TRUST; surface timestamp confidence | 01.5 adds `timestamp_confidence` in explainability; connector original-date capture deferred to Workflow 02 | Partially addressed (owner decision still required) |
| FJ-UAT-005 | Job 30 source link dead/unverifiable (`jooble.org/desc/3351767658277894220` returns empty) | Medium | One accepted job's source is not verifiable | Open job 30 URL → empty page (all 10 `jdp/` links resolve) | Normalize `/desc/` variants in the Jooble connector; re-verify or age out job 30 | Workflow 02 (connector URL normalization) | Deferred (owner may re-verify/discard) |
| FJ-UAT-007 | Work-mode filter returns 0 for every option because `workplace_type` is null on all accepted rows | Medium | Visible dead control; remote roles unfilterable | `/jobs` → Work mode = Remote → Apply → "0 jobs" | Map remote/hybrid in the Jooble connector; hide the control when unmapped | Workflow 02 (connector field mapping) | Deferred |
| FJ-UAT-006 | Aggregator links labeled "official employer URL"; manual jobs render inert `adhoc://` href | Medium (labeling) | Misleading provenance labeling; dead click for manual `adhoc://` | Open any accepted job detail → "Open official application" points to Jooble; job 184 → `adhoc://` | Relabel as "source listing (aggregator)"; suppress inert links; 01.5 origin/explainability clarifies provenance | 01.5 exposes true origin/provider in the Why panel; link relabel deferred to Workflow 02 | Partially addressed |
| — | Responsive / filter caveats (visual narrow-width verification blocked by window manager) | Low | Unverified small-screen layout | Resize window to phone width (blocked during UAT) | Manual re-verify on a phone-sized window; structural media queries already present | Workflow 02 | Deferred |
| — | Disclosed Cowork UAT job **184** ("Quality Engineering Manager (UAT Intake Test)") requires owner disposition | Low | One clearly labeled test job remains in owner data | `GET /api/jobs` → id 184 | Owner archives it at convenience (no deletion performed) | Owner action | **Open — awaiting owner disposition.** In 01.5 it is classified `OWNER_ADDED`, `manual_protected=true`, and appears under manual opportunities; owner may archive. |

### Additional Low-severity hygiene items (from UAT §4 Low)
- FJ-UAT-003 stored `freshness_bucket` drifts (read path is dynamic; label stale) — 01.5 explainability recomputes tier at read time.
- FJ-UAT-008 salary under-capture (ranking-only; no eligibility impact).
- FJ-UAT-009 description renders raw HTML entities.
- FJ-UAT-010 no owner-facing shortlist/unshortlist control.
- FJ-UAT-011 bare empty state ("0 jobs" with no message).
- FJ-UAT-012 case-inconsistent `reject` enum on non-owner rows; mojibake in rejected titles.
- FJ-UAT-013 sign-out auto-re-auth under `LOCAL_DEV_AUTH_BYPASS` (local-dev by design).
- FJ-UAT-014 minor location-semantics / doc-window wording issues.

All Lows are deferred to a Workflow 02 hygiene pass; none block Lock 01 or 01.5.

---

## B. Flaky / test-infrastructure backlog (NOT product defects)

| ID | Finding | Severity | Impact | Reproduction | Proposed fix | Planned workflow | Status |
|---|---|---|---|---|---|---|---|
| FLAKE-PW-001 | Playwright teardown / parallel-execution instability | Low (infra) | Intermittent red on full-parallel Playwright runs; not a functional regression | Run full Playwright suite with default workers; teardown races surface intermittently. Reruns of the same specs with `--workers=1` pass | Stabilize teardown ordering / global-setup isolation; consider serial teardown project | Test-infrastructure hardening (Workflow 02) | Deferred |

This item is **test infrastructure only** — reruns of the affected specs pass deterministically, and it does not correspond to any owner-facing behavior. It is explicitly kept out of the functional backlog above.
