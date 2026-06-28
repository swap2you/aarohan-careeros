# Application Modes

## Manual

Behavior:

- discovers and scores,
- prepares documents,
- validates facts,
- saves locally and in Drive,
- opens official application,
- tracks the user's decision.

It does not fill or submit external fields.

## Assisted

Behavior:

- supported ATS detection,
- uses approved profile answers,
- selects approved documents,
- prefills supported fields,
- displays unresolved questions,
- reruns duplicate checks,
- captures evidence,
- stops before final external submission.

The user presses Submit on the employer/ATS site.

## Autonomous — locked

R2 behavior:

- visible as a future capability,
- disabled in UI,
- rejected by backend,
- warning explains why,
- no hidden override through URL or API.

Suggested warning:

`Autonomous submission is disabled. Automatic applications can send duplicate, inaccurate, or low-quality submissions and may violate job-site rules. Use Assisted mode and review the final application before submitting.`

## Unsupported websites

Fall back to Manual mode. Do not attempt brittle automation merely to claim broader coverage.

## CAPTCHA

Never bypass CAPTCHA. Pause and hand control to the user.

## Sensitive and voluntary questions

Do not infer or automatically answer:

- disability,
- race/ethnicity,
- gender,
- veteran status,
- demographic self-identification,
- criminal history,
- salary history where restricted,
- sponsorship/work authorization without an approved answer,
- binding legal attestations.

Use saved approved responses where appropriate, or require the user to answer.
