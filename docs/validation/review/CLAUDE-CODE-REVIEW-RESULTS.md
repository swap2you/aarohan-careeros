# Claude Code architecture review results (R2.13 RC)

**Date:** 2026-06-29  
**Scope:** `r2.13.0-rc1` (`edb540d`)  
**Verdict:** **Maintainable for solo-owner local-first usage** with documented risks; **not** ready for multi-tenant cloud without ADR-001 execution.

## Strengths

- Clear router → service → model layering
- Job ingestion → dedupe → scoring → packet pipeline is traceable
- Audit log on sensitive operations (OAuth, Gmail sync, Ask queries)
- Fixture mode cleanly separates live vs test integrations
- R2.12 canonical paths and validation scripts improve operability

## Architecture risks (prioritized)

| Priority | Area | Risk | Mitigation path |
|----------|------|------|-----------------|
| P1 | Auth | Dual JWT + session paths | Unify on session cookie for UI |
| P1 | OAuth | In-process state, single-worker assumption | DB-backed state before cloud |
| P2 | Gmail | Race on concurrent sync | Idempotent insert-first pattern |
| P2 | Documents | Partial failure leaves PACKET_GENERATING | Transactional generation |
| P2 | Assisted apply | Host substring ATS detection | Strict host allowlist |
| P3 | Duplicate engine | Full-table URL scan | Indexed normalized URL column |
| P3 | Ask Aarohan | Rule engine limited; SQL mode not wired | Keep read-only; document limits |
| P3 | Scheduler | Disabled locally; n8n separate | Document worker split (R2.11) |

## Data flow assessment

```
Connectors/Gmail → ingestion → dedupe/trust → shortlist → packet → validation → manual/assisted apply
                                      ↓
                              company ledger / timeline
```

Flow is coherent. Side-effect commits inside `evaluate_duplicate_risk` on read paths are a maintainability smell — separate query from mutation.

## Failure modes

| Failure | Current behavior | Gap |
|---------|------------------|-----|
| OAuth token expiry | Auto-refresh path in `google_api.py` | Silent decrypt failure on reconnect |
| OpenAI unavailable | TTS returns `unavailable` mode | Documented; PASS in tests |
| Connector missing keys | NOT_CONFIGURED status | PASS |
| Budget exceeded | `enforce_budget` raises | PASS |
| Docker restart | Sessions in Postgres survive | PASS (Playwright) |
| Missing alembic_version | API crash loop on upgrade | Operational: `alembic stamp head` |

## Performance

Acceptable for single-user local volumes. Gmail sync loads up to 50 messages per call — fine for inbox scale. Duplicate URL scan will degrade with large ledger — medium backlog item.

## Cleanup quality (R2.12)

- Single active program board: `docs/Program/R2-PROGRAM-BOARD.md`
- Execution-pack template is historical (not duplicate active doc)
- `generated/` gitignored correctly
- `00-CURRENT-STATUS.md` was stale — updated in rc2 validation commit

## Recommendation

**CONDITIONAL GO** for July owner UAT on local stack. Refactor auth/OAuth state before any cloud pilot.
