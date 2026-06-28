# R2 Traceability Matrix

| Requirement | Release | Implementation | Tests |
|-------------|---------|----------------|-------|
| Baseline governance | R2.0 | Program docs, verify gate script | secret_scan, prohibited_scan, pytest, build |
| Application ledger | R2.1 | companies, ledger, events | `test_duplicate_risk.py` |
| Duplicate protection | R2.1 | duplicate_risk engine | `test_duplicate_risk.py` |
| Resume factual core | R2.1 | factual_core validator | `test_duplicate_risk.py` |
| Autonomous mode lock | R2.1 | backend reject + Settings UI | `test_duplicate_risk.py` |
| Job connectors | R2.2 | provider interface + adapters | `test_job_connectors.py` |
| Trust/fit scoring | R2.3 | trust_matching + hard filters | `test_trust_matching.py` |
| Document quality | R2.4 | vault, templates, validation | extraction tests |
| Manual apply workflow | R2.5 | packet review, apply link | E2E |
| Assisted apply | R2.6 | ATS detect, prefill, stop-before-submit | integration |
| Gmail lifecycle | R2.7 | alert parse, classify, dedup | fixture + live optional |
| Interview intel | R2.8 | briefs, STAR stories | unit |
| Ask Aarohan + TTS | R2.9 | Q&A, SQL guard, read-aloud | API tests |
| Modern UI | R2.10 | design system, screens | Playwright |
| Cloud readiness | R2.11 | design docs only | review checklist |
| Cleanup/hardening | R2.12 | lint, dead code, migrations | full gate |
| UAT / RC | R2.13 | multi-agent packages | Playwright UAT |
