# Master Cursor Execution Prompt

You are the primary implementation agent for Aarohan CareerOS.

Repository:

`C:\Development\Workspace\aarohan-careeros`

Remote:

`https://github.com/swap2you/aarohan-careeros`

Required branch:

`main`

Known working checkpoint:

`aed228d583e0b6a7760eb6091c82883cda5e5426`

The project is already operational locally. Docker, FastAPI, Next.js, PostgreSQL, n8n, Google OAuth, Google Drive, Gmail read integration, resume/PDF/DOCX generation, local authentication, and baseline tests are working. Do not rebuild infrastructure merely because a different design is possible.

## Mission

Implement the R2 program end to end, release by release, without waiting for another planning conversation.

Build a professional local-first career operating system that supports legitimate job discovery, explainable matching, duplicate-application prevention, tailored document generation, manual and assisted application workflows, Gmail lifecycle tracking, interview preparation, Ask Aarohan, OpenAI TTS, modern UI, future cloud readiness, cleanup, hardening, and UAT evidence.

## Authority

You have authority to inspect and modify the entire repository, database schema, migrations, backend, frontend, tests, scripts, Docker files, local configuration templates, and documentation.

You may run all local commands and tests required.

Do not expose or commit secrets. Do not delete user data or reset local volumes unless a backup is created and the reason is documented. Do not alter OAuth scopes unless a feature genuinely requires it.

Work directly on `main`. Do not create branches or pull requests.

## First actions

1. `cd C:\Development\Workspace\aarohan-careeros`
2. Confirm the current branch is `main`.
3. Inspect `git status`, remote, latest commits, tags, and the baseline commit.
4. Never discard uncommitted user work.
5. Pull only with a safe fast-forward strategy.
6. Verify GitHub Actions status for the baseline through available GitHub tooling or repository UI evidence.
7. Run the existing baseline:
   - secret scan,
   - prohibited-source scan,
   - backend tests,
   - frontend lint/type/build checks,
   - Playwright,
   - local health checks.
8. Inspect the actual architecture and existing documentation before writing code.
9. Create or update:
   - `docs/00-CURRENT-STATUS.md`
   - `docs/program/R2-PROGRAM-BOARD.md`
   - `docs/program/R2-DECISIONS.md`
   - `docs/program/R2-TRACEABILITY-MATRIX.md`
   - `docs/program/R2-RISK-REGISTER.md`
   - `docs/releases/`
10. Record the true baseline. Do not claim a check passed unless it actually ran and passed.

## Continuous execution rule

Proceed through every release in `02-RELEASE-ROADMAP.md`.

Do not stop because an external key is missing. Implement the connector contract, configuration validation, tests with fixtures/mocks, disabled-state UI, and setup documentation, then continue.

Stop only for a genuine destructive blocker that cannot be safely resolved locally. Document the blocker precisely and continue every independent task.

## Release protocol

For each release:

1. Read its scope and acceptance criteria.
2. Update the program board to `IN_PROGRESS`.
3. Implement the smallest coherent production-quality solution.
4. Add migrations and rollback notes.
5. Add unit, integration, API, and UI tests appropriate to the change.
6. Run the full release gate in `09-RELEASE-GATE-AND-GIT-POLICY.md`.
7. Update:
   - current status,
   - traceability matrix,
   - risk register,
   - architecture docs,
   - operational runbooks,
   - release notes.
8. Set the program-board release status to `DONE` only when evidence exists.
9. Commit directly to `main`.
10. Push `main`.
11. Create the specified annotated release tag.
12. Push the tag.
13. Record commit SHA, tag, tests, known limitations, and rollback command.
14. Continue to the next release.

Do not batch multiple release tags onto one unvalidated final commit.

## Job-source policy

Build a provider interface with normalized records, provenance, rate-limit handling, retries, source health, attribution, and fixtures.

Initial no-key sources:

- Greenhouse public job boards
- Ashby public job postings
- Lever public postings
- Remotive
- Remote OK
- supported RSS feeds only where allowed

Configured-key sources:

- Adzuna
- Jooble
- USAJOBS

LinkedIn, Indeed, Dice, and Glassdoor:

- do not scrape,
- ingest job-alert emails through Gmail,
- support manual URL import,
- support a future browser helper,
- link to original postings.

Prefer employer or ATS postings over aggregator copies.

## Application modes

Implement these modes:

### MANUAL

Generate, validate, store, and present the application packet. Open the official application URL. Do not fill or submit the external form.

### ASSISTED

For explicitly supported ATS platforms, prepare/prefill fields and uploads, then stop at the final review screen. Require the user to press the external submit button.

### AUTONOMOUS_LOCKED

Display as a future mode with a warning and disabled control. It must not submit in R2. The backend must also reject autonomous submission even if the UI is bypassed.

## Duplicate-application prevention

