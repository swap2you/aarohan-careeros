# Cursor Finalization, Full Validation, and Main Sync

You are the primary implementation, cleanup, integration, testing, documentation, Git, and first-review agent for Aarohan CareerOS.

Repository root:

`C:\Development\Workspace\aarohan-careeros`

Central repository:

`https://github.com/swap2you/aarohan-careeros.git`

The user has explicitly approved:
- one working branch only;
- branch name `main`;
- direct initial commit and push to `main`;
- no pull request for this first private baseline;
- local development and validation;
- no cloud deployment yet.

## Non-negotiable boundaries

- Do not commit or print secrets.
- Do not commit OAuth JSON.
- Do not commit `.env.local`.
- Do not commit `AarohanSecrets/`, `private/`, generated runtime output, logs, tokens, or credentials.
- Do not scrape LinkedIn or Indeed.
- Do not add unattended final application submission.
- Do not activate production schedules.
- Do not send external email except through the explicit test-only allowlist and confirmation workflow.
- Do not push until all required local gates pass.
- Do not force-push unless the remote is verified empty and a normal first push is impossible.
- Never delete unique source or Career Vault evidence without preserving it.

## Phase 1 — Inspect Git and repository state

Run and record:

```powershell
git rev-parse --show-toplevel
git status --short
git status --short --ignored
git branch --show-current
git remote -v
git log --oneline --decorate --all -20
gh auth status
gh repo view swap2you/aarohan-careeros --json nameWithOwner,visibility,defaultBranchRef,url
```

If GitHub CLI is unavailable, install it using the official package manager or continue with Git after verifying credentials.

Verify:
- repository root is correct;
- GitHub authentication is the `swap2you` account;
- remote repository is private;
- no secret files are staged or tracked;
- local branch history is understood before changes.

If the current local branch is `master`, rename it:

```powershell
git branch -M main
```

Configure the remote safely:

```powershell
git remote get-url origin
```

If `origin` is missing:

```powershell
git remote add origin https://github.com/swap2you/aarohan-careeros.git
```

If `origin` is incorrect:

```powershell
git remote set-url origin https://github.com/swap2you/aarohan-careeros.git
```

Fetch without overwriting local work:

```powershell
git fetch origin --prune
```

Inspect remote refs:

```powershell
git ls-remote --heads origin
```

If the remote has commits, compare histories before proceeding. Do not overwrite remote history. Reconcile safely and document the action.

## Phase 2 — Canonical repository cleanup

Create:

`validation/R1_REPOSITORY_AUDIT.md`

Classify every root file/folder as:
- KEEP
- MOVE
- ARCHIVE
- DELETE
- GENERATED
- LOCAL_ONLY
- SECRET_RISK

The final canonical root should contain only required items such as:

```text
apps/
career_vault/
config/
docs/
n8n/
scripts/
tests/
validation/
.cursor/
.github/
AGENTS.md
README.md
.env.example
.gitignore
docker-compose.yml
pyproject.toml or required package files
```

Move obsolete design packs and superseded prompts to:

`docs/archive/ai-prompts/`

Remove extracted pack directories after preserving unique content.

Move runtime-generated output to:

`.local/`
`artifacts/`
`generated/`

and ensure they are gitignored unless a small sanitized fixture is intentionally tracked.

Ensure `.gitignore` includes at least:

```gitignore
.env
.env.*
!.env.example
.env.local
.env.*.local
AarohanSecrets/
private/
secrets/
.local/
artifacts/
generated/
logs/
*.log
*.pem
*.key
*.crt
google-oauth-client.json
__pycache__/
.pytest_cache/
.venv/
node_modules/
.next/
coverage/
dist/
build/
playwright-report/
test-results/
```

Run secret scans over:
- tracked files;
- staged files;
- untracked project files;
- Git history if any local commits already exist.

Do not reveal secret values in reports.

## Phase 3 — Create one authoritative documentation set

Create or rewrite these canonical documents:

