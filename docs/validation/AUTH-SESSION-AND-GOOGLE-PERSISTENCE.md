# AUTH-SESSION-AND-GOOGLE-PERSISTENCE — R2.6.1 validation

**Date:** 2026-06-29  
**Baseline:** r2.6.0 (`83bbe66`)  
**Patch:** R2.6.1 auth/session lifecycle  
**Validator:** automated + container restart acceptance

## Root cause (confirmed)

| Layer | Failure |
|---|---|
| Frontend | `localStorage` key `careeros_token` treated as proof of login; shell rendered before API validation |
| Backend | Stateless JWT only (12h); no HttpOnly cookie; no PostgreSQL session rows |
| After restart | Stale client token → API 401; UI still showed Nav + Overview with blank dashboard (`—`) |

## Session architecture (post-patch)

- **Authority:** PostgreSQL `user_sessions` table (Alembic `0007_auth_sessions`)
- **Transport:** HttpOnly cookie `careeros_session` (`SameSite=Lax`, `Secure=false` on localhost HTTP)
- **Validation gate:** `GET /api/auth/session` on every app load; splash until resolved
- **Remember Me:** 60-day sliding renewal (server-managed)
- **Short session:** 12 hours when Remember Me unchecked
- **Logout:** `POST /api/auth/logout` revokes DB row + clears cookie
- **API auth:** cookie first; Bearer session token or legacy JWT for tests only
- **Session invalid:** `401` + `X-Aarohan-Auth: session-required` → single redirect to `/login?reason=session_expired`
- **Business 403:** no logout (e.g. autonomous-mode policy)

## Restart acceptance

### A. `docker compose restart api web` (no volume loss)

| Step | Result |
|---|---|
| Services healthy after restart | PASS — api, web, postgres, n8n healthy |
| Playwright auth-session suite (6 tests) | PASS — login, protected routes, logout, tampered cookie, no shell leak |
| API `/health` | PASS |

### B. `docker compose down` → `docker compose up -d` (no `-v`)

| Step | Result |
|---|---|
| All services healthy | PASS |
| PostgreSQL volume retained | PASS (sessions table present) |
| Playwright smoke + auth-session | PASS (re-run after stack up) |

### C. Remember-Me persistence semantics

| Scenario | Expected | Result |
|---|---|---|
| Login with Remember Me | DB session row + cookie Max-Age | PASS (backend tests) |
| API container restart | Session row in Postgres survives | PASS |
| Web container restart | Cookie in browser survives | PASS (Playwright after restart) |
| Logout | Row revoked, cookie cleared | PASS |
| Tampered cookie | Redirect + session-expired message | PASS |

## Google OAuth persistence (fixture / unit)

| Check | Result |
|---|---|
| Refresh token preserved when re-auth omits it | PASS (`test_save_token_preserves_refresh_when_missing`) |
| Refresh response without new refresh token keeps old | PASS (`test_refresh_keeps_refresh_token`) |
| Expired access token triggers refresh path | PASS (`test_get_token_auto_refresh_when_expired`) |
| Tokens absent from `/api/integrations/status` payload | PASS |
| Fixture mode survives restart | PASS (OAUTH_FIXTURE_MODE=true in compose) |

## Live Google Drive

| Item | Status |
|---|---|
| Owner browser OAuth + live upload proof | **PENDING** — owner action required |
| R2.5 release status | **CONDITIONAL GO** |

**Owner action (one step):** Open Settings → Connect Google (or Reconnect) → approve Drive/Gmail scopes → return to Aarohan → confirm Drive root and packet upload after restart.

## Test evidence

| Suite | Count | Result |
|---|---|---|
| API pytest (container) | 108 passed | PASS |
| Playwright auth-session + smoke | 7 passed | PASS |
| Playwright auth-session after `restart api web` | 6 passed | PASS |

## Configuration persistence after restart

Integrations load from env/vault (not browser storage). Status values remain categorical (`READY`, `NOT_CONFIGURED`, `DEGRADED`, `ERROR`) — no secret values logged or returned.

## R2.7

**Not started** — resume after r2.6.1 tag and CI green.
