# Architecture

```text
Public ATS feeds + remote feeds + dedicated Gmail + forwarded URLs
                              ↓
                       n8n workflows
                              ↓
                    FastAPI application
                              ↓
                         PostgreSQL
                              ↓
          deterministic scoring + AI-assisted analysis
                              ↓
             DOCX/PDF generation + Google Drive
                              ↓
                      Next.js dashboard
                              ↓
               user approval and external action
```

## Containers
- `api`: FastAPI
- `web`: Next.js
- `postgres`: PostgreSQL
- `n8n`: workflow orchestration
- `proxy`: Caddy or Nginx
- `worker`: optional background worker only if required by load
- `redis`: deferred unless the queue architecture requires it

## Scheduling
- n8n for business workflows;
- GitHub Actions for CI/CD;
- cron for backups and health checks only;
- no Hermes in V1;
- no dependence on a desktop app staying open.

## Storage
- PostgreSQL: jobs, scores, applications, approvals, interviews, leads, audits.
- Google Drive: generated documents and sanitized portfolio assets.
- GitHub: source code and non-secret configuration.
- Environment variables / GitHub Secrets: credentials.

## AI
Use model APIs only for:
- ambiguous fit analysis;
- resume tailoring;
- company research synthesis;
- interview preparation;
- consulting proposals.

Use deterministic code for:
- parsing;
- normalization;
- deduplication;
- freshness;
- salary range logic;
- state transitions;
- audit logging.
