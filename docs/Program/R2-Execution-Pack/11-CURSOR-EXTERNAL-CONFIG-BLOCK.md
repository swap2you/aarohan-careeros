# External Configuration Contract for Cursor

Cursor must add configuration without storing secret values.

Suggested logical variables:

```dotenv
# AI
OPENAI_API_KEY=
OPENAI_DOCUMENT_MODEL=
OPENAI_UTILITY_MODEL=
OPENAI_TTS_MODEL=

# Job sources
ADZUNA_APP_ID=
ADZUNA_APP_KEY=
JOOBLE_API_KEY=
USAJOBS_API_KEY=
USAJOBS_USER_AGENT=swapnilpatil.tech@gmail.com

# Application policy
APPLICATION_MODE=manual
AUTONOMOUS_APPLICATION_ENABLED=false
DUPLICATE_CAUTION_DAYS=180
SAME_COMPANY_MIN_SPACING_DAYS=14
MAX_ACTIVE_APPLICATIONS_PER_COMPANY=2

# Internal assistant
ASK_AAROHAN_SQL_MODE=read_only
ASK_AAROHAN_ALLOW_MUTATIONS=false
```

Cursor must adapt names to existing conventions where necessary.

Rules:

- update `.env.example` with blanks and explanations,
- keep real values under `C:\AarohanSecrets`,
- validate required/optional variables at startup,
- show source status as `READY`, `NOT_CONFIGURED`, `PENDING_APPROVAL`, `DEGRADED`, or `ERROR`,
- never print secret values,
- redact headers and tokens in logs,
- missing optional source credentials must not fail API startup.
