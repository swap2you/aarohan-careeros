# Cloud threat model (R2.11)

## Assets

- User credentials and session tokens
- Google OAuth refresh tokens (encrypted at rest)
- Career Vault evidence
- Application packets and interview materials
- API keys (OpenAI, job connectors)

## Threats

| ID | Threat | Mitigation |
|----|--------|------------|
| T1 | Session hijack | HttpOnly cookies, TLS, rotation, revocation |
| T2 | XSS token theft | No tokens in localStorage; CSP |
| T3 | CSRF on mutations | SameSite + CSRF tokens in cloud mode |
| T4 | Secret leakage | Vault, secret scan CI, no logs of tokens |
| T5 | Prompt injection via job text | Sanitize HTML; policy guardrails |
| T6 | Ask Aarohan SQL abuse | Read-only default; block secret tables |
| T7 | Autonomous apply | Hard-disabled; assisted stop-before-submit |

## Out of scope (local)

- Multi-tenant isolation (documented in ADR-001)
