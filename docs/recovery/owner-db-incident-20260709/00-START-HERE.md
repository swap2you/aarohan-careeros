# Aarohan Owner-Database Recovery — Start Here

## Repository

`C:\Development\Workspace\aarohan-careeros`

## Install location

Extract this entire pack to:

`C:\Development\Workspace\aarohan-careeros\docs\recovery\owner-db-incident-20260709\`

Do not scatter the files across `runbooks`, `validation`, or `workflow-locks`.

Runtime evidence and SQL dumps must go under:

`C:\Development\Workspace\aarohan-careeros\artifacts\recovery\incident-20260709\`

## Execution model

- **Cursor is the only code-writing/executing agent.**
- **Codex is the independent read-only reviewer.**
- Do not run Cursor and Codex simultaneously against the repository.
- Do not allow two agents to commit or edit the same branch at the same time.
- Cowork is used only after recovery and backend stabilization for final UAT.

## Mandatory sequence

1. Cursor runs Phase 1: containment and verified backups.
2. Cursor stops at Gate 1.
3. Codex reviews Phase 1 evidence.
4. Cursor resolves review findings and runs Phase 2: permanent test isolation.
5. Codex reviews Phase 2.
6. Cursor resolves findings and prepares recovery candidate.
7. Cursor stops at Gate 2 before owner cutover.
8. Owner approves or rejects cutover.
9. Cursor performs approved cutover and final validation.
10. Codex performs final independent sign-off.
11. Cowork performs UI/UAT only after backend sign-off.

## Non-negotiable safety rules

Never run:

- `docker compose exec api pytest`
- `docker compose down -v`
- `Audit-FreshJobsData.ps1 -Execute`
- migration downgrade against `career_os`
- direct restore over `career_os`
- schema reset against owner or validation databases

Workflow Lock 01 remains `READY_FOR_OWNER_VALIDATION` until final recovery and fresh-jobs validation are complete.
