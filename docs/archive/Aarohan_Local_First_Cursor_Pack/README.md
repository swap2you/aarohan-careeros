# Aarohan CareerOS — Local-First Cursor Completion Pack

This patch changes the immediate execution model:

- Develop and validate everything locally first.
- Run workflows manually from the dashboard.
- Do not deploy yet.
- Do not enable scheduled production workflows yet.
- Cursor completes implementation and performs the first full review.
- Codex or Claude Code performs the independent second review.
- Cowork performs UAT after the second review.

## One action

Extract this ZIP into the root of `aarohan-careeros`, then send Cursor:

```text
Read prompts/CURSOR_LOCAL_FIRST_COMPLETE_REVIEW.md and execute it end to end. Do not stop between internal gates unless a real user credential or destructive action is required. Do not commit or push.
```
