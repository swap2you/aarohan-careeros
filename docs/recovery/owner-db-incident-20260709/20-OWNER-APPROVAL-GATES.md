# Owner Approval Gates

## Gate 1 — Recovery strategy

Cursor and Codex may inventory, back up, verify, and isolate tests without owner approval.

Before recovering or merging ambiguous owner rows, present:

- recoverable tables/counts
- missing data
- ambiguous data
- proposed exclusions
- candidate recovery strategy

## Gate 2 — Canonical cutover

Cursor must stop before replacing or redirecting the canonical owner database.

The exact approval phrase is:

`APPROVE OWNER CANDIDATE CUTOVER`

Without that phrase, no cutover is permitted.

## Final lock

Workflow Lock 01 may be marked LOCKED only after:

- owner cutover succeeds
- final tests pass
- Codex final review is GO
- owner confirms Fresh Jobs output
