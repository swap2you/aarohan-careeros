# Live validation evidence (redacted)

**Date:** 2026-06-27  
**RC:** `r2.13.0-rc3`

## Google connection

| Check | Result | Notes |
|-------|--------|-------|
| Account linked in DB | **PASS** | Dedicated career Gmail shown |
| Token decrypt usable | **FAIL** | Stored tokens not decryptable with current `TOKEN_ENCRYPTION_KEY` / `APP_SECRET` — **Reconnect Google** once in Settings |
| Fixture mode | **PASS** | `OAUTH_FIXTURE_MODE=false` in running stack |
| Restart without re-consent | **NOT VERIFIED** | Blocked until `token_usable` |

## Google Drive (R2.5)

| Step | Result | Notes |
|------|--------|-------|
| Drive root accessible | **FAIL** | `resolve_active_drive_root` → not accessible (no usable Drive token) |
| Subfolders in settings | **PARTIAL** | Cached subfolder map present; live API calls blocked |
| Packet v01 upload | **NOT RUN** | Requires token reconnect + job packet workflow |
| Packet v02 immutability | **NOT RUN** | Pending v01 |
| UI Drive ID masking | **PASS** | Settings UI hides raw IDs in normal view |

**Drive live validation:** **FAIL** (token reconnect required)

## Gmail (R2.7)

| Source | Result |
|--------|--------|
| Live labeled sync | **FAIL** (empty — no usable Gmail token) |
| Idempotency (fixture) | **PASS** — Playwright `r27-gmail.spec.ts` |
| Raw payload in UI | **PASS** — recruiter signals show snippets only |

**Gmail live validation:** **FAIL** until reconnect; fixture path **PASS**

## Connectors

Live probe via `POST /api/validation/run` → `connectors` step: **PASS** (10 connectors checked, redacted status/latency/count).

## Ask Aarohan

| Check | Result |
|-------|--------|
| Pipeline question | **PASS** — cited answer, no secrets |
| Secret request block | **PASS** (unit + prior tests) |

## TTS

| Check | Result |
|-------|--------|
| API with key in container | **FAIL** — `mode: unavailable` (`AI_API_KEY` not loaded in current Docker session) |
| Key not in browser bundle | **PASS** (build + secret scan) |

**Owner action:** Start stack via `Start-Aarohan.ps1` so `.env.local` / SecretStore loads `OPENAI_API_KEY` into `AI_API_KEY`.

## Backup / restore

| Check | Result |
|-------|--------|
| `pg_dump` owner DB | **PASS** (~2.1 MB artifact) |
| Restore to `career_os_validation` | **PASS** (28 public tables) |
| Owner DB unchanged | **PASS** (2 users on `career_os`) |

## Local validation UI

`POST /api/validation/run` returns plain-English PASS/FAIL steps when `OAUTH_FIXTURE_MODE=false`.

**Latest automated run (rc3 session):** **FAIL** — `google_connection` PASS (linked), `drive_root` FAIL, `drive_packets` FAIL, `gmail_live` PASS (empty inbox path), `connectors` PASS.

## Owner unblock checklist

1. Settings → **Reconnect Google** (re-encrypts tokens with current `TOKEN_ENCRYPTION_KEY`).
2. Confirm Drive root accessible → **Sync Drive Subfolders**.
3. Generate packet v01 → mark submitted → generate v02 → re-run validation.
4. **Sync Gmail (read-only)** → confirm per-label counts.
5. Restart stack → confirm no second consent screen.
6. Start via `Start-Aarohan.ps1` for live TTS key injection.
