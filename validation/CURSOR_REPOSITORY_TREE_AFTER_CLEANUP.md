# Repository Tree After Cleanup

Date: 2026-06-27

## Tracked canonical layout

```text
aarohan-careeros/
├── .cursor/rules/
├── .github/workflows/ci.yml
├── .env.example
├── .gitignore
├── AGENTS.md
├── README.md
├── PROJECT_CHARTER.md
├── START_HERE.md
├── docker-compose.yml
├── apps/
│   ├── api/          # FastAPI, Alembic, pytest
│   └── web/          # Next.js dashboard, Playwright
├── career_vault/     # Evidence and resume profiles
├── config/           # Policy YAML
├── docs/
│   ├── architecture/
│   ├── runbooks/
│   ├── testing/
│   ├── operations/
│   ├── releases/
│   └── archive/      # Superseded prompts and packs
├── n8n/workflows/
├── scripts/
│   ├── local/        # Bootstrap, Start, Stop, Test, Backup, Restore
│   ├── validation/   # secret_scan, prohibited_source_scan
│   └── backup/
└── validation/       # R1 review and test evidence
```

## Archived / removed from root

- `aarohan_finalize_main_sync_pack/` → `docs/archive/ai-prompts/CURSOR_FINALIZE_MAIN_SYNC.md`
- `Aarohan_R1_Local_Execution_Pack_v2/` → `docs/archive/execution-packs/`
- Obsolete prompts → `docs/archive/ai-prompts/`

## Local-only (gitignored)

- `Aarohan - Keys & secrets.txt`
- `*.zip`
- `.env.local`
- `AarohanSecrets/`
- `.local/`, `artifacts/`, `generated/`
- `node_modules/`, `.venv/`, `.next/`
