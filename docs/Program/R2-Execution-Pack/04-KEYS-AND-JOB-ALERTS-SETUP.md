# Keys, Accounts, and Job Alerts Setup

Use the dedicated account:

`swapnilpatil.tech@gmail.com`

Do not store job-board passwords in Aarohan. Do not paste secret values into Git, documentation, issue comments, Cursor chat, Codex chat, or Claude chat.

Cursor must first discover the existing local secret-loading mechanism and extend it. Keep secrets under:

`C:\AarohanSecrets`

Recommended environment variable names are listed below. The actual local file must remain ignored and outside the repository.

---

## 1. OpenAI

A secure OpenAI API key setup flow was opened from ChatGPT for the key name:

`Aarohan CareerOS Local`

After creating/copying the key:

1. Save it only in the existing local secret mechanism.
2. Recommended variable:
   `OPENAI_API_KEY=<secret>`
3. Add non-secret configuration separately:
   - `OPENAI_DOCUMENT_MODEL=<configured current model>`
   - `OPENAI_UTILITY_MODEL=<configured economical model>`
   - `OPENAI_TTS_MODEL=<configured speech model>`
4. Never hardcode model names throughout the codebase. Use a model registry/configuration.
5. Set an OpenAI project budget and usage alerts in the Platform dashboard.

Official API documentation:

`https://developers.openai.com/api/docs/`

Official speech-generation guide:

`https://developers.openai.com/api/docs/guides/text-to-speech`

---

## 2. Adzuna

Official registration:

`https://developer.adzuna.com/`

Steps:

1. Select **Register**.
2. Use `swapnilpatil.tech@gmail.com`.
3. Application name: `Aarohan CareerOS`.
4. Website, when required: `https://github.com/swap2you`
5. Use description:

   `Private local-first career management tool for personal job discovery, job matching, document preparation, and application tracking. Results retain Adzuna attribution and link users to the original job posting.`

6. Complete email verification.
7. Open the application/API credentials page.
8. Copy the application ID and application key.
9. Store locally as:
   - `ADZUNA_APP_ID`
   - `ADZUNA_APP_KEY`
10. Do not commit them.

Aarohan must preserve source attribution and original application links.

---

## 3. Jooble

Official API request form:

`https://jooble.org/api/about`

Steps:

1. Fill in the API request form.
2. Name: `Swapnil Patil`
3. Position: `Project Lead / Developer`
4. Email: `swapnilpatil.tech@gmail.com`
5. Website: `https://github.com/swap2you`
6. Use purpose:

   `A private local-first career operating system used by one job seeker to search and normalize job listings, compare them with a career profile, and link back to the original job source. No resale of data.`

7. Submit the request.
8. When the key arrives, store it as:
   `JOOBLE_API_KEY`
9. Mark Jooble `PENDING_APPROVAL` until the key is received.

---

## 4. USAJOBS

Official token request:

`https://developer.usajobs.gov/apirequest/index`

Steps:

1. Enter the requested name, email, phone, and project details.
2. Company/Agency:
   `Aarohan CareerOS — personal project`
3. Description:

   `Private personal-use career application that searches public federal job announcements, filters them for the registered user, and links back to the official USAJOBS announcement. Data is not resold or redistributed.`

4. Accept the current terms.
5. Submit.
6. Store the received token as:
   - `USAJOBS_API_KEY`
   - `USAJOBS_USER_AGENT=swapnilpatil.tech@gmail.com`
7. Cursor must follow the current USAJOBS authentication/header documentation.
8. Mark the source `PENDING_APPROVAL` until received.

---

## 5. No-key connectors

The first implementation must not wait for credentials for:

- Greenhouse public GET job-board endpoints
- Ashby public job-posting endpoints
- Lever public postings
- Remotive
- Remote OK

Official references:

- Greenhouse: `https://developers.greenhouse.io/job-board.html`
- Ashby: `https://developers.ashbyhq.com/docs/public-job-posting-api`
- Lever: `https://github.com/lever/postings-api`
- Remotive: `https://remotive.com/remote-jobs/api`
- Remote OK: `https://remoteok.com/api`

