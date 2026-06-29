# Known limitations (R2.13 RC)

1. **Live Google Drive** — owner browser OAuth required for FULL GO on R2.5.
2. **Ask Aarohan** — rule-based read-only engine; full LLM SQL mode gated behind config and not enabled by default.
3. **TTS** — requires `AI_API_KEY` / OpenAI; falls back to on-screen text when unavailable.
4. **Cloud multi-tenant** — documented only (ADR-001); not implemented locally.
5. **Gmail live smoke** — fixture-complete; real inbox validation depends on labeled messages.
6. **No LinkedIn/Indeed scraping** — by policy; email alerts and API connectors only.
