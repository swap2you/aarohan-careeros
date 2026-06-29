# Live validation evidence (redacted)

**Date:** 2026-06-29  
**RC:** `r2.13.0-rc1`

## Google Drive (R2.5)

| Step | Status | Notes |
|------|--------|-------|
| Connected account | **BLOCKED** | Validation session: SecretStore locked; API container lacks `ADMIN_EMAIL` when not started via `Start-Aarohan.ps1` |
| Expected scopes | **NOT VERIFIED** | Requires owner Settings → integration status |
| Encrypted refresh token | **PASS** (unit) | `test_google_oauth_persistence.py`; live row not inspected in this session |
| Drive root | **NOT VERIFIED** | Owner: confirm app root in Settings after OAuth |
| Packet v01/v02 immutability | **NOT VERIFIED** | Fixture + unit tests PASS; live upload pending |
| Restart without re-consent | **NOT VERIFIED** | Owner action after live OAuth |

**R2.5 status:** **CONDITIONAL GO** (unchanged)

## Gmail (R2.7)

| Source | Status |
|--------|--------|
| LinkedIn alert | **NOT VERIFIED** live |
| Indeed alert | **NOT VERIFIED** live |
| Dice alert | **NOT VERIFIED** live |
| USAJOBS alert | **NOT VERIFIED** live |
| Glassdoor | **PENDING** (weekly cadence) |
| Fixture corpus | **PASS** — 9 messages, idempotent sync tests |
| Idempotent re-sync | **PASS** (fixture) |

**R2.7 status:** **CONDITIONAL GO** (unchanged)

## Ask Aarohan (live)

| Question class | Status |
|----------------|--------|
| Job counts / companies | **PASS** (automated tests) |
| Secret/token requests | **PASS** — blocked |
| Fit score / duplicates / follow-up | **LIMITED** — rule engine; returns uncertainty or generic guidance |
| Mutation / SQL | **PASS** — not enabled |

## TTS (live)

| Check | Status |
|-------|--------|
| API fallback without key | **PASS** |
| Generated audio with key | **NOT VERIFIED** in validation session |
| No key in browser bundle | **PASS** (secret scan + code review) |
| Cost recording | **PARTIAL** — budget service exists; live cost entry not verified |

## Owner actions to complete live validation

1. Run `scripts/local/Start-Aarohan.ps1` (loads SecretStore + env).
2. Complete Settings → Google connect if not READY.
3. Run `scripts/validation/Live-RC-Validation.ps1`.
4. Execute Drive packet v01/v02 checklist manually or via owner Cowork session.
5. Run Gmail sync; confirm per-source parsers on real labeled messages.
