# Lever job board connector

## Site slug from hosted URL

Lever hosts public job boards at:

`https://jobs.lever.co/{company_slug}`

The **company slug** is the path segment after `jobs.lever.co/`. Examples:

| Hosted board URL | Slug for API / connector |
|------------------|--------------------------|
| `https://jobs.lever.co/leverdemo` | `leverdemo` |
| `https://jobs.lever.co/acme-corp` | `acme-corp` |

The public postings API is:

`https://api.lever.co/v0/postings/{company_slug}?mode=json`

For EU-hosted boards, set `LEVER_API_BASE=https://api.eu.lever.co/v0/postings` in environment.

## Demo / test-only mode

Use slug `leverdemo` or pass `"demo": true` in connector params. Demo mode returns fixture jobs only and does not call the live API or persist demo records into production workflows when `CONNECTOR_FIXTURE_MODE` is used for scheduled runs.

## Error handling

| Condition | User-visible result |
|-----------|---------------------|
| Invalid or inactive slug (HTTP 404) | `NO_ACTIVE_BOARD` message, zero ingested jobs |
| Non-JSON or non-list response | `NO_ACTIVE_BOARD` structured error |
| One board failure | Other configured boards continue independently |

Invalid slugs such as `figma` must not produce HTTP 500 from the application API.
