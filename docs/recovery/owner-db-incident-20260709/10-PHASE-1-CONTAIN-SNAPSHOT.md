# Phase 1 — Contain and Snapshot

## Goal

Preserve every recoverable database and establish trustworthy inventory before any recovery.

## Prohibited

No data writes, restores, migrations, cleanups, schema resets, test runs against owner,
or Docker volume deletion.

## Required work

1. Record Git SHA/status and running Docker resources.
2. Identify PostgreSQL container, named volume, Compose project, databases, schemas,
   sizes, and table counts.
3. Create:
   `artifacts/recovery/incident-20260709/<timestamp>/`
4. Dump every non-template database, including:
   - career_os
   - career_os_validation
   - every test/E2E/recovery database
   - PostgreSQL globals
5. Use byte-safe dump creation inside the container followed by `docker cp`, or another
   method proven safe on Windows.
6. Generate SHA-256 checksums and manifests.
7. Restore each dump into a new disposable verification database and validate it.
8. Inventory owner-relevant tables and exact row counts.
9. Inspect generated document volume, Drive metadata, Gmail IDs, OAuth rows, applications,
   versions, interviews, recruiter signals, audit and AI usage.
10. Produce:
    - INCIDENT-SNAPSHOT-REPORT.md
    - DATABASE-INVENTORY.json
    - TABLE-ROW-COUNTS.json
    - BACKUP-MANIFEST.json
    - RECOVERY-CANDIDATE-ASSESSMENT.md
11. Confirm no owner or validation row changed.
