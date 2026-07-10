# Cowork UAT — Run Only After Backend Sign-Off

Do not run during recovery.

After Codex final GO, use Cowork to validate:

- login and restart
- Fresh Jobs list/detail/filter/sort
- public discovery result messaging
- URL-only intake and New Opportunity
- shortlist and packet generation
- approval/application workflow
- Gmail review and recruiter/interview pages
- Ask Aarohan context
- TTS locations
- settings and validation summaries
- no broken links, stale loaders, silent button failures, or raw JSON exposure

Cowork must not alter database infrastructure or recovery files.
