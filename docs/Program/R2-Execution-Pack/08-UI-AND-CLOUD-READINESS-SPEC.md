# UI and Cloud Readiness Specification

## Product direction

Aarohan should feel like a professional operating console, not an admin database screen.

Use a restrained design:

- strong typography,
- consistent spacing,
- clear hierarchy,
- status chips,
- useful motion,
- responsive layout,
- dark/light theme,
- accessible controls,
- plain-English explanations.

Avoid:

- raw JSON in normal views,
- animation for its own sake,
- excessive dashboards,
- hidden critical actions,
- misleading AI certainty,
- decorative complexity.

## Required local screens

1. Login
2. Command Center
3. Job Inbox
4. Job Detail
5. Search/Schedule Manager
6. Application Packet
7. Application Pipeline
8. Company/Application Ledger
9. Recruiters
10. Interviews
11. Document Center
12. Integrations
13. Ask Aarohan
14. Settings
15. Audit/Run History

## Command Center

Show:

- last run,
- source health,
- new jobs,
- high-fit jobs,
- duplicate-risk jobs,
- packets awaiting review,
- applications needing follow-up,
- upcoming interviews,
- integration failures,
- Run Search Now action.

## Job detail

Show:

- source and official link,
- trust status,
- fit status,
- hard requirements,
- evidence matches,
- gaps,
- prior company applications,
- possible duplicates,
- generated documents,
- company/recruiter information,
- Prepare Application action.

## Cloud readiness

Cloud deployment is deferred until local R2 passes UAT.

Future cloud requirements:

- every private route protected,
- unauthenticated deep link redirects to login and returns after authentication,
- Google login,
- email/password login,
- reset flow,
- secure cookie/session handling,
- CSRF protection,
- rate limits,
- encrypted secrets,
- tenant-boundary design,
- audit events,
- object storage,
- worker/scheduler separation,
- backups and restore,
- privacy/export/delete controls,
- terms, privacy policy, and AI disclaimer,
- subscription/billing abstraction.

Do not implement full multi-tenancy now. Avoid schema choices that make it impossible later.

## Legal/product boundaries

- use only permitted data sources,
- preserve attribution,
- link to original jobs,
- do not represent fit/trust scores as guarantees,
- do not fabricate application content,
- disclose AI-generated assistance,
- do not bypass job-site controls,
- document data retention and deletion before public launch,
- obtain legal review before commercial SaaS launch.
