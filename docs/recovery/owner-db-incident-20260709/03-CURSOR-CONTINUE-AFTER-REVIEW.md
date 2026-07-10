# Cursor Continuation Prompt After a Codex Review

Resume the recovery orchestration.

Repository:

`C:\Development\Workspace\aarohan-careeros`

Read:

- `docs/recovery/owner-db-incident-20260709/RECOVERY-ORCHESTRATION-STATE.md`
- the newest file under
  `docs/recovery/owner-db-incident-20260709/reviews/`
- `01-CURSOR-MASTER-ORCHESTRATOR.md`

Resolve every Critical and High Codex finding and all recovery-correctness Medium findings.

Do not change UI/UX/CSS.
Do not run tests against owner `career_os`.
Do not proceed through an owner-approval gate.
Do not create RC4.

After corrections:

- rerun all affected evidence and tests
- update the review disposition in the state file
- continue only to the next permitted phase
- stop at the next mandatory gate
- return exact evidence paths and test/database identities
