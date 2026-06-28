# Release Gate and Git Policy

## Direct-main policy

The owner approved direct commits to `main` during private construction.

This saves process overhead but raises rollback risk. Compensate with:

- clean baseline,
- small release commits,
- full gate before every commit,
- annotated tags,
- pushed tags,
- documented rollback,
- no force push,
- no history rewrite,
- no unreviewed destructive migration.

## Before each release

- confirm branch `main`,
- confirm clean or understood working tree,
- fetch remote,
- fast-forward safely,
- record current SHA,
- create a local safety reference if needed,
- verify the previous release tag exists.

## Required checks

Cursor must discover actual commands and maintain one canonical local verification script.

Minimum:

- secret scan,
- prohibited-source/scraping scan,
- backend formatter/lint,
- backend type/static checks where configured,
- `pytest`,
- frontend lint,
- frontend type check,
- frontend tests,
- production frontend build,
- migration upgrade from clean database,
- migration upgrade against existing local database,
- API integration tests,
- Playwright end-to-end tests,
- Docker health,
- document extraction tests when relevant,
- Drive/Gmail tests with redacted evidence when relevant.

A skipped test requires a reason. A failing test cannot be reported as passed.

## Commit

Recommended format:

`R2.x: <release outcome>`

Example:

`R2.1: add duplicate application protection and company ledger`

## Tag

Create annotated tag:

`git tag -a r2.x.0 -m "Aarohan CareerOS R2.x — <title>"`

Push:

`git push origin main`
`git push origin r2.x.0`

Do not tag before the commit and gate are complete.

## Release notes

Create:

`docs/releases/R2.x.0.md`

Include:

- objective,
- delivered scope,
- architecture changes,
- migrations,
- configuration,
- tests/results,
- screenshots/evidence,
- known limitations,
- external credentials,
- commit/tag,
- rollback.

## Rollback

Document release-specific rollback.

At minimum:

- application rollback to prior tag,
- database downgrade feasibility,
- backup location,
- data added after migration,
- irreversible actions.

## GitHub Actions

GitHub Actions must validate pushes to `main`.

Do not put local secrets in Actions. External integration tests should use mocks unless intentionally configured with repository/environment secrets.
