# R1 Local Acceptance Criteria

## Google
- OAuth Connect button opens Google consent.
- Correct dedicated account is selected.
- Callback succeeds.
- Refresh token is encrypted and persisted.
- Gmail read-only connection works.
- Drive root folder is accessible.
- Required Drive subfolders are created or reused.
- Disconnect and reconnect work.
- Exact remediation is shown for invalid secret, redirect mismatch, revoked token, missing API, insufficient scope, and inaccessible folder.

## Job intake
- Fixture feed works.
- Greenhouse public feed works.
- Lever public feed works.
- Gmail alert ingestion works.
- Manual URL/pasted description works.
- Duplicates are prevented.
- No LinkedIn or Indeed scraping.

## Documents
- Three resume profiles.
- DOCX and PDF output.
- Dashboard preview.
- Evidence map.
- Keyword map.
- Change report.
- Missing evidence warnings.
- ATS text extraction validation.
- Google Drive synchronization.
- Version and checksum tracking.

## Dashboard
- All manual actions work.
- Progress and errors are visible.
- No schedule is active.
- No final submission endpoint exists.
- External email send is disabled by default.

## Optional test email
- Separate incremental consent for Gmail send.
- Allowlist only.
- Confirmation click required.
- `[AAROHAN TEST]` subject prefix.
- No bulk send.
- Full audit log.

## Persistence and quality
- Complete Alembic migrations.
- PostgreSQL survives restart.
- Backup and restore are demonstrated.
- Backend tests pass.
- Frontend tests pass.
- Playwright E2E passes.
- Secret scan passes.
- Dependency scan passes or exceptions are documented.
- Cursor first review is complete.
