# Document Naming, Storage, and Linking

## Principle

A filename is for convenience. The database job ID, packet ID, and artifact ID are the authoritative links.

## Local storage

Use an ignored/generated root discovered from the existing project configuration. Do not commit personal documents.

Recommended logical structure:

`<artifact-root>\<year>\<company-slug>\<job-id>-<role-slug>\<packet-version>\`

Example:

`2026\amazon\job-18422-director-quality-engineering\packet-v01\`

## Google Drive storage

Use the existing app-created Drive root.

Recommended structure:

- `02_Application_Packets`
  - `2026`
    - `<Company>`
      - `<YYYY-MM-DD> - <Role> - <ReqID or JobID>`
        - Resume
        - Cover Letter
        - Application Answers
        - Company Brief
        - Recruiter Brief
        - Interview Preparation
        - Packet Summary

## Filename convention

Use a sanitized, human-readable name:

`YYYY-MM-DD__Company__Role__ReqID__DocumentType__vNN.ext`

Examples:

- `2026-06-30__Amazon__Director-Quality-Engineering__REQ-12345__Resume__v01.pdf`
- `2026-06-30__Amazon__Director-Quality-Engineering__REQ-12345__Cover-Letter__v01.docx`
- `2026-06-30__Amazon__Director-Quality-Engineering__REQ-12345__Interview-Brief__v01.pdf`

If no requisition ID exists, use the internal normalized job ID.

## Packet metadata

Store internally:

- job and company IDs,
- source URL and source snapshot ID,
- requisition/ATS IDs,
- document type,
- version,
- factual-core hash,
- template/prompt/model versions,
- local path,
- Drive file/folder IDs,
- generated/approved/used timestamps,
- application ID,
- checksum.

Internal metadata may be JSON in the database or artifact manifest. Standard UI must display plain English, not raw JSON.

## Dashboard behavior

Each job and application must provide:

- **Open Resume**
- **Open Cover Letter**
- **Open Packet Folder**
- **Open in Google Drive**
- **Open Local Folder**
- **Download**
- **Copy Application Answers**
- **View Version History**

A scheduled run summary must link directly to newly generated or updated artifacts.

## Usage states

- Draft
- Validation Failed
- Ready for Review
- Approved
- Used in Application
- Superseded
- Archived

Once a resume is marked used, do not overwrite it. Create a new version.

## Retention

Keep the exact submitted packet and source job snapshot. This is necessary for later interview preparation, recruiter responses, consistency checks, and duplicate prevention.
