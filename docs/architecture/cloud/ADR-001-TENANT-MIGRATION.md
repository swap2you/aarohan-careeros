# ADR-001: Tenant migration (future)

## Status

Proposed — not implemented in local R2.

## Context

Local CareerOS is single-user. Cloud SaaS requires tenant isolation.

## Decision

1. Add `tenant_id` to core tables in a future migration wave
2. Row-level security in PostgreSQL per tenant
3. Separate OAuth token namespaces per tenant
4. No premature tenant columns in local R2.12 app code

## Consequences

- Local installs unaffected
- Cloud migration is a dedicated program phase after R2.13 UAT
