# Google Configuration Verification

## Accepted setup
The new dedicated Google Cloud project is the correct project for Aarohan.

Use:
- Project ID: `aarohan-careeros-500722`
- Project number: `558756512850`
- Dedicated account: `swapnilpatil.tech@gmail.com`

The localhost origins and callbacks are correct.

## OAuth scope policy

The Google Cloud console currently contains more scopes than V1 needs. This does not block local development.

The application code must request only these scopes by default:

```text
openid
https://www.googleapis.com/auth/userinfo.email
https://www.googleapis.com/auth/userinfo.profile
https://www.googleapis.com/auth/drive.file
https://www.googleapis.com/auth/gmail.readonly
```

Optional test-email capability may request this additional scope incrementally and only after the user clicks `Enable Test Email`:

```text
https://www.googleapis.com/auth/gmail.send
```

The application must not request:
- full Gmail access
- Gmail modify
- Gmail insert
- Gmail settings
- Gmail add-on scopes
- full Drive access
- Drive activity scopes

Configured-but-unused console scopes are not a runtime requirement. The code controls the actual consent request.

## OAuth application state
The screenshots show mixed testing/production indicators. The application must support both:
- local testing with the dedicated account
- production publishing state with an unverified warning

Do not submit public verification during R1.

## Secret handling
The OAuth JSON file contains the client ID and client secret. The application reads it from:

`C:\AarohanSecrets\google-oauth-client.json`

Do not copy the client secret into:
- prompts
- Markdown
- `.env.example`
- source code
- logs
- test output
- Git history
