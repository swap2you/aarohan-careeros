# Local-First Secret Strategy

## Decision

Secrets do not travel with Git.

Each environment has its own secret source:

| Environment | Secret source |
|---|---|
| Local Windows development | PowerShell SecretStore, loaded by repository scripts |
| GitHub Actions | GitHub repository/environment secrets; tests should prefer mocks and fixtures |
| Future VPS deployment | Docker secrets or a server-side secret manager |
| Google OAuth tokens | Encrypted at rest in the application database using a master encryption key held outside the database |

## Local development

Use Microsoft's PowerShell SecretManagement and SecretStore modules.

The repository stores:
- secret names;
- configuration examples;
- bootstrap scripts;
- no secret values.

The developer runs one setup script once to enter values. A start script loads the values from the local encrypted vault and starts the application.

Do not keep a live credentials text file under the repository, even if gitignored.

## GitHub Actions

CI should run:
- unit tests;
- integration tests with disposable PostgreSQL;
- fixture-based Gmail and Drive tests;
- document-generation tests;
- security scans;
- frontend build and E2E tests.

CI does not need personal live Gmail, Drive, LinkedIn, Indeed, or production API credentials.

Only add GitHub Actions secrets when a specific CI test or deployment job genuinely needs one.

## Future deployment

When deployment starts:
- create new production-only credentials;
- rotate all development tokens;
- use Docker secrets or a server-side secret manager;
- never copy the local secret vault to the server;
- never put production secrets in GitHub files or Google Drive.

## OAuth

Use a dedicated career Gmail account.

Store:
- OAuth client ID/secret in the environment secret provider;
- refresh/access tokens encrypted at rest;
- minimum required scopes;
- explicit disconnect and token-revocation support.

## Current exposed credential response

The previous GitHub PAT and passwords that were visible to Cursor should be rotated. This is a parallel security task, not a reason to stop local development.