```text
README.md
docs/architecture/ARCHITECTURE.md
docs/runbooks/LOCAL_DEVELOPMENT.md
docs/runbooks/GOOGLE_OAUTH.md
docs/runbooks/TROUBLESHOOTING.md
docs/runbooks/BACKUP_RESTORE.md
docs/testing/TEST_STRATEGY.md
docs/testing/UAT_RUNBOOK.md
docs/operations/MAINTENANCE.md
docs/releases/R1_LOCAL_COMPLETE.md
```

`LOCAL_DEVELOPMENT.md` must provide exact commands for:

### Prerequisite/version check

```powershell
git --version
gh --version
docker --version
docker compose version
python --version
node --version
npm --version
pwsh --version
```

### One-command bootstrap

Implement:

```text
scripts/local/Bootstrap-Aarohan.ps1
scripts/local/Start-Aarohan.ps1
scripts/local/Stop-Aarohan.ps1
scripts/local/Test-Aarohan.ps1
scripts/local/Reset-Aarohan.ps1
scripts/local/Backup-Aarohan.ps1
scripts/local/Restore-Aarohan.ps1
```

The scripts must:
- detect missing prerequisites;
- give exact remediation;
- initialize non-secret local configuration;
- never print secrets;
- start backend, frontend, PostgreSQL, and n8n;
- verify health;
- stop cleanly;
- preserve data unless reset is explicitly confirmed.

Document both supported modes:

1. Docker Compose mode — preferred.
2. Direct developer mode — backend and frontend separately.

Document exact backend commands, frontend commands, migrations, tests, and URLs.

## Phase 4 — Docker installation and verification

Run:

```powershell
docker --version
docker compose version
```

If Docker Desktop is missing, attempt installation with:

```powershell
winget install -e --id Docker.DockerDesktop
```

A user UAC approval, sign-in, WSL update, or restart may be required. Pause only for that real interaction. Afterward resume automatically.

Verify Docker Desktop is running before continuing.

Run:

```powershell
docker compose config
docker compose build --no-cache
docker compose up -d
docker compose ps
docker compose logs --no-color
```

Required healthy services:
- PostgreSQL
- FastAPI API
- Next.js frontend
- n8n

Add health checks where missing.

Prove:
- API connects to PostgreSQL;
- frontend connects to API;
- n8n starts;
- PDF generation works inside the API container;
- data survives `docker compose restart`.

## Phase 5 — Database and Alembic correctness

Inspect every SQLAlchemy model and every migration.

Required:
- complete schema in Alembic;
- all tables, columns, indexes, unique constraints, foreign keys, and enums represented;
- no production startup dependence on `Base.metadata.create_all()`.

Prove against a clean PostgreSQL database:

```powershell
alembic upgrade head
alembic check
alembic downgrade base
alembic upgrade head
```

Add automated migration tests.

Prove:
- clean bootstrap;
- downgrade/upgrade;
- persistence after restart;
- backup and restore into a clean database.

## Phase 6 — Google OAuth, Gmail, and Drive

Use:

```text
Dedicated account:
swapnilpatil.tech@gmail.com

Project ID:
aarohan-careeros-500722

Project number:
558756512850

OAuth JSON:
C:\AarohanSecrets\google-oauth-client.json

Drive root folder:
1yqQixjo6GGBcjwIXEfHx1STeaJHz_qOI
```

Default requested scopes must be exactly:

```text
openid
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
https://www.googleapis.com/auth/drive.file
https://www.googleapis.com/auth/gmail.readonly
```

Implement and prove:
- connect;
- callback;
- CSRF state validation;
- dedicated-account identity verification;
- encrypted refresh-token persistence;
- access-token refresh;
- status;
- disconnect;
- revoke;
- reconnect;
- exact safe remediation messages.

Gmail ingestion must:
- call `labels.list`;
- resolve exact label IDs for:
  - Aarohan/Job Alerts
  - Aarohan/Recruiters
  - Aarohan/Interviews
  - Aarohan/Applications
  - Aarohan/Rejections
- use exact label IDs;
- paginate;
- parse text and HTML MIME safely;
- support multipart messages;
- deduplicate by Gmail message ID;
- store processing state in PostgreSQL;
- not mutate Gmail messages or labels.

