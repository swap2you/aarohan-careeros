# Multi-Agent Validation and UAT

## Principle

Cursor implements. Automated tests prove. Codex and Claude review independently. Cowork performs human-style UAT. None may approve its own assumptions without evidence.

## Cursor evidence package

Produce:

- current status,
- architecture,
- requirements traceability,
- release notes,
- commands and outputs,
- migrations,
- API inventory,
- UI route inventory,
- sample redacted data,
- known risks,
- UAT seed instructions.

## Codex review prompt requirements

Codex must:

- inspect the full repository,
- compare implementation against R2 traceability,
- run tests,
- review migrations,
- identify security and secret risks,
- examine duplicate-protection edge cases,
- review factual-consistency enforcement,
- review assisted-mode hard stops,
- inspect release tags and notes,
- produce findings with severity and file references.

## Claude Code review requirements

Claude Code must:

- independently review architecture and maintainability,
- inspect data flow from connector to UI,
- inspect retry/idempotency,
- inspect scheduler behavior,
- inspect document and Drive linkage,
- inspect Gmail linkage,
- inspect failure modes and observability,
- run available tests,
- produce actionable findings.

## Cowork UAT

Cowork should operate the application as a user and preserve evidence.

Core journey:

1. Start local stack.
2. Sign in.
3. Run an ad hoc search.
4. Confirm source health and run summary.
5. Open a new job.
6. Verify fit/trust explanations.
7. Verify duplicate indicator.
8. Generate a packet.
9. Review resume and cover letter.
10. Verify local and Drive links.
11. Approve packet.
12. Open official application.
13. Use Assisted mode on a supported test/sandbox flow if available.
14. Confirm it stops before submit.
15. Record/mark application.
16. Sync Gmail.
17. Confirm application email linkage.
18. Open company ledger.
19. Attempt duplicate scenario.
20. Confirm warning/block.
21. Generate interview brief.
22. Use Ask Aarohan.
23. Read a section with TTS.
24. Compare UI data to API and database.
25. Record screenshots, defects, and severity.

## Required automated UAT scenarios

- same requisition through two sources,
- same job through employer and aggregator,
- same company/similar role inside 180 days,
- same company/different role,
- vendor submission conflict,
- changed job title/date in generated resume,
- unsupported AI configuration,
- missing API key,
- source timeout/rate limit,
- Drive unavailable,
- Gmail unavailable,
- duplicate Gmail messages,
- expired job,
- unsupported ATS,
- direct URL import,
- unauthorized deep route,
- backend rejection of autonomous mode.

## Sign-off

Release sign-off requires:

- no critical defects,
- no open high-severity data-integrity defects,
- no secret exposure,
- assisted mode cannot submit automatically,
- duplicate hard-block scenarios pass,
- factual-core contradictions are blocked,
- backup/restore succeeds,
- owner completes manual acceptance.