Cursor must review current terms, attribution, and rate guidance before productionizing a connector.

---

## 6. Google

Existing OAuth is working for:

- identity,
- Gmail read access,
- Drive file access.

Do not widen scopes merely to simplify implementation.

Existing local client file:

`C:\AarohanSecrets\google-oauth-client.json`

Connected account:

`swapnilpatil.tech@gmail.com`

---

## 7. LinkedIn job alerts

Do not request or build a personal LinkedIn job-search API. Do not scrape LinkedIn.

Use the LinkedIn website/app:

1. Sign in with the existing LinkedIn account.
2. Open **Jobs**.
3. Run each saved search from the search matrix below.
4. Set location and remote/hybrid filters.
5. Enable **Set alert** / **Job alert**.
6. Choose daily email delivery where available.
7. Use `swapnilpatil.tech@gmail.com` as the notification email.
8. Keep one factual public resume/profile baseline.
9. Aarohan will ingest alert emails and retain the LinkedIn source URL.

---

## 8. Indeed job alerts

1. Create or sign in to Indeed with `swapnilpatil.tech@gmail.com`.
2. Keep the same factual work history as LinkedIn.
3. Run each saved search.
4. Apply remote, location, seniority, and compensation filters where available.
5. Create a daily alert.
6. Do not use a materially different uploaded resume.
7. Aarohan will ingest the alert email; it will not scrape Indeed.

---

## 9. Dice job alerts

1. Create/sign in using the dedicated Gmail.
2. Use the stable baseline resume.
3. Create saved searches for senior quality, architecture, AI-quality, and automation leadership roles.
4. Enable daily alerts.
5. Preserve direct employer links when available.
6. Aarohan will ingest alert emails and perform employer/ATS verification.

---

## 10. Glassdoor job alerts

1. Create/sign in using the dedicated Gmail.
2. Create saved job searches.
3. Enable job alerts.
4. Use Glassdoor primarily for company intelligence, salary context, and discovery.
5. Verify the actual job on the employer or ATS site before application.
6. Aarohan will not scrape reviews or restricted data.

---

## 11. Saved-search matrix

Create separate alerts rather than one broad noisy query.

### Leadership

- `Head of Quality Engineering`
- `Director of Quality Engineering`
- `Director of QA`
- `QA Manager`
- `Test Engineering Manager`

### Senior technical

- `Principal SDET`
- `Staff Quality Engineer`
- `Quality Engineering Architect`
- `Test Automation Architect`
- `Solution Architect Automation`
- `DevTestOps Architect`

### AI and future direction

- `AI Quality Engineering`
- `GenAI Test Automation`
- `AI Automation Lead`
- `AI Solutions Architect`
- `Prompt Engineer`
- `Context Engineer`

### Location variants

Create at least two variants:

1. United States — Remote
2. Harrisburg/Enola, Pennsylvania — hybrid radius appropriate to the user

Do not require salary to be present, because many high-quality roles omit it. Score disclosed compensation when available.

---

## 12. Gmail organization

After the first alert from each site arrives:

1. Open the message in Gmail.
2. Use **Filter messages like these**.
3. Apply label:
   `Aarohan/Job Alerts/<Source>`
4. Do not auto-delete.
5. Optionally skip Inbox only after Aarohan parsing is validated.
6. Keep alerts for audit and source tracing.

Suggested labels:

- `Aarohan/Job Alerts/LinkedIn`
- `Aarohan/Job Alerts/Indeed`
- `Aarohan/Job Alerts/Dice`
- `Aarohan/Job Alerts/Glassdoor`
- `Aarohan/Recruiters`
- `Aarohan/Applications`
- `Aarohan/Interviews`
- `Aarohan/Rejections`
- `Aarohan/Offers`

---

## 13. Profile consistency checklist

Use the same factual core across every job site:

- employer names,
- job titles,
- employment dates,
- education,
- certifications,
- location,
- contact information,
- work authorization,
- leadership scope,
- technologies actually used.

Different summaries and skill emphasis are acceptable. Conflicting dates, titles, degrees, or employment claims are not.
