# UAT plan (R2.13)

## Scope

End-to-end owner validation before personal daily usage.

## Entry criteria

- `r2.13.0-rc1` tagged and CI green
- `scripts/validation/Verify-Full-R2.ps1` PASS (or documented skips)

## Execution

1. Run automated gate locally.
2. Complete Cowork UAT package (`docs/validation/uat/COWORK-UAT-PACKAGE.md`).
3. Complete live Drive OAuth section if not yet done.
4. File results in `UAT-RESULTS-TEMPLATE.md`.

## Exit criteria

- No critical or high-severity data-integrity defects open
- Rollback plan reviewed
- Owner sign-off on GO / CONDITIONAL GO / NO GO
