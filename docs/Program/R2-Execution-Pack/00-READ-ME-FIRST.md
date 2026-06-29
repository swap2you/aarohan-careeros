# Aarohan CareerOS R2 Execution Pack

Prepared: 2026-06-28  
Target repository: `C:\Development\Workspace\aarohan-careeros`  
Target branch: `main`  
Baseline checkpoint: `aed228d583e0b6a7760eb6091c82883cda5e5426`

## Purpose

This pack converts the approved Aarohan CareerOS vision into an executable, documented release program.

The immediate objective is a complete local-first career workflow:

1. Discover jobs from legitimate sources.
2. Normalize and deduplicate them.
3. Verify employer and posting trust.
4. Score fit against Swapnil Patil's career profile.
5. detect prior applications and duplicate-submission risk.
6. Generate a job-specific application packet.
7. Validate factual consistency and document quality.
8. Save the packet locally and in Google Drive.
9. Require human approval before external submission.
10. Track applications, Gmail responses, interviews, and follow-ups.
11. Provide a human-readable dashboard and Ask Aarohan assistant.
12. Complete independent engineering review and UAT.

## Approved application modes

- **Manual**: Generate and organize everything. User opens the application and completes it.
- **Assisted**: Prefill supported application forms and stop before final submission.
- **Autonomous**: Visible in the roadmap but locked and disabled. It must not submit applications in R2.

## Non-negotiable rules

- Work directly on `main`; no feature branches or pull requests.
- Never commit secrets, tokens, generated personal documents, or browser profiles.
- Complete releases sequentially.
- Each release must pass its gate, update documentation, commit, push, create an annotated tag, and push the tag.
- A missing external API key must not stop the program. Mark that connector `NOT_CONFIGURED` and continue.
- Preserve the working infrastructure. Do not rebuild architecture without evidence that it is required.
- Use the existing local secret vault under `C:\AarohanSecrets`.
- Do not scrape LinkedIn, Indeed, Glassdoor, or other sources in violation of their rules.
- No CAPTCHA bypass.
- No fabricated experience, credentials, dates, salary history, work authorization, or application answers.
- The factual core of all resumes must remain consistent.

## How to use this pack

1. Extract this folder outside the repository.
2. Open Cursor in `C:\Development\Workspace\aarohan-careeros`.
3. **Run the app:** follow `docs/runbooks/LOCAL-APPLICATION-EXECUTION.md` (bootstrap, start, test, troubleshoot).
4. Paste the contents of `01-MASTER-CURSOR-PROMPT.md` into Cursor Agent mode when driving releases.
5. Complete the key/account checklist in `04-KEYS-AND-JOB-ALERTS-SETUP.md` while Cursor works.
6. Do not paste secrets into Cursor chat. Place them only in SecretStore / `.env.local` (non-secrets).
7. Use `12-OWNER-CHECKLIST.md` to track external actions.

## Definition of the first usable product

The product is usable when a user can:

- run an ad hoc job search,
- see trustworthy human-readable results,
- identify duplicate-application risk,
- prepare one tailored application packet,
- approve it,
- open the official application,
- record the application,
- sync Gmail,
- and view the complete timeline.

The final R2 release adds UI modernization, Ask Aarohan, TTS, cleanup, hardening, and UAT.
