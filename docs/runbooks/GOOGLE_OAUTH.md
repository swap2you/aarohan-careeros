# Google OAuth Runbook

Dedicated career Gmail integration for Drive sync and labeled Gmail ingestion. Client credentials stay outside Git.

## Configuration sources

| Item | Location |
|------|----------|
| OAuth client JSON | `C:\AarohanSecrets\google-oauth-client.json` |
| Project metadata | `config/integration-context.yml` |
| Client ID/secret (Docker) | PowerShell SecretStore (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) |
| Dedicated account | `swapnilpatil.tech@gmail.com` (`CAREER_GMAIL_ADDRESS`) |
| Primary phone | `714.307.4266` (Career Vault `contact.yml`) |
| Redirect URI | `http://localhost:8000/api/integrations/google/callback` |
| Configured Drive root (manual) | `1yqQixjo6GGBcjwIXEfHx1STeaJHz_qOI` |
| Active app-created root (proven) | `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr` (`aarohan-careeros`) |

Google Cloud project: `aarohan-careeros-500722` (number `558756512850`).

## Local login before OAuth

| Item | Value |
|------|-------|
| Dashboard | http://localhost:3000 |
| Settings | http://localhost:3000/settings |
| Admin email | `swapnilpatil.tech@gmail.com` |
| Local password | `TempLocal123!` (reset via `scripts/local/Reset-LocalAdmin.ps1`) |

## Scopes (unchanged — minimal)

**Default (always requested):**

- `openid`
- `userinfo.email`, `userinfo.profile`
- `drive.file` — app-created Drive files/folders only
- `gmail.readonly` — read labeled career mail

**Optional (test email only):**

- `gmail.send` — only when `ENABLE_EXTERNAL_EMAIL_SEND=true` and user connects with "Enable Test Email"

Local-first defaults: external send **disabled**; test sends produce `.eml` drafts instead.

## Connect flow

1. Start stack with `OAUTH_FIXTURE_MODE=false` and OAuth credentials available.
2. Sign in at http://localhost:3000 (`swapnilpatil.tech@gmail.com` / local password).
3. Open http://localhost:3000/settings → **Connect Google**.
4. Approve scopes as **swapnilpatil.tech@gmail.com**.
5. Callback saves tokens even if configured manual root is inaccessible.
6. If Drive warning appears, click **Create Aarohan Drive Root**, then **Sync Drive Subfolders**.

Post-connect: encrypted tokens in `oauth_tokens`; active root ID in `system_settings`; subfolders created idempotently.

## Drive root and `drive.file` scope

The `drive.file` scope **does not** grant access to arbitrary folders by ID. Manually created roots (including `1yqQixjo6GGBcjwIXEfHx1STeaJHz_qOI`) are **inaccessible** unless the app created them. Public link sharing does not fix this.

**Proven behavior (2026-06-28):**

1. OAuth callback saves tokens; Drive sync is best-effort (warning, not failure).
2. Settings shows root accessibility, source (`configured` vs `app-created`), subfolder IDs.
3. **Create Aarohan Drive Root** provisions `aarohan-careeros` → active ID `1EaueVpEFOkZE-_9EKrY-_xdcJgY1Jkqr`.
4. Subfolders under active root:

| Folder | ID |
|--------|-----|
| `01_Career_Vault` | `1V0xcP90y2XZPH7cABm4ByOJmvfFXy7B9` |
| `02_Application_Packets` | `1___eJy4-j8bhDHtPXzHljNkkmbkpyXmj` |
| `03_Interview_Preparation` | `1cI1GdpOSxAaZqz1uOwLFBMIldaSkVOLm` |
| `04_Consulting` | `1mcg_J6mhQzyn3u9Og9waPkbNisHjp8oR` |
| `05_Reports` | `1dp1k0kYhJp8fgHfKznZ5tbK0s58T9PCO` |
| `99_Archive` | `1WWMbm0yyu2aAN8LU4f2SQ-TATbbWXUsQ` |

## Dedicated account rule

The callback calls `verify_dedicated_account()`. Connecting any account other than `CAREER_GMAIL_ADDRESS` fails. Disconnect and reconnect with `swapnilpatil.tech@gmail.com`.

## Fixture mode

`OAUTH_FIXTURE_MODE=true` (compose default) uses fixtures — no live Google calls. For local OAuth proof, set `OAUTH_FIXTURE_MODE=false` before `docker compose up`.

## Disconnect and refresh

- **Disconnect:** Settings or `POST /api/integrations/google/disconnect`
- **Refresh:** `POST /api/integrations/google/refresh`
- **Revoke in Google:** https://myaccount.google.com/permissions — then disconnect locally

## Remediation matrix

| Error / symptom | Fix |
|-----------------|-----|
| OAuth not configured | Place JSON at `C:\AarohanSecrets\google-oauth-client.json`; store client ID/secret in SecretStore |
| redirect_uri_mismatch | Add localhost and 127.0.0.1 callback URIs in Cloud Console |
| invalid_client | Verify JSON or SecretStore client ID/secret |
| invalid_grant | Disconnect and reconnect with consent |
| wrong_account | Use `swapnilpatil.tech@gmail.com` only |
| Drive root inaccessible | Expected for manual root with `drive.file`; use **Create Aarohan Drive Root** in Settings |
| Not authenticated in Settings | Sign in at http://localhost:3000 first; or run `Reset-LocalAdmin.ps1` |
| api_disabled | Enable Gmail and Drive APIs in project `aarohan-careeros-500722` |

## Gmail labels (expected)

- `Aarohan/Job Alerts`
- `Aarohan/Recruiters`
- `Aarohan/Interviews`
- `Aarohan/Applications`
- `Aarohan/Rejections`

Manual sync: `POST /api/integrations/gmail/sync` (live) or `/gmail/sync-fixture` (fixture mode).

## Security notes

- Tokens encrypted at rest with `TOKEN_ENCRYPTION_KEY`.
- Never commit OAuth JSON or client secrets to Git.
- Test email recipients must be on `TEST_EMAIL_ALLOWLIST` when send is enabled.
