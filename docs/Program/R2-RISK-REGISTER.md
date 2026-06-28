# R2 Risk Register

| ID | Risk | Impact | Mitigation | Owner | Status |
|----|------|--------|------------|-------|--------|
| R-01 | Direct-main commits without PR review | Rollback difficulty | Annotated tags, release gates, rollback docs | Cursor | OPEN |
| R-02 | `drive.file` cannot access manual Drive root | Drive sync fails | App-created root flow in Settings | Cursor | MITIGATED |
| R-03 | Missing external API keys | Connector gaps | NOT_CONFIGURED state + fixtures | Cursor | MITIGATED |
| R-04 | Duplicate application reputational risk | Employer rejection | R2.1 ledger + hard blocks | Cursor | MITIGATED |
| R-05 | AI hallucination in documents | False claims | Evidence vault + factual-core validator | Cursor | MITIGATED (baseline) |
| R-06 | Autonomous apply bypass | Policy violation | Backend rejection + locked UI | Cursor | MITIGATED |
| R-07 | n8n schema in full DB backup | Restore noise | Career-only dump (R2.12) | Cursor | OPEN |
| R-08 | GitHub Actions not verified locally | CI drift | `gh auth login` then verify after each push | Owner | MITIGATED (run 28333913718 green) |
| R-09 | Live PostgreSQL duplicate path drift | False GREEN on duplicates | `test_duplicate_risk_postgres.py` in CI with Postgres service | Cursor | MITIGATED (R2.5) |
| R-10 | Google Drive live session not gate-tested | Upload proof gap | Owner OAuth step documented in R2.5.0 release notes | Owner | OPEN |
