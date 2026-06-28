# Aarohan CareerOS — Architecture

Supervised, local-first career operations platform. Human approval gates all external actions; no automatic job submission or outbound messaging.

## System overview

```text
Public ATS feeds + remote feeds + dedicated Gmail + manual URLs
                              ↓
                       n8n workflows (optional)
                              ↓
                    FastAPI API (apps/api)
                              ↓
                         PostgreSQL
                              ↓
          deterministic scoring + AI-assisted analysis
                              ↓
             DOCX/PDF generation + Google Drive sync
                              ↓
                      Next.js dashboard (apps/web)
                              ↓
               user approval and external action
```

## Components

| Component | Role | Location |
|-----------|------|----------|
| **web** | Dashboard UI (15 pages), auth shell, approval queues | `apps/web` (Next.js 15, React 19) |
| **api** | REST API, scoring, generation, OAuth, audit | `apps/api` (FastAPI, Python 3.12) |
| **postgres** | Jobs, applications, scores, OAuth tokens, audit | Docker service `postgres:16-alpine` |
| **n8n** | Workflow orchestration (ingestion triggers) | Docker service `n8nio/n8n:1.70.3` |
| **career_vault** | Approved evidence for external claims | `career_vault/` (read-only mount) |
| **config** | Non-secret integration context | `config/` (read-only mount) |

Future production adds `proxy` (Caddy/Nginx) and optional `worker`; neither is required for local R1.

## API surface

Routers under `/api`:

- `auth` — login, session, admin bootstrap
- `jobs` — ingestion, normalization, deduplication, scoring
- `connectors` — job discovery providers, health, ad hoc runs
- `matching` — preferences, match cards, trust/fit explainability
- `documents` — templates, baseline resume, quality validation, answer sheets
- `companies` — company registry, application ledger, duplicate-risk, application modes
- `applications` — packets, approval queue, tracking
- `interviews` — Interview Grilling Machine
- `consulting` — lead intake and proposals
- `career_vault` — evidence registry sync
- `integrations` — Google OAuth, Gmail sync, Drive folders
- `workflows` — n8n triggers (schedules disabled locally)
- `ops` — health, AI spend, analytics
- `validation` — validation center endpoints

Health: `GET /health`, `GET /ready` (DB connectivity).

## Data flow

### Job pipeline

1. **Ingest** — Greenhouse/Lever feeds, manual URL, Gmail labels, or fixtures.
2. **Normalize** — Pydantic validation, HTML sanitization, deduplication keys, company linkage.
3. **Score** — Deterministic rules (salary, remote, freshness, role fit); AI only for ambiguous analysis within budget caps.
4. **Duplicate check** — Evaluate RED/AMBER/GREEN risk against application ledger (requisition, URL, ATS ID, cadence).
5. **Generate** — Resume/cover letter from Career Vault evidence only; factual-core hash validated.
6. **Approve** — User edits, holds, rejects, or approves in dashboard; duplicate recheck on approve/submit.
7. **Track** — Ledger and audit events; external submit never automatic.

### Google integration

1. User connects via Settings → Google OAuth (`/api/integrations/google/connect`).
2. Callback stores encrypted refresh token in PostgreSQL.
3. Gmail read-only sync processes labeled messages; Drive syncs generated docs to folder tree.

### Security boundaries

- External content (JDs, emails, web pages) is untrusted input.
- OAuth tokens encrypted with `TOKEN_ENCRYPTION_KEY`.
- Secrets live in PowerShell SecretStore locally, never in Git.
- `SCHEDULING_ENABLED=false` and `ENABLE_EXTERNAL_EMAIL_SEND=false` in local-first mode.

## Storage

| Store | Contents |
|-------|----------|
| PostgreSQL | Jobs, scores, applications, OAuth tokens, interviews, consulting leads, audit events |
| Google Drive | Generated documents, application packets (`config/integration-context.yml` folder tree) |
| Docker volume `generated_docs` | Local generated DOCX/PDF before Drive upload |
| Git | Source, config templates, Career Vault structure |

## AI usage

Model APIs (via OpenRouter when configured) for: fit analysis, resume tailoring, company research, interview prep, consulting proposals.

Deterministic code for: parsing, normalization, deduplication, salary logic, state machines, audit logging. Hard monthly cap enforced in API settings.

## Local vs production

Local-first mode disables scheduled workflows, external email send, and deployment automation. See `docs/runbooks/LOCAL_DEVELOPMENT.md` for startup and `docs/operations/MAINTENANCE.md` for rotation and updates.
