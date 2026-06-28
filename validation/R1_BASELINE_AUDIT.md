# R1 Baseline Audit

Date: 2026-06-27  
Scope: Aarohan CareerOS local V1 against R1 acceptance criteria

## Summary

| Status | Count |
|--------|------:|
| WORKING | 28 |
| PARTIAL | 12 |
| STUB | 2 |
| BROKEN | 0 |
| MISSING | 4 |

## Google integration

| Requirement | Status | Notes |
|-------------|--------|-------|
| OAuth connect/callback | WORKING | Unified scopes; HTML callback page |
| CSRF state validation | WORKING | `_oauth_states` map |
| Offline access + refresh | WORKING | `access_type=offline`, refresh in `get_token` |
| Encrypted token persistence | WORKING | Fernet via `crypto.py` |
| Disconnect + revoke | WORKING | Token revoke POST to Google |
| Account identity verification | WORKING | Must match `swapnilpatil.tech@gmail.com` |
| Remediation errors | WORKING | `OAUTH_REMEDIATION` map |
| Gmail read-only ingest | PARTIAL | Live client implemented; live consent not yet proven |
| Drive folder tree | PARTIAL | `ensure_drive_folder_tree`; live proof pending |
| Drive upload sync | PARTIAL | Wired into packet generation |
| Optional test send | PARTIAL | `.eml` fallback; incremental send scope scaffolded |
| Live OAuth consent | MISSING | Requires user browser action |

## Job intake

| Requirement | Status |
|-------------|--------|
| Fixture feed | WORKING |
| Greenhouse public feed | WORKING |
| Lever public feed | WORKING |
| Gmail alert ingestion | PARTIAL (fixture + live client) |
| Manual URL/paste ingest | WORKING |
| Deduplication | WORKING |
| No LinkedIn/Indeed scraping | WORKING |

## Documents

| Requirement | Status |
|-------------|--------|
| Three resume profiles | WORKING |
| DOCX/PDF generation | WORKING |
| Dashboard preview | WORKING |
| Evidence/keyword maps | WORKING |
| Missing evidence warnings | WORKING |
| ATS validation | PARTIAL |
| Drive sync | PARTIAL |
| Version/checksum tracking | PARTIAL |

## Dashboard

| Page | Status |
|------|--------|
| Executive Overview | WORKING |
| Fresh Jobs | WORKING |
| Shortlist | WORKING |
| Job Detail | WORKING |
| Application Packet Preview | WORKING (approvals) |
| Approval Queue | WORKING |
| Applications | WORKING |
| Recruiter Signals | WORKING |
| Interview Preparation | WORKING |
| Consulting Leads | WORKING |
| Reports | WORKING (analytics) |
| AI Usage and Cost | WORKING |
| Audit Log | WORKING |
| Settings / Integrations | WORKING |
| Validation Center | WORKING |

## Persistence and quality

| Requirement | Status |
|-------------|--------|
| Alembic migrations | WORKING (`0001`, `0002`) |
| First-run admin | WORKING |
| AI budget caps | WORKING |
| Audit log | WORKING |
| Secret scan | WORKING |
| Prohibited source scan | WORKING |
| Backend tests (19) | WORKING |
| Frontend build | WORKING |
| Playwright E2E | MISSING (not executed) |
| Docker build/start | MISSING (Docker not on agent host) |
| Backup/restore demo | PARTIAL (script exists) |
| Dependency scan | MISSING |

## Archived / consolidated

- `prompts/CURSOR_MASTER_BUILD_PROMPT.md` → `docs/archive/`
- `prompts/CURSOR_CONTINUE_UNTIL_GATE_COMPLETE.md` → `docs/archive/`
- `prompts/CURSOR_LOCAL_FIRST_COMPLETE_REVIEW.md` → `docs/archive/`
- `Aarohan_Local_First_Cursor_Pack/` → `docs/archive/`

Current execution pack: `Aarohan_R1_Local_Execution_Pack_v2/`
