# Google OAuth Runbook

Dedicated career Gmail integration for Drive sync and labeled Gmail ingestion. Client credentials stay outside Git.

## Configuration sources

| Item | Location |
|------|----------|
| OAuth client JSON | `C:\AarohanSecrets\google-oauth-client.json` |
| Project metadata | `config/integration-context.yml` |
| Client ID/secret (Docker) | PowerShell SecretStore (`GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`) |
| Dedicated account | `swapnilpatil.tech@gmail.com` (`CAREER_GMAIL_ADDRESS`) |
| Redirect URI | `http://localhost:8000/api/integrations/google/callback` |
| Drive root folder | `GOOGLE_DRIVE_ROOT_FOLDER_ID` in SecretStore |

Google Cloud project: `aarohan-careeros-500722` (see `integration-context.yml`).

## Scopes

**Default (always requested):**

- `openid`
- `userinfo.email`, `userinfo.profile`
- `drive.file` — app-created Drive files only
- `gmail.readonly` — read labeled career mail

**Optional (test email only):**

- `gmail.send` — only when `ENABLE_EXTERNAL_EMAIL_SEND=true` and user connects with "Enable Test Email"

Local-first defaults: external send **disabled**; test sends produce `.eml` drafts instead.

## Google Cloud Console checklist

1. OAuth client type: Web application.
2. Authorized redirect URIs:
   - `http://localhost:8000/api/integrations/google/callback`
   - `http://127.0.0.1:8000/api/integrations/google/callback`
3. Authorized JavaScript origins:
   - `http://localhost:3000`
   - `http://127.0.0.1:3000`
4. Enable Gmail API and Google Drive API.
5. OAuth consent screen configured for the dedicated account.

## Connect flow

1. Start stack with live mode: `OAUTH_FIXTURE_MODE=false` and OAuth credentials available.
2. Sign in to dashboard at http://localhost:3000.
3. Open Settings → Integrations → **Connect Google**.
4. API returns auth URL from `GET /api/integrations/google/connect`.
5. Sign in as **swapnilpatil.tech@gmail.com** and approve all scopes.
6. Browser redirects to `/api/integrations/google/callback`; success page shows account and Drive folder count.
7. Verify status: `GET /api/integrations/status` (authenticated).

Post-connect: API syncs Drive subfolders (`01_Career_Vault` … `99_Archive`) and writes `oauth.connected` audit event.

## Dedicated account rule

The callback calls `verify_dedicated_account()`. Connecting any account other than `CAREER_GMAIL_ADDRESS` fails with a remediation message. Disconnect and reconnect with the correct Gmail.

## Fixture mode (default in Docker)

`OAUTH_FIXTURE_MODE=true` (compose default) uses in-memory Gmail/Drive fixtures — no live Google calls. Use for CI and offline development.

Switch to live:

```powershell
$env:OAUTH_FIXTURE_MODE = "false"
pwsh .\scripts\local\Start-Aarohan.ps1 -Detached
```

Ensure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are in SecretStore for Docker deployments.

## Disconnect and refresh

- **Disconnect:** `POST /api/integrations/google/disconnect` (Settings UI or API).
- **Refresh:** `POST /api/integrations/google/refresh` — validates stored token.
- **Revoke in Google:** https://myaccount.google.com/permissions — then disconnect locally.

## Remediation matrix

| Error / symptom | Fix |
|-----------------|-----|
| OAuth not configured | Place JSON at `C:\AarohanSecrets\google-oauth-client.json`; store client ID/secret in SecretStore for Docker |
| redirect_uri_mismatch | Add both localhost and 127.0.0.1 callback URIs in Cloud Console |
| invalid_client | Verify JSON or SecretStore client ID/secret match Cloud Console |
| invalid_grant | Disconnect and reconnect; re-consent if refresh token revoked |
| access_denied | Retry connect; approve all requested scopes |
| insufficient_scope | Disconnect and reconnect |
| wrong_account | Use `swapnilpatil.tech@gmail.com` only |
| folder_not_found | Verify `GOOGLE_DRIVE_ROOT_FOLDER_ID`; ensure account owns or can access folder |
| api_disabled | Enable Gmail and Drive APIs in project `aarohan-careeros-500722` |

Messages are defined in `apps/api/app/services/google_api.py` (`OAUTH_REMEDIATION`).

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
- No primary personal Gmail — dedicated career account only.
