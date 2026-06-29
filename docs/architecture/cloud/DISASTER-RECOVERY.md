# Disaster recovery (R2.11)

## Local scripts

- `scripts/local/Backup-Aarohan.ps1`
- `scripts/local/Restore-Aarohan.ps1`

## RPO / RTO targets (cloud TBD)

- Daily DB backups minimum
- Generated document storage replicated
- OAuth tokens recoverable from encrypted vault backup

## Never commit

- `.env.local`, dumps, OAuth tokens, Playwright artifacts