Drive integration must create or reuse idempotently:

```text
01_Career_Vault
02_Application_Packets
03_Interview_Preparation
04_Consulting
05_Reports
99_Archive
```

Persist folder IDs, file IDs, web URLs, versions, checksums, ownership relationships, and timestamps.

Run the folder-tree operation twice and prove no duplicates are created.

## Phase 7 — Complete end-to-end application behavior

Complete and prove:

### Job sources
- fixture source;
- Greenhouse public API;
- Lever public API;
- approved Gmail alerts;
- manual URL/pasted job description;
- deduplication;
- freshness;
- source audit.

### Transparent score
- compensation;
- benefits confidence;
- remote/location;
- technical fit;
- leadership;
- AI-enabled QE;
- stability/risk;
- evidence strength;
- freshness;
- application effort;
- interview probability.

Every score must show reasoning, uncertainty, gaps, risk, and recommended action.

### Application packet
Generate a fresh current packet containing:
- ATS DOCX;
- ATS PDF;
- cover letter;
- recruiter note;
- hiring-manager note;
- fit analysis;
- keyword map;
- evidence map;
- change report;
- missing-evidence report;
- interview starter.

Validate:
- DOCX extraction;
- PDF extraction;
- contact details;
- dates;
- headings;
- bullet ordering;
- duplicates;
- unsupported claims;
- evidence IDs;
- page count;
- filename;
- checksum;
- Drive upload;
- dashboard preview.

### Dashboard
Required pages:
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

### Interview Grilling Machine
Prove:
- company brief;
- role outcomes;
- JD/resume gaps;
- recruiter and hiring-manager questions;
- technical and architecture questions;
- automation, API, performance, CI/CD, cloud, and data questions;
- AI-enabled QE, agentic AI, context engineering, prompt engineering, MCP, LLM/RAG evaluation, guardrails, observability, and human-in-the-loop questions when relevant;
- leadership and behavioral questions;
- verified STAR mappings;
- honest gap answers;
- exercises;
- scoring;
- weak-area tracking;
- seven-day plan;
- voice mock-interview export.

### Consulting
Prove:
- lead intake;
- classification;
- service mapping;
- score;
- proposal;
- case-study mapping;
- follow-up state;
- analytics.

## Phase 8 — Complete test execution

Run and repair all:

```text
Python format
Python lint
TypeScript format
TypeScript lint
backend unit tests
PostgreSQL integration tests
Alembic migration tests
auth tests
authorization tests
OAuth state/callback/refresh/revoke tests
Gmail exact-label/pagination/MIME tests
Drive idempotency tests
job-source tests
deduplication tests
scoring-boundary tests
evidence-grounding tests
DOCX tests
PDF tests
text round-trip tests
interview tests
consulting tests
AI-budget tests
prompt-injection tests
unsafe-HTML tests
Playwright E2E
secret scan
prohibited-source scan
dependency vulnerability scan
Docker smoke tests
restart-persistence tests
backup/restore tests
```

Do not claim success from inspection. Record commands, duration, count, pass/fail, and artifacts.

For Playwright:
- start the complete application;
- install required browsers if missing;
- test real user journeys;
- save screenshots, traces, and reports under ignored `artifacts/`.

## Phase 9 — Full local demonstration

Prove exactly:

1. Bootstrap local environment.
2. Securely initialize administrator.
3. Log in.
4. Connect Google.
5. Confirm account `swapnilpatil.tech@gmail.com`.
6. Create/reuse Drive tree.
7. Ingest fixtures.
8. Ingest one live Greenhouse or Lever feed.
9. Sync Gmail exact labels.
10. Deduplicate.
11. Score.
12. Open job detail.
13. Generate fresh packet.
14. Preview DOCX/PDF content.
15. Validate evidence.
16. Approve packet.
17. Mark manually submitted.
18. Ingest recruiter fixture or permitted test message.
19. Generate interview workspace.
20. Generate consulting recommendation.
21. Verify audit log.
22. Verify AI budget controls.
23. Restart containers.
24. Verify persistence.
25. Back up database.
26. Restore to clean test database.
27. Verify restored data.

