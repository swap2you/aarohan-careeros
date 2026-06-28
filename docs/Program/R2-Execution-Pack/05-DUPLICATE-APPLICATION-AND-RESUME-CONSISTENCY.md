# Duplicate Application and Resume Consistency Policy

## Objective

Prevent accidental duplicate submissions, conflicting resumes, vendor conflicts, excessive applications to one employer, and avoidable reputational risk.

This is not a claim that employers universally blacklist applicants for multiple applications. Employer behavior varies. The system should control unnecessary risk without blocking reasonable applications to distinct roles.

## Canonical identities

### Company identity

Maintain:

- canonical company name,
- aliases and former names,
- parent/subsidiary relationships,
- verified domains,
- ATS board tokens/slugs,
- known staffing/vendor relationships.

Examples of records that may need linking:

- `Amazon`
- `Amazon Web Services`
- `AWS`
- a staffing vendor submitting to Amazon

Do not automatically collapse legal subsidiaries without evidence. Record relationships and let the policy decide how broadly to warn.

### Job identity

Store:

- source,
- source job ID,
- employer requisition ID,
- ATS job ID,
- canonical application URL,
- normalized title,
- normalized location/work arrangement,
- posted/updated/closing dates,
- description fingerprint,
- semantic similarity vector when available,
- employer and vendor.

### Resume identity

Every resume version must retain:

- stable factual-core hash,
- job ID,
- company ID,
- template version,
- prompt version,
- model version,
- generated timestamp,
- approval status,
- application usage status.

## Default policy

All thresholds must be configurable in Settings.

### RED — hard block

Block assisted progression until an explicit override is recorded when:

- exact employer requisition ID was already submitted,
- exact ATS job ID was already submitted,
- same canonical application URL was already submitted,
- same employer, substantially same description, and same role was already submitted,
- a staffing vendor already has active candidate representation for that exact client/requisition,
- the new resume changes protected factual-core data,
- application is already active or in interview/offer state,
- source appears to be a copied listing that redirects to an already-applied job.

Override requires:

- reason,
- user confirmation,
- timestamp,
- old and new records,
- audit event.

### AMBER — caution

Warn and require review when:

- same canonical company has any application within 180 days,
- role similarity is high but requisition ID differs,
- same company has two active applications,
- another application was sent within the last 14 days,
- resume emphasis differs significantly,
- vendor/client relationship is uncertain,
- parent/subsidiary relation may create duplication,
- a previous rejection occurred recently,
- job appears reposted.

Default cadence:

- maximum two active applications per canonical company,
- default 14-day spacing between applications to the same company,
- 180-day caution window,
- no automatic assumption that a six-month-old application is harmless.

The user can change the cadence for specific employers.

### GREEN — no known conflict

Display green only when:

- no exact or probable duplicate exists,
- no active vendor representation conflict exists,
- factual core is consistent,
- company cadence is within configured limits.

Green means no known conflict, not a guarantee.

## Resume consistency

### Immutable factual core

The following cannot change through tailoring without editing the approved career record:

- employer,
- title,
- dates,
- degree and institution,
- certifications,
- location history where represented,
- team sizes and metrics claimed as facts,
- work authorization,
- technologies not actually used.

### Tailorable elements

The following may change:

- summary,
- ordering of skills,
- ordering of achievements,
- wording,
- selected projects,
- role-specific keywords,
- length,
- cover-letter narrative.

### Validation output

Before approval, show:

- unchanged facts,
- tailored emphasis,
- removed facts,
- new claims,
- contradictions,
- unsupported claims,
- prior resume used for the same company,
- prior application date/status.

## UI indicator

Every job and packet must show:

- `No known conflict`
- `Prior company application`
- `Probable duplicate role`
- `Exact duplicate — blocked`
- `Vendor representation conflict`
- `Resume consistency issue`

The indicator must open a plain-English explanation and links to prior records.

## Pre-submit recheck

Run duplicate and resume checks:

1. when a job enters the inbox,
2. when a packet is generated,
3. when a packet is approved,
4. immediately before assisted apply,
5. when marking an application submitted.

A stale green result is not sufficient.

## Audit requirements

Store:

- policy version,
- thresholds,
- matched records,
- similarity scores,
- decision,
- override,
- user identity,
- timestamp.
