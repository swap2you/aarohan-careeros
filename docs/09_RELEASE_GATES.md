# Release Gates

Release only when:
- unit tests pass;
- integration tests pass;
- E2E tests pass;
- secret scan passes;
- prohibited-source scan passes;
- scoring tests pass;
- generated claims map to evidence;
- approval boundary tests pass;
- AI budget cap is active;
- backups and restore are tested;
- health endpoints are green;
- audit log is complete;
- Codex returns PASS;
- Cowork UAT returns PASS or approved conditional PASS.

Release decision:
- GO
- CONDITIONAL GO
- STOP