Implement the policy in `05-DUPLICATE-APPLICATION-AND-RESUME-CONSISTENCY.md`.

Minimum requirements:

- canonical company identity,
- aliases, domains, subsidiaries, and ATS board identity,
- canonical requisition and external job IDs,
- normalized role/title,
- description similarity/fingerprint,
- source and vendor channels,
- application ledger,
- representation/vendor history,
- configurable 180-day caution window,
- exact requisition hard block,
- same-company and similar-role warnings,
- active-application caps,
- immutable resume factual core,
- resume-difference validation,
- explicit override with reason and audit event,
- visible conflict indicator before packet approval and before assisted apply.

## Document storage and naming

Implement `06-DOCUMENT-NAMING-STORAGE-AND-LINKING.md`.

Each generated packet must:

- belong to exactly one normalized job,
- have version history,
- retain source job snapshot,
- retain model/prompt/template versions,
- retain approval and usage status,
- store local and Drive locations,
- expose clickable links in the UI,
- support resume, cover letter, interview brief, company brief, recruiter brief, and application-answer sheet,
- never rely only on a filename to establish identity.

## AI implementation

Use model names through configuration and a model registry. Do not hardcode a model across the codebase.

Use a high-capability model only where quality matters. Use a smaller economical model for extraction, classification, summaries, and email categorization.

The application must function in deterministic fallback mode when OpenAI is not configured. It should clearly show which AI features are unavailable.

Use approved career facts as the source of truth. Generated text may reframe or prioritize facts but may not invent them.

Add OpenAI TTS for read-aloud after core document generation is correct.

## Database and Ask Aarohan

Local development code and migrations may access the full database.

Ask Aarohan may support full SQL capability in internal mode, but:

- log every query,
- show the tables/records used,
- run mutations in transactions,
- require an explicit in-product confirmation before `UPDATE`, `DELETE`, `INSERT`, DDL, or bulk changes,
- prohibit secret-table exposure,
- provide a read-only default mode,
- create backups before destructive maintenance.

This is an internal tool, but accidental corruption still wastes time.

## UI requirements

Create a coherent modern design system rather than isolated styled pages.

Required screens:

- Login
- Command Center
- Job Inbox
- Job Detail
- Search and Schedule Manager
- Application Packet
- Application Pipeline
- Companies and Duplicate-Risk Ledger
- Recruiters
- Interviews
- Documents
- Integrations
- Ask Aarohan
- Settings
- Audit and Run History

UI rules:

- no raw JSON in normal views,
- plain-English states and errors,
- technical payloads only in an optional details drawer,
- restrained meaningful motion,
- responsive layout,
- accessible controls,
- keyboard navigation,
- skeleton states,
- empty states,
- clear source and trust labels,
- visible local/Drive document links,
- one-click copy for application answers,
- final-submit warning in assisted mode.

Use the existing frontend stack unless there is a concrete reason to add a dependency. Avoid a full rewrite.

## Cloud and SaaS readiness

Do not deploy now.

Prepare architecture and documentation so a later release can support:

- protected cloud routes,
- Google login,
- email/password login,
- password reset,
- secure sessions,
- tenant-aware data,
- encrypted secrets,
- object storage,
- worker/scheduler separation,
- observability,
- backups,
- privacy controls,
- terms/disclaimers,
- subscription plans.

All routes except explicitly public authentication/health assets must be designed to redirect unauthenticated users to login in cloud mode.

Do not add multi-tenant complexity to local workflows prematurely. Document interfaces and migration path.

## Testing and independent validation

Create deterministic evidence that Codex, Claude Code, and Claude Cowork can follow.

Add:

- requirements traceability,
- architecture validation checklist,
- security checklist,
- data consistency checks,
- API/DB/UI reconciliation checks,
- Playwright UAT journeys,
- document extraction checks,
- local/Drive artifact checks,
- Gmail sync checks,
- duplicate-application scenarios,
- failure and retry scenarios.

Do not use an AI review as a substitute for automated tests.

## Final cleanup release

The final engineering release before UAT must:

- remove dead code and abandoned experiments,
- remove generated output from Git,
- normalize folder structure,
- update `.gitignore`,
- run formatters and linters,
- remove unused dependencies,
- check database migration history,
- validate backup/restore,
- scan secrets and prohibited source code,
- validate documentation links,
- ensure all release tags and notes exist,
- produce a clean repository tree report.

## Final output expected from you

At completion, report:

- final branch and commit SHA,
- all release tags,
- all tests and results,
- source connectors and configuration status,
- external keys still required,
- migrations applied,
- local URLs,
- user workflow instructions,
- known limitations,
- UAT evidence location,
- exact rollback point,
- cloud-readiness items deferred,
- whether the product is ready for July 4 weekend UAT.

Begin now with R2.0. Do not wait for another planning response.
