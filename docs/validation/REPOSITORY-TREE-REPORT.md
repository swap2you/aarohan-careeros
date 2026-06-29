# Repository tree report (R2.12)

Generated as part of R2.12 consolidation. Canonical locations:

| Purpose | Path |
|---------|------|
| Program board | `docs/Program/R2-PROGRAM-BOARD.md` |
| Release notes | `docs/releases/R2.*.md` |
| Validation evidence | `docs/validation/` |
| Runbooks | `docs/runbooks/` |
| Cloud ADRs | `docs/architecture/cloud/` |
| API fixtures | `apps/api/fixtures/` |
| Gmail fixtures | `apps/api/fixtures/gmail/` |
| Local scripts | `scripts/local/` |
| Validation scripts | `scripts/validation/` |
| Career vault | `career_vault/` |

Top-level layout:

```
apps/api/          FastAPI backend, Alembic, pytest
apps/web/          Next.js frontend, Playwright e2e
config/            Shared configuration references
docs/              Program, releases, validation, architecture
scripts/           Bootstrap, local ops, validation gates
career_vault/      Approved evidence (no secrets)
docker-compose.yml Local stack
```

Tracked secrets policy: none — see `.gitignore` and `scripts/validation/secret_scan.py`.
