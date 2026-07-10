# Phase 2 — Permanent Test Isolation

## Goal

Make owner-database damage impossible through supported and accidental test execution.

## Required architecture

- separate `postgres-e2e` service
- separate Compose project
- separate user/password/database/network/volume
- no owner secrets mounted into E2E
- owner runtime image excludes tests/pytest or aborts before collection
- DB identity marker: OWNER / E2E / CI / RECOVERY plus UUID
- destructive helpers require E2E/CI identity and explicit token
- owner runtime DB role has no DDL
- migration role is separate
- audit dry-run uses read-only DB role/transaction
- owner destructive operations require verified same-run backup
- one canonical `Run-Aarohan-Tests.ps1`
- CI scan rejects owner-stack pytest commands

## Mandatory proof

- owner `docker compose exec api pytest` cannot run
- spoofed DB name/password/host cannot bypass guard
- E2E credentials cannot connect to owner
- owner runtime role cannot drop schema/table
- audit dry-run cannot update
- test suite passes only on isolated test infrastructure
- owner data counts unchanged