Write:

```text
validation/CURSOR_END_TO_END_DEMO.md
validation/CURSOR_TEST_EVIDENCE.md
```

## Phase 10 — Cursor first review

Perform independent review roles:
- Product
- Security
- Database
- Backend
- Frontend/UX
- Google integration
- Gmail/Drive
- ATS/document quality
- Test automation
- DevOps
- Career truthfulness

Fix all P0 and P1 defects.
Fix practical P2 defects.

Create:

```text
validation/R1_REPOSITORY_AUDIT.md
validation/CURSOR_REPOSITORY_TREE_AFTER_CLEANUP.md
validation/CURSOR_FIRST_REVIEW.md
validation/CURSOR_TEST_EVIDENCE.md
validation/CURSOR_END_TO_END_DEMO.md
validation/SECOND_REVIEW_HANDOFF.md
docs/releases/R1_LOCAL_COMPLETE.md
```

## Phase 11 — Final pre-commit verification

Run:

```powershell
git status --short
git status --short --ignored
git diff --check
git diff --stat
git ls-files
python scripts/validation/secret_scan.py
python scripts/validation/prohibited_source_scan.py
```

Inspect every staged path.

Confirm none of these are staged:
- OAuth JSON;
- client secrets;
- `.env.local`;
- credentials;
- tokens;
- private documents;
- generated resumes containing private data;
- Playwright artifacts;
- local logs;
- database backups.

Stage canonical project files:

```powershell
git add -A
git status --short
```

Run the scans again against staged content.

## Phase 12 — Commit directly to main and push

Proceed only when the final release decision is `READY`.

Confirm branch:

```powershell
git branch --show-current
```

It must be:

```text
main
```

Create the initial baseline commit:

```powershell
git commit -m "R1 complete local CareerOS baseline"
```

Push:

```powershell
git push -u origin main
```

If GitHub's default branch is not `main`, set it using GitHub CLI after `main` exists remotely:

```powershell
gh repo edit swap2you/aarohan-careeros --default-branch main
```

Verify:

```powershell
git status
git rev-parse HEAD
git rev-parse origin/main
gh repo view swap2you/aarohan-careeros --json nameWithOwner,visibility,defaultBranchRef,url
```

Local `HEAD` and `origin/main` must match.

Do not create `master`.
If an obsolete remote `master` exists after `main` is established and confirmed, delete it only after verifying that it contains no unique commits:

```powershell
git log main..origin/master --oneline
```

Delete only when that output is empty:

```powershell
git push origin --delete master
```

## Phase 13 — GitHub Actions validation

The push must trigger CI.

Inspect:

```powershell
gh run list --repo swap2you/aarohan-careeros --limit 10
```

Watch the relevant run:

```powershell
gh run watch <RUN_ID> --repo swap2you/aarohan-careeros --exit-status
```

If CI fails:
1. inspect job logs;
2. reproduce locally;
3. fix;
4. rerun all affected local tests;
5. commit the repair to `main`;
6. push;
7. watch CI again.

Continue until required GitHub Actions checks are green.

Do not hide or disable failing checks to obtain green status.

## Final response

Return:

- READY or NOT READY
- repository visibility
- final branch
- remote URL
- final commit SHA
- confirmation that local HEAD equals origin/main
- GitHub Actions run URL and status
- final canonical repository tree
- files moved/archived/deleted
- exact commands executed
- actual test totals and failures
- Docker services and health
- local URLs
- Google OAuth result
- Gmail result
- Drive folder IDs
- generated current artifact paths
- Playwright result
- migration result
- persistence result
- backup/restore result
- secret-scan result
- dependency-scan result
- unresolved defects
- exact local run commands for the user
- exact Cowork UAT command

Do not stop after code generation. Continue until:
- local release gates pass;
- repository is clean;
- `main` is pushed;
- remote and local match;
- GitHub Actions is green;

or a genuine user interaction blocks progress.
