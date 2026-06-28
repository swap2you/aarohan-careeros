# R2 Release Roadmap

The program is sequential, but missing external credentials are non-blocking.

## R2.0 — Baseline, Governance, and CI

Tag: `r2.0.0`

Deliverables:

- verify repository and checkpoint,
- verify GitHub Actions,
- baseline all local services and tests,
- inventory configuration and secrets references,
- create program board, traceability, risk register, decisions, release-note template,
- document current architecture and runbooks,
- add a single full local verification command.

Exit gate:

- existing behavior preserved,
- baseline evidence recorded,
- secret and prohibited-source scans pass.

## R2.1 — Application Ledger and Duplicate Protection

Tag: `r2.1.0`

Deliverables:

- canonical companies and company aliases,
- company domains and ATS identities,
- normalized jobs and source records,
- application ledger and application events,
- vendor/recruiter submission channel,
- duplicate-risk engine,
- 180-day caution policy,
- exact requisition hard block,
- resume factual-core validator,
- UI indicators and override audit trail.

This release comes before broad job ingestion because duplicate protection must exist before applications scale.

## R2.2 — Job Discovery Connectors

Tag: `r2.2.0`

Deliverables:

- provider interface,
- Greenhouse,
- Ashby,
- Lever,
- Remotive,
- Remote OK,
- allowed RSS provider,
- Adzuna adapter,
- Jooble adapter,
- USAJOBS adapter,
- source health and configuration screen,
- retries, rate limits, provenance, attribution,
- fixtures and contract tests,
- ad hoc runs and scheduled runs.

Unconfigured key-based connectors must appear disabled, not broken.

## R2.3 — Trust, Matching, and Explainability

Tag: `r2.3.0`

Deliverables:

- profile/preferences,
- hard filters,
- employer/ATS verification,
- trust score with reasons,
- fit score with reasons,
- role-family classification,
- location/remote/hybrid handling,
- compensation handling,
- work-authorization and travel handling,
- duplicate-source merging,
- job aging/expiration,
- human-readable job cards.

## R2.4 — Career Evidence Vault and Document Quality

Tag: `r2.4.0`

Deliverables:

- approved career-fact store,
- stable baseline resume,
- job-to-evidence mapping,
- professional templates,
- tailored resume,
- cover letter,
- application answer sheet,
- claim validation,
- ATS readability diagnostics,
- DOCX/PDF text extraction comparison,
- versioned prompts/templates/models,
- deterministic fallback when AI is unavailable.

## R2.5 — Manual Application Workflow

Tag: `r2.5.0`

Deliverables:

- application packet review,
- approve/reject/regenerate,
- local and Drive storage,
- clickable artifact links,
- official Apply button,
- application-state machine,
- event timeline,
- no external field filling,
- duplicate-risk recheck immediately before marking applied.

This is the first complete safe vertical slice.

## R2.6 — Assisted Apply

Tag: `r2.6.0`

Deliverables:

- supported-ATS detection,
- browser-assisted workflow or extension architecture,
- prefilled profile answers,
- resume/cover-letter selection,
- application question review,
- screenshot/evidence capture,
- stop before external submit,
- unsupported-site fallback,
- autonomous mode locked in UI and API.

Do not bypass CAPTCHAs.

## R2.7 — Gmail Lifecycle and Alerts

Tag: `r2.7.0`

Deliverables:

- parse job alerts from LinkedIn, Indeed, Dice, Glassdoor, and other configured senders,
- normalize alert jobs,
- deduplicate alert jobs against API jobs,
- classify recruiter outreach, application confirmations, rejections, interviews, offers, and follow-ups,
- link messages to company/job/application,
- thread-aware deduplication,
- follow-up reminders,
- user-correctable classification.

## R2.8 — Interview and Recruiter Intelligence

Tag: `r2.8.0`

Deliverables:

- company brief,
- recruiter/contact profile,
- interview brief,
- likely questions,
- role-specific preparation,
- STAR-story selection from approved facts,
- compensation/negotiation preparation,
- interview schedule linkage,
- document and Drive links.

## R2.9 — Ask Aarohan and OpenAI TTS

Tag: `r2.9.0`

Deliverables:

- question answering over jobs, applications, companies, recruiters, interviews, and documents,
- transparent citations to internal records,
- read-only default,
- internal full-SQL mode with mutation confirmation and audit,
- read-aloud for resume, cover letter, company brief, and interview brief,
- speed, pause, resume, and section selection,
- AI-off fallback states.

## R2.10 — Modern Product UI

Tag: `r2.10.0`

Deliverables:

- coherent design system,
- professional login,
- command center,
- modern job inbox and details,
- pipeline,
- document center,
- integrations center,
- Ask Aarohan UI,
- responsive and accessible design,
- restrained motion,
- plain-English statuses,
- no raw JSON in standard views.

Functional workflows must not be sacrificed for animation.

## R2.11 — Cloud and SaaS Readiness Contract

Tag: `r2.11.0`

Deliverables:

- cloud deployment decision record,
- protected-route design,
- Google login design,
- email/password and reset design,
- tenant-boundary plan,
- storage/secrets/worker architecture,
- privacy, retention, export, deletion, and disclaimer requirements,
- subscription-model placeholder,
- production environment checklist.

Do not deploy in this release.

## R2.12 — Cleanup, Restructure, and Hardening

Tag: `r2.12.0`

Deliverables:

- remove dead code and generated trash,
- normalize repository structure,
- format and lint,
- remove unused dependencies,
- verify migration chain,
- backup/restore test,
- error-path and retry tests,
- security checks,
- documentation link validation,
- complete release-history audit,
- clean tree report.

## R2.13 — Independent Review, UAT, and Release Candidate

Tag: `r2.13.0-rc1`

Deliverables:

- Cursor self-review,
- Codex review package,
- Claude Code review package,
- Cowork UAT package,
- API/DB/UI reconciliation,
- end-to-end Playwright journeys,
- UAT findings and remediation,
- release sign-off,
- rollback instructions,
- July 4 weekend UAT readiness report.

## Future releases

- cloud deployment,
- multi-tenant SaaS,
- billing/subscriptions,
- autonomous application research,
- additional licensed data sources,
- realtime voice agent,
- mobile app,
- employer/recruiter CRM extensions.
