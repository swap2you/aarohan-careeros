# Phase 3 — Recover Owner Candidate

## Goal

Recover trustworthy owner data through staging and candidate databases without
overwriting evidence.

## Required flow

1. Restore verified validation snapshot into `career_os_recovery`.
2. Upgrade old schema only in recovery staging.
3. Classify every row:
   OWNER_CONFIRMED / LIVE_SOURCE_RECONSTRUCTABLE / TEST / FIXTURE / AMBIGUOUS / SYSTEM.
4. Exclude PG Test Co, e2e@test.local, example/fixture companies and fixture artifacts.
5. Create row-level recovery and exclusion manifests.
6. Create a fresh `career_os_owner_candidate`.
7. Import high-value owner state in priority order:
   - owner admin/settings
   - OAuth/Drive metadata when valid
   - applications/versions/documents
   - shortlist/submitted/interview/offer state
   - companies linked to real activity
   - Gmail processed IDs/provenance
   - recruiter/interview signals
   - trusted jobs
8. Reconstruct current job data through corrected Gmail/connectors rather than copying noise.
9. Validate login, OAuth, Drive, Gmail idempotency, applications, documents, Fresh Jobs,
   duplicate protection, immutable versions, row counts and no fixture/test data.
10. Back up and restore-test the candidate.
11. Produce cutover and rollback plan.
12. Stop before canonical owner cutover.
