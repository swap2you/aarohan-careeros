# Fast Verification Plan

The following assumptions must be verified early:

1. Current repository still matches the handoff.
2. Existing GitHub Actions are accessible and passing.
3. The frontend and backend stacks support incremental modernization.
4. Existing document generation can be improved without replacement.
5. Google OAuth scopes remain sufficient.
6. Job connector terms allow the intended personal-use integration.
7. OpenAI models available to the user's project are configurable at runtime.

Verification method:

- inspect current code and migrations,
- run baseline locally,
- query source endpoints with non-secret smoke tests,
- generate one packet from a controlled job fixture,
- parse generated DOCX/PDF,
- compare UI/API/DB,
- perform one Drive upload,
- perform one Gmail sync,
- record evidence.

Do not make a full architecture rewrite decision until these checks are complete.
