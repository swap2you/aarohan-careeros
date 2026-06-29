# Cloud auth and sessions (R2.11)

## Local (implemented)

- Email/password + first-run setup
- HttpOnly `careeros_session` cookie
- PostgreSQL `user_sessions` with token hashes
- Remember Me: 60-day sliding; without: browser-session cookie

## Cloud (planned)

- Google Sign-In as optional IdP alongside email
- CSRF tokens on state-changing browser forms
- Rate limiting on `/api/auth/login`
- Secure cookies (`Secure`, `SameSite=None` only behind TLS)

See `docs/validation/AUTH-SESSION-AND-GOOGLE-PERSISTENCE.md` for local validation evidence.
