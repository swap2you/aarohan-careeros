# UAT Runbook

Manual user acceptance testing for Aarohan CareerOS. Primary scenario list: `validation/COWORK_UAT_PROMPT.md`.

## Roles

| Role | Responsibility |
|------|----------------|
| **Tester (Cowork / human)** | Execute journeys, record PASS/FAIL |
| **Operator** | Start stack, OAuth, fixtures |
| **Reviewer** | Sign off via `validation/CHATGPT_RELEASE_SIGNOFF.md` |

## Pre-flight

1. Bootstrap and secrets initialized.
2. Stack running: `powershell -File .\scripts\local\Start-Aarohan.ps1 -Detached`
3. Validation green: `powershell -File .\scripts\local\Test-Aarohan.ps1`
4. Sign in at http://localhost:3000:
   - Email: `swapnilpatil.tech@gmail.com`
   - Password: `TempLocal123!` (local only; reset via `scripts/local/Reset-LocalAdmin.ps1`)
5. Open http://localhost:3000/settings — connect Google as `swapnilpatil.tech@gmail.com` if not already connected.
6. For offline UAT without Google, set `OAUTH_FIXTURE_MODE=true` and use `/gmail/sync-fixture`.

Document environment (fixture vs live) in UAT evidence.

## R1 checkpoint snapshot (2026-06-28)

| Gate | Status |
|------|--------|
| Docker stack | PASS |
| Migrations | PASS (`0003_fk_not_null`) |
| pytest | 29 passed, 1 skipped |
| Secret / prohibited scans | PASS |
| Live OAuth | PASS |
| Drive app-root + subfolders | PASS |
| Packet + Drive upload | PASS |
| Playwright smoke | PASS |
| GitHub Actions | **NOT VERIFIED** |

Active Drive root: `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr` (app-created; manual root inaccessible with `drive.file`).

## Known gaps (before production signoff)

- Document quality needs improvement
- ATS templates need validation
- Real Gmail content still needs more test data
- GitHub Actions needs verification
- Playwright coverage needs expansion
- Backup/restore n8n schema noise
- UI polish pending

See `validation/CURSOR_TEST_EVIDENCE.md` before Cowork UAT.

## User journeys

Execute each scenario from `validation/COWORK_UAT_PROMPT.md`:

| # | Journey | Pass criteria |
|---|---------|---------------|
| 1 | Ingest fresh public job | Job appears in pipeline with source metadata |
| 2 | Normalize and deduplicate | Duplicate suppressed; fields normalized |
| 3 | Salary and remote scoring | Scores visible with transparent breakdown |
| 4 | Generate grounded packet | Resume/cover letter cites Career Vault evidence only |
| 5 | Approve, edit, hold, reject | Queue states transition; edits persist |
| 6 | Mark submitted | Application tracked; no automatic external submit |
| 7 | Ingest recruiter response | Gmail/fixture signal creates recruiter entry |
| 8 | Full interview pack | Questions, frameworks, exercises generated |
| 9 | Exercises and weak areas | Progress tracked in Interview section |
| 10 | Consulting lead intake | Lead scored and categorized |
| 11 | Service recommendation + proposal | Proposal grounded; approval required |
| 12 | Analytics and audit logs | Events match actions taken in session |
| 13 | Failures and retries | Errors show remediation; retry succeeds |
| 14 | No external action without approval | No email send, submit, or Drive upload without explicit approval |

## Per-journey steps (operator hints)

**Jobs (1–3):** Jobs page → ingest via Greenhouse/Lever URL, manual paste, or fixture. Open job detail → verify score components.

**Packets (4–6):** Applications → generate packet → review claims against Career Vault → approve or edit → mark submitted manually.

**Recruiter (7):** Integrations → Gmail sync (or sync-fixture) → verify signal on Applications or Jobs.

**Interviews (8–9):** Interviews → create pack from application → run exercise → mark weak areas.

**Consulting (10–11):** Consulting → new lead → generate recommendation → proposal draft → hold for approval.

**Ops (12–13):** Ops / Validation pages → audit log entries for each action. Deliberately trigger OAuth disconnect or invalid input; confirm remediation text.

**Approval boundary (14):** Confirm `ENABLE_EXTERNAL_EMAIL_SEND=false` — test send produces `.eml` only. No auto-submit buttons succeed without human confirmation.

## Evidence to capture

For each journey:

- Screenshot or screen recording
- Relevant audit log entry IDs or timestamps
- API response snippets (no secrets)
- Generated document filenames (not full resume content in shared logs)

Store under `validation/` with date prefix, e.g. `validation/UAT_EVIDENCE_2026-06-27.md`.

## UAT report template

Return per `COWORK_UAT_PROMPT.md`:

```markdown
# UAT Report — YYYY-MM-DD

**Environment:** local Docker / fixture | live Google
**Tester:**

## Result: PASS | FAIL | CONDITIONAL PASS

### Failed scenarios
- (list numbers and brief reason)

### Evidence
- (links to files)

### Usability defects
- (UI/UX issues, non-blocking)

### Missing requirements
- (gaps vs product scope)

## Release recommendation
GO | CONDITIONAL GO | STOP
```

## Conditional pass rules

CONDITIONAL PASS allowed only when:

- Failures are documented P2/P3 with workaround
- No P0/P1 security or approval-boundary failures
- Scoring evidence grounding verified for all generated claims

## Post-UAT

1. File report in `validation/`.
2. Link from `validation/SECOND_REVIEW_HANDOFF.md` if applicable.
3. Run backup if UAT created valuable local data: `Backup-Aarohan.ps1`.
4. Await ChatGPT release signoff before deploy.

## Related

- Scenario source: `validation/COWORK_UAT_PROMPT.md`
- Release gates: `docs/09_RELEASE_GATES.md`
- OAuth setup: `docs/runbooks/GOOGLE_OAUTH.md`
