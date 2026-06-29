# Auth Session and Google Persistence Validation

Date: 2026-06-27  
Release: **r2.6.1** (patch on r2.6.0)  
Environment: local Docker (`docker compose`, volumes retained — no `-v`)

## Root cause (Phase 1)

| Symptom | Cause |
|---|---|
| Shell + Overview rendered after restart | Frontend treated `localStorage.careeros_token` as authenticated without server validation |
| Dashboard dashes / API failures | Stale JWT or missing server session after container restart or `APP_SECRET` change |
| No durable login | Bearer-only auth; no HttpOnly cookie; no PostgreSQL session rows |

## Session architecture (implemented)

- **Authority:** PostgreSQL `auth_sessions` table (migration `0007_auth_sessions`)
- **Transport:** HttpOnly cookie `careeros_session` (`SameSite=Lax`, `Secure` in production/staging)
- **Validation gate:** `GET /api/auth/session` on every load via `AuthProvider`
- **Protected UI:** `AppShell` splash until session resolves; unauthenticated → `/login?reason=session_expired&returnTo=…`
- **API:** `resolve_user_from_session` first; Bearer JWT retained for tests only
- **Logout:** `POST /api/auth/logout` revokes DB row and clears cookie
- **401 handling:** single `apiFetch` redirect; business 403 (e.g. autonomous mode) does not log out

## Remember Me

| Setting | Behavior |
|---|---|
| Enabled (default) | 30-day sliding server session; survives browser, API, web, and full stack restart |
| Disabled | 12-hour session cookie max-age |

## Restart acceptance (Phase 8)

Test user: `e2e@test.local` (Remember Me enabled)

| Step | Result |
|---|---|
| Login | `authenticated=true` |
| `GET /api/auth/session` before restart | `authenticated=true` |
| `docker compose restart api web` | api + web healthy |
| Session after api/web restart | `authenticated=true` |
| `GET /api/jobs` after restart | 200 (5 jobs) |
| `docker compose down` + `docker compose up -d` (no `-v`) | all services healthy |
| Session after full stack restart | `authenticated=true` |

Google integration status after restart: **disconnected** in fixture/local mode (no live OAuth connection on this test account). API keys/connectors remain configured via environment/SecretStore.

## Live Google Drive (Phase 9)

**Status: PENDING OWNER ACTION**

1. Open **Settings**
2. Click **Connect Google** (or **Reconnect Google** if required)
3. Approve Drive/Gmail scopes in browser
4. Return to Aarohan

After owner confirmation, re-run Drive packet upload validation to upgrade **R2.5** from CONDITIONAL GO to FULL GO.

## Test evidence

| Suite | Result |
|---|---|
| API pytest (SQLite in container) | 105 passed |
| Auth session tests (`test_auth_sessions.py`) | 10 passed |
| Google persistence (`test_google_oauth_persistence.py`) | 3 passed |
| Playwright e2e | 18 passed |
| Web `npm run build` | PASS |

## Playwright coverage

- Unauthenticated → login
- Remember Me login → Overview with data
- Protected routes gated
- Logout → login; direct protected route blocked
- Session-expired message
- Invalid cookie → login
- Autonomous 403 does not clear session
- Cookie session survives API re-auth

## Secrets

No tokens, cookies, or secret values are recorded in this document.
