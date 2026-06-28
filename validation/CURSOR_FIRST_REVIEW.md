# Cursor First Review — R1 Local Docker Validation

Date: 2026-06-28  
Decision: **NOT READY** — implementation and local stack validated; live Google OAuth and CI watch remain user/host actions.

## Gates passed

| Area | Status |
|------|--------|
| Secret / prohibited scans | PASS |
| Docker 4-service stack | PASS (all healthy) |
| Alembic current/check/downgrade/upgrade | PASS (`0003_fk_not_null`) |
| Backend pytest (container) | PASS (25/25) |
| Fixture ingest → score → packet → preview | PASS |
| Playwright smoke E2E | PASS (1/1) |
| Backup write + restore data verify | PASS (with n8n-schema caveat) |
| OAuth JSON mount | PASS |
| Scheduling disabled | PASS (`scheduling_enabled: false`) |

## Gates blocked

| Area | Status |
|------|--------|
| Live Google OAuth UI | **BLOCKED** — user must connect `swapnilpatil.tech@gmail.com` |
| Drive folder idempotency (live IDs) | **BLOCKED** — no OAuth token |
| Gmail label-ID sync + dedup (live) | **BLOCKED** — no OAuth token |
| GitHub Actions watch | **BLOCKED** — `gh` not installed on host |
| Git commit/push | **NOT PERFORMED** — gates incomplete |

## Fixes applied during validation

1. `config_loader._repo_root()` — Docker-safe path (fixture ingest)
2. `integrations.sync_gmail` — wire `get_gmail_client(db)`
3. Alembic `0003_fk_not_null` — FK nullability drift
4. Playwright smoke — accept Sign in or First-run setup heading
5. Playwright artifacts → `artifacts/playwright/`

## Reviewer summaries

- **Product:** Dashboard IA complete; packet pipeline proven on fixture job.
- **Security:** Scans pass; OAuth configured; no external send; no schedules.
- **Database:** Migrations reversible; `alembic check` clean at head.
- **Backend:** 25 tests pass in container with live OAuth env.
- **Frontend:** E2E smoke passes against running stack.
- **Google:** Connect URL generates; live proof pending user consent.
- **DevOps:** Docker healthy; backup/restore works for Career OS data; restore noisy due to shared DB with n8n.
- **Career truthfulness:** Evidence-gated generation; missing-evidence warnings surfaced.
