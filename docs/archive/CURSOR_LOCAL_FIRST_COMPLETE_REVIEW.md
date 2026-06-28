# Cursor Local-First Completion and First Review

You are the primary implementation, integration, QA, security, documentation, and first-review agent for Aarohan CareerOS.

Read the entire repository before editing:
- START_HERE.md
- PROJECT_CHARTER.md
- AGENTS.md
- docs/
- config/
- career_vault/
- prompts/
- validation/
- all application, test, Docker, n8n, and GitHub Actions files

## Immediate operating mode

This phase is LOCAL-FIRST.

Do not deploy.
Do not push.
Do not enable production schedules.
Do not require Hostinger.
Do not require Hermes.
Do not require live GitHub deployment secrets.

All core workflows must be runnable manually from the dashboard.

## User experience requirement

The user must be able to:

1. Start the full application with one PowerShell command.
2. Open the dashboard.
3. Configure or verify local integrations from a Settings page.
4. Click a button to ingest jobs.
5. Review scoring.
6. Select jobs.
7. Generate resume, cover letter, recruiter note, and fit analysis.
8. Preview and download correctly formatted DOCX and PDF files.
9. Approve, hold, edit, or reject.
10. Mark an application manually submitted.
11. Create a full interview-preparation workspace.
12. Run interview exercises.
13. Review consulting opportunities.
14. Run a full local validation from the dashboard or one PowerShell command.
15. Stop the environment with one PowerShell command.

## Internal gates

Complete all gates without waiting for another prompt unless a real credential, OAuth consent, billing action, or destructive action requires the user.

### Gate 1 — Secret hygiene and local bootstrap

Implement:
- PowerShell SecretManagement and SecretStore integration;
- `scripts/local/Initialize-AarohanSecrets.ps1`;
- `scripts/local/Start-Aarohan.ps1`;
- `scripts/local/Stop-Aarohan.ps1`;
- `scripts/local/Test-Aarohan.ps1`;
- no live credential file inside the repository;
- clear secret-name inventory;
- safe missing-secret behavior;
- no secret values in logs;
- `.env.example` containing names only.

The start script must load secrets from the local vault into the process at runtime. It must not write them into repository files.

Remove hard-coded deployable default credentials.
Implement secure first-run administrator creation.

### Gate 2 — Database correctness

Fix Alembic so the complete schema is migration-controlled.

Requirements:
- complete initial migration for all tables, indexes, constraints, and relationships;
- no production dependence on `Base.metadata.create_all()`;
- migration test against a blank PostgreSQL database;
- upgrade and downgrade verification;
- durable data after container restart.

### Gate 3 — Local integrations

Implement real local OAuth flows for:
- dedicated Gmail account;
- Google Drive.

Requirements:
- connect/disconnect UI;
- minimum scopes;
- encrypted token storage;
- disabled mode when not configured;
- fixture mode for automated tests;
- no primary Gmail requirement;
- no token logging.

Keep LinkedIn and Indeed as email-alert/manual-link sources only.

### Gate 4 — Manual dashboard workflows

Disable schedules by default.

Add explicit dashboard controls:
- Ingest approved public sources
- Import forwarded URL
- Import fixture
- Score all new jobs
- Generate selected packets
- Prepare for interview
- Run local validation
- View validation report

The dashboard must show progress, success, failure, and retry information.

### Gate 5 — Resume and application quality

Research current ATS-safe resume practices using credible current sources. Record sources and retrieval dates in `docs/research/ATS_RESUME_RESEARCH.md`.

Do not copy copyrighted templates.

Create at least three resume profiles:
1. QE Leadership
2. Quality / Test Platform Architect
3. AI-Enabled QE / Agent Evaluation

For each generated packet:
- ATS-safe single-column DOCX;
- visually clean PDF;
- standard headings;
- no icons, text boxes, charts, or critical information in headers/footers for the ATS version;
- evidence-backed claims only;
- keyword mapping to the job description;
- change report;
- missing-evidence warnings;
- file naming convention;
- document metadata;
- text-extraction round-trip validation;
- formatting checks;
- page-count checks;
- duplicate and unsupported-claim checks.

Add a dashboard preview before download or approval.

### Gate 6 — Interview Grilling Machine

For a selected job, generate and persist:
- company briefing;
- role outcome map;
- JD/resume gap map;
- recruiter questions;
- hiring-manager questions;
- technical deep dives;
- system-design scenarios;
- automation, API, performance, CI/CD, data, and cloud questions;
- AI-enabled QE, agentic AI, prompt/context engineering, MCP, LLM evaluation, RAG evaluation, guardrails, observability, and human-in-the-loop questions when relevant;
- leadership questions;
- behavioral questions;
- verified STAR story suggestions;
- honest gap answers;
- exercises and take-home simulations;
- answer-scoring rubric;
- weak-area tracking;
- seven-day plan;
- voice mock-interview export prompt.

### Gate 7 — Consulting pipeline

Complete:
- lead intake;
- problem classification;
- service matching;
- lead score;
- proposal draft;
- case-study mapping;
- follow-up status;
- dashboard reporting.

No automatic outreach.

### Gate 8 — Full test and security pass

Upgrade vulnerable dependencies.

Run and fix:
- backend formatting and linting;
- frontend formatting and linting;
- backend unit tests;
- PostgreSQL integration tests;
- authentication and authorization tests;
- scoring boundary tests;
- evidence-grounding tests;
- DOCX/PDF generation tests;
- Gmail and Drive fixture tests;
- interview-pack tests;
- consulting tests;
- budget-cap tests;
- prompt-injection tests;
- unsafe-HTML tests;
- Playwright E2E;
- secret scan;
- prohibited-source scan;
- Docker build;
- full Docker startup;
- health checks;
- restart persistence;
- backup and restore;
- end-to-end demo.

## Required end-to-end proof

Prove locally:

1. Secure administrator initialization.
2. Login.
3. Fixture ingestion.
4. At least one live permitted public feed ingestion.
5. Deduplication.
6. Salary, remote, role, AI, stability, and evidence scoring.
7. Selection of a job.
8. DOCX and PDF packet generation.
9. Evidence mapping.
10. Preview.
11. Approval.
12. Manual-submission status.
13. Recruiter fixture ingestion.
14. Interview pack generation.
15. Consulting lead generation.
16. Audit events.
17. AI budget enforcement.
18. Restart persistence.
19. Backup and restore.

## Cursor first-review requirement

After implementation, review your own work as separate internal reviewers:

- Product reviewer
- Security reviewer
- Database reviewer
- Backend reviewer
- Frontend/E2E reviewer
- Document/ATS reviewer
- DevOps reviewer
- Career-truthfulness reviewer

Fix all P0 and P1 findings. Fix reasonable P2 findings.

Write:
- `validation/CURSOR_FIRST_REVIEW.md`
- `validation/CURSOR_LOCAL_TEST_EVIDENCE.md`
- `validation/SECOND_REVIEW_HANDOFF.md`

## Completion report

Do not claim completion from code inspection alone.

Return:
- files changed;
- architecture changes;
- exact commands executed;
- actual test counts and results;
- Docker service status;
- local URLs;
- OAuth actions still requiring the user;
- screenshots or generated sample paths;
- unresolved defects;
- second-review readiness: READY or NOT READY.

Do not commit, push, or deploy.
