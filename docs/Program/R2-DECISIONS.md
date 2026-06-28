# R2 Program Decisions

| ID | Date | Decision | Rationale |
|----|------|----------|-----------|
| D-R2-001 | 2026-06-28 | Work directly on `main`; annotated tags per release | Owner-approved private construction |
| D-R2-002 | 2026-06-28 | Keep OAuth scopes minimal (`drive.file`, `gmail.readonly`) | Manual Drive root inaccessible; app-created root required |
| D-R2-003 | 2026-06-28 | Missing API keys are non-blocking | Implement `NOT_CONFIGURED` connectors with fixtures |
| D-R2-004 | 2026-06-28 | AUTONOMOUS application mode locked in R2 | UI disabled + backend rejection |
| D-R2-005 | 2026-06-28 | R2.1 before broad ingestion | Duplicate protection before scale |
| D-R2-006 | 2026-06-28 | No LinkedIn/Indeed scraping | Gmail alerts + manual URL import only |
| D-R2-007 | 2026-06-28 | Incremental UI modernization (R2.10) | No full frontend rewrite |
