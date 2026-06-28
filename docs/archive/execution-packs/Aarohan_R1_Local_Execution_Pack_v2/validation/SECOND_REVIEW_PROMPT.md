# Independent Second Review — R1 Local

Read:
- all current architecture/policy files
- `validation/R1_BASELINE_AUDIT.md`
- `validation/CURSOR_FIRST_REVIEW.md`
- `validation/CURSOR_TEST_EVIDENCE.md`
- `validation/CURSOR_END_TO_END_DEMO.md`
- `validation/SECOND_REVIEW_HANDOFF.md`

Execute tests independently.

Verify:
- no secret in Git or logs
- OAuth JSON outside source tree
- correct Google project/account
- minimal runtime scopes
- CSRF state
- refresh/revoke
- encrypted token storage
- Gmail read-only behavior
- optional test-send allowlist
- Drive folder/file tracking
- migrations
- scoring
- Career Vault evidence
- ATS outputs
- interview workspace
- consulting
- budget caps
- manual approval boundaries
- Docker
- backup/restore
- E2E

Return PASS or STOP with command evidence and exact fixes.
Do not deploy or push.
