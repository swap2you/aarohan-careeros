# Owner Checklist

**Run the app:** `docs/runbooks/LOCAL-APPLICATION-EXECUTION.md`

## Machine setup (once)

- [ ] `pwsh .\scripts\local\Bootstrap-Aarohan.ps1`
- [ ] `pwsh .\scripts\local\Initialize-AarohanSecrets.ps1`
- [ ] OAuth JSON at `C:\AarohanSecrets\google-oauth-client.json`
- [ ] `.env.local` configured (non-secrets only; see `.env.example`)

## Daily / validation

- [ ] `pwsh .\scripts\local\Start-Aarohan.ps1 -Detached`
- [ ] Sign in at http://localhost:3000/login (SecretStore admin)
- [ ] `pwsh .\scripts\validation\Verify-Full-R2.ps1` before release sign-off
- [ ] `pwsh .\scripts\validation\Live-RC-Validation.ps1` after live Google connect

## Today — key/account actions

- [ ] Complete the OpenAI key setup widget.
- [ ] Save `OPENAI_API_KEY` in the existing local secret vault.
- [ ] Register for Adzuna API credentials.
- [ ] Request Jooble API access.
- [ ] Request USAJOBS API access.
- [ ] Do not paste any returned secret into chat or Git.
- [ ] Confirm Cursor can read this execution pack.
- [ ] Paste `01-MASTER-CURSOR-PROMPT.md` into Cursor Agent mode.

## Job source accounts

Use `swapnilpatil.tech@gmail.com`.

- [ ] LinkedIn alerts
- [ ] Indeed alerts
- [ ] Dice account and alerts
- [ ] Glassdoor account and alerts
- [ ] Verify account profile facts match
- [ ] Use one stable public baseline resume
- [ ] Create Gmail labels after first alerts arrive

## Search alerts

- [ ] Head of Quality Engineering
- [ ] Director of Quality Engineering
- [ ] Director of QA
- [ ] QA Manager
- [ ] Test Engineering Manager
- [ ] Principal SDET
- [ ] Staff Quality Engineer
- [ ] Quality Engineering Architect
- [ ] Test Automation Architect
- [ ] Solution Architect Automation
- [ ] AI Quality Engineering
- [ ] GenAI Test Automation
- [ ] AI Automation Lead
- [ ] AI Solutions Architect
- [ ] Prompt Engineer
- [ ] Context Engineer

Create remote-US and Harrisburg-area variants where useful.

## Before July 4 weekend UAT

- [ ] Releases R2.0–R2.12 tagged and pushed, or documented exceptions exist.
- [ ] No secrets in repository.
- [ ] Manual end-to-end journey passes.
- [ ] Assisted mode stops before submit.
- [ ] Autonomous mode is locked.
- [ ] Duplicate exact-requisition test passes.
- [ ] Resume contradiction test passes.
- [ ] Local and Drive links work.
- [ ] Gmail sync works.
- [ ] Ask Aarohan returns traceable answers.
- [ ] TTS reads a generated document.
- [ ] Backup/restore passes.
- [ ] Codex review complete.
- [ ] Claude Code review complete.
- [ ] Cowork UAT complete.
- [ ] Critical/high defects resolved.
