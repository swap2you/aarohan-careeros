# Cursor End-to-End Demo — R1 Local v2

Date: 2026-06-27

## Demo path (fixture mode — no live Google required)

1. **Auth**: Admin login via `/api/auth/login` (test: `admin@test.local`)
2. **Ingest**: `POST /api/jobs/ingest/fixture` → 1 job, score ≥ 75
3. **Score**: Transparent scoring components persisted on `JobScore`
4. **Packet**: `POST /api/applications/jobs/{id}/generate?resume_profile=qe_leadership` → DOCX/PDF under `generated/`
5. **Approval**: `POST /api/applications/{id}/actions` with `approve` → `APPROVED_FOR_SUBMISSION` (no external submit route)
6. **Interview**: `POST /api/interviews/jobs/{id}/generate` → questions, system design
7. **Consulting**: `POST /api/consulting/leads` → lead score + service recommendation
8. **Gmail fixture**: `POST /api/integrations/gmail/sync-fixture` → recruiter signal
9. **Validation**: `POST /api/validation/run` → secret scan + prohibited scan + pytest
10. **AI budget**: `GET /api/ai/budget` → hard cap active

## Live Google demo (requires user)

1. Set `OAUTH_FIXTURE_MODE=false` in environment
2. Ensure `C:\AarohanSecrets\google-oauth-client.json` exists
3. Start stack: `pwsh scripts/local/Start-Aarohan.ps1 -Detached`
4. Open http://localhost:3000/settings → **Connect Google**
5. Sign in as `swapnilpatil.tech@gmail.com` and approve scopes
6. Verify `/api/integrations/status` shows connected
7. `POST /api/integrations/gmail/sync` — ingest labeled messages
8. `GET /api/integrations/google/drive/folders` — verify subfolder IDs
9. Generate packet → Drive links in `packet_metadata.drive_links`

## Sample generated paths (from prior fixture run)

- `apps/api/generated/job_1/Example_Health_Tech_Director_of_Quality_Engineering_qe_leadership_20260624.pdf`

## Blockers for full live demo

- User OAuth consent click in browser
- Docker Desktop installed for containerized demo
- Gmail messages labeled `Aarohan` for ingestion proof
