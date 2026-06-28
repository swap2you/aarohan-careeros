# R2 Risk Register

| ID | Risk | Impact | Mitigation | Owner | Status |
|----|------|--------|------------|-------|--------|
| R-01 | Direct-main commits without PR review | Rollback difficulty | Annotated tags, release gates, rollback docs | Cursor | OPEN |
| R-02 | `drive.file` cannot access manual Drive root | Drive sync fails | App-created root flow in Settings | Cursor | MITIGATED |
| R-03 | Missing external API keys | Connector gaps | NOT_CONFIGURED state + fixtures | Cursor | OPEN |
| R-04 | Duplicate application reputational risk | Employer rejection | R2.1 ledger + hard blocks | Cursor | PLANNED |
| R-05 | AI hallucination in documents | False claims | Evidence vault + factual-core validator | Cursor | PLANNED |
| R-06 | Autonomous apply bypass | Policy violation | Backend rejection + locked UI | Cursor | PLANNED |
| R-07 | n8n schema in full DB backup | Restore noise | Career-only dump (R2.12) | Cursor | OPEN |
| R-08 | GitHub Actions not verified locally | CI drift | Verify after each push | Owner | OPEN |
