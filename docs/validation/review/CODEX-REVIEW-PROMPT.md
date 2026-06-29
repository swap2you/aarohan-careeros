# Codex independent review prompt (R2.13)

Copy this prompt into Codex for a full traceability and security review.

---

You are reviewing **Aarohan CareerOS** at release candidate `r2.13.0-rc1`.

Repository: local checkout at HEAD tagged `r2.13.0-rc1`.

## Required coverage

1. **Traceability** — map R2.0–R2.13 requirements to code, migrations, tests, and `docs/releases/`.
2. **Migrations** — Alembic chain `0001`–`0009`; upgrade/downgrade safety.
3. **Security** — session cookies, no tokens in browser storage, CSRF posture for future cloud.
4. **Auth** — `user_sessions` stores hashes only; logout revocation; Remember Me semantics.
5. **Google** — refresh token encryption at rest; preservation on re-auth; no plaintext in DB/logs.
6. **Duplicate logic** — job dedupe across API, ATS, Gmail.
7. **Vendor representation** — assisted apply boundaries; no autonomous submit.
8. **Immutable documents** — submitted packet versions cannot be silently overwritten.
9. **Gmail idempotency** — `processed_gmail_messages`, thread updates.
10. **Ask Aarohan** — read-only default; secret table blocking; SQL mutation gates.
11. **Tests & CI** — pytest, Playwright, secret scan in pipeline.
12. **Release history** — tags r2.0.0–r2.13.0-rc1 immutable.

## Output format

- Executive summary (GO / CONDITIONAL / NO GO)
- Findings by severity with file:line references
- Missing test gaps
- Owner actions before personal usage

Do not request or print secrets.
