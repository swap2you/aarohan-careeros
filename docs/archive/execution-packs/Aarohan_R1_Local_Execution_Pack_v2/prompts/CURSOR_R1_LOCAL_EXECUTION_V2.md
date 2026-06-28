# Cursor R1 Local Execution v2

You are the primary implementation, integration, testing, documentation, cleanup, and first-review agent for Aarohan CareerOS.

Read the entire repository plus:
- `00_START_HERE.md`
- `01_GOOGLE_CONFIGURATION_VERIFICATION.md`
- `config/integration-context.yml`
- `03_LOCAL_ENV_TEMPLATE.md`
- `04_R1_ACCEPTANCE_CRITERIA.md`

## Operating mode
- Local only
- Cursor Auto
- Manual dashboard actions
- No deployment
- No push
- No commit
- No active production schedules
- No final application submission
- No LinkedIn or Indeed scraping
- No automatic external outreach

## First gate: inspect and consolidate
1. Inspect the existing code, prompts, local packs, tests, Docker, migrations, documentation, and configuration.
2. Create `validation/R1_BASELINE_AUDIT.md` classifying every requirement as:
   - WORKING
   - PARTIAL
   - STUB
   - BROKEN
   - MISSING
3. Move obsolete/superseded prompt packs and design drafts to `docs/archive/`.
4. Keep one current architecture, one current runbook, one current release plan, and one current troubleshooting guide.
5. Preserve Career Vault evidence and historical reports.

## Secret file
Expected OAuth JSON:

`C:\AarohanSecrets\google-oauth-client.json`

If the file exists only at:

`C:\Development\Workspace\aarohan-careeros\AarohanSecrets\google-oauth-client.json`

then:
- run or reproduce `02_MOVE_SECRET_FILE.ps1`
- copy it outside the repo
- add `AarohanSecrets/` to `.gitignore`
- update local configuration
- do not print the JSON content
- do not include its client secret in any report

## Google implementation
Use the latest project values from `config/integration-context.yml`.

Default OAuth request scopes must be exactly:
- openid
- userinfo.email
- userinfo.profile
- drive.file
- gmail.readonly

Do not request every scope configured in the Cloud console.

Implement:
- connect
- callback
- CSRF state validation
- offline access
- refresh token handling
- encrypted token persistence
- refresh
- status
- disconnect
- revoke
- account identity verification
- explicit remediation errors

The connected account must be:
`swapnilpatil.tech@gmail.com`

Google Drive:
- locate the configured root folder
- create/reuse the required folder tree
- persist folder/file IDs, links, versions, and checksums
- upload generated application and interview documents

Gmail:
- read only
- ingest Aarohan-labeled job, recruiter, interview, application, and rejection messages
- store processed Gmail message IDs in PostgreSQL
- do not mutate Gmail labels/messages in R1

Optional test send:
- use incremental authorization for `gmail.send`
- disabled by default
- only allow configured test recipients
- require confirmation
- prefix `[AAROHAN TEST]`
- no bulk send
- if send scope is not connected, generate `.eml` instead

## Complete implementation
Finish:
- secure first-run admin
- full Alembic migrations
- job source adapters
- normalization and deduplication
- transparent scoring
- Career Vault evidence retrieval
- three resume profiles
- DOCX/PDF generation
- ATS and text-extraction validation
- document preview
- Google Drive synchronization
- approval queue
- manual application tracking
- recruiter signals
- Interview Grilling Machine
- consulting lead workflow
- reports
- AI usage/cost controls
- audit log
- validation center
- exact troubleshooting messages

## Dashboard required pages
- Executive Overview
- Fresh Jobs
- Shortlist
- Job Detail
- Application Packet Preview
- Approval Queue
- Applications
- Recruiter Signals
- Interview Preparation
- Consulting Leads
- Reports
- AI Usage and Cost
- Audit Log
- Settings / Integrations
- Validation Center

## Required tests
Run and repair:
- backend format/lint
- frontend format/lint
- unit tests
- PostgreSQL integration tests
- migration blank-db test
- migration rollback test
- auth tests
- source adapter tests
- Gmail/Drive fixture tests
- OAuth state/callback/refresh/revoke tests
- scoring boundaries
- evidence grounding
- DOCX/PDF generation
- text round-trip checks
- interview tests
- consulting tests
- AI budget tests
- prompt injection
- unsafe HTML
- Playwright E2E
- secret scan
- prohibited-source scan
- dependency scan
- Docker build/start
- restart persistence
- backup/restore
- full end-to-end demo

## First review
After implementation, perform separate reviews:
- Product
- Security
- Database
- Backend
- Frontend/UX
- Google integration
- ATS/document quality
- Test automation
- DevOps
- Career truthfulness

Fix all P0 and P1 issues. Fix practical P2 issues.

## Required evidence files
Create:
- `validation/R1_BASELINE_AUDIT.md`
- `validation/CURSOR_FIRST_REVIEW.md`
- `validation/CURSOR_TEST_EVIDENCE.md`
- `validation/CURSOR_END_TO_END_DEMO.md`
- `validation/SECOND_REVIEW_HANDOFF.md`
- `docs/releases/R1_LOCAL_COMPLETE.md`

## Final response
Return:
- READY or NOT READY
- exact files changed
- files archived
- commands run
- actual test counts/results
- Docker status
- local URLs
- Google OAuth status
- connected Google account
- Drive folder IDs
- Gmail ingestion evidence
- generated sample paths
- unresolved defects
- user actions still required
- independent second-review command

Do not stop after creating code. Continue until the local application is proven or a real external action requires the user.
