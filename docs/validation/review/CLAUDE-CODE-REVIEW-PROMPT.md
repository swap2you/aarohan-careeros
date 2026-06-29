# Claude Code architecture review prompt (R2.13)

Copy into Claude Code for maintainability and data-flow review.

---

Review **Aarohan CareerOS** `r2.13.0-rc1` for architecture quality.

## Focus areas

- Layering: routers → services → models/integrations
- Data flow: job ingestion, dedupe, scoring, packet generation, Drive linkage
- Scheduler and connector retry/idempotency
- Gmail lifecycle → job/recruiter linking
- Interview intelligence evidence boundaries
- Ask Aarohan and TTS cost paths
- Observability: audit logs, health endpoints
- Failure modes: OAuth expiry, budget caps, connector degradation
- Performance: N+1 queries, large Gmail sync batches
- R2.12 cleanup quality — dead code, doc duplication

## Deliverable

Structured report: strengths, risks, refactor suggestions (prioritized), and whether the codebase is maintainable for a solo owner through July UAT.
