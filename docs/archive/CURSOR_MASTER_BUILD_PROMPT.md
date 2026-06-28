# Cursor Master Build Prompt

You are the primary implementation agent for Aarohan CareerOS.

Read:
- START_HERE.md
- PROJECT_CHARTER.md
- AGENTS.md
- all docs
- all config
- all Career Vault files
- all validation prompts

## Build objective
Create the complete end-to-end V1 application in this repository.

## Required stack
- Python 3.12
- FastAPI
- Pydantic
- PostgreSQL
- SQLAlchemy
- Alembic
- Next.js
- TypeScript
- n8n
- Docker Compose
- GitHub Actions
- pytest
- Playwright
- DOCX and PDF generation
- Google Drive integration interface
- dedicated Gmail integration interface

## Required modules
1. Career Vault
2. Job ingestion
3. Normalization and deduplication
4. Salary, remote, role, stability, AI-alignment, and evidence scoring
5. Application packet generation
6. Approval queue
7. Application tracker
8. Recruiter signal monitor
9. Interview Grilling Machine
10. Consulting lead pipeline
11. Analytics
12. AI usage and cost control
13. Audit logs
14. Authentication
15. Backup, health, deployment, and rollback

## Build style
Build the full architecture now, but use internal gates:
- Gate A: foundation
- Gate B: ingestion and scoring
- Gate C: documents and approvals
- Gate D: interviews and consulting
- Gate E: cloud and CI/CD
- Gate F: validation

Do not wait for a new user prompt between gates unless there is a real blocker.
Do not create a superficial mockup.
Do not leave core behavior as empty placeholders.

## Safety
- no LinkedIn scraping;
- no Indeed scraping;
- no final submission automation;
- no automatic external messaging;
- no credential storage in Drive or Git;
- no fabricated candidate history;
- no claims without evidence;
- no unlimited model calls.

## First response
Before editing, return:
1. architecture summary;
2. assumptions;
3. complete proposed tree;
4. dependencies;
5. risks;
6. gate plan;
7. exact commands.

Then implement.

## Completion report
Return:
- files created;
- migrations;
- tests and exact results;
- local URLs;
- seed-data demo;
- Docker status;
- GitHub Actions status;
- security status;
- AI budget status;
- known limitations;
- Codex audit command;
- deployment instructions.

Do not commit or deploy until approved.
