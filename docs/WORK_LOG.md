# GLRChain Engineering Work Log

## 2026-10-25 — Foundation hardening and documentation

### Starting point reviewed

Inspected the live GitHub contents of `Berima1/glrchain-backend` and found broken/missing database session wiring, a report insert into a table not represented in the ORM model, local file evidence storage, public endpoints without sufficient authentication, hard-coded intelligence alerts, a fake `0xDEMO` anchor, unimplemented NBR/SAR/U-Net modules, and placeholder CI tests.

### Repository workflow

- Created feature branch: `foundation/production-hardening-2026-10`.
- Opened draft PR: [#1 — GLRChain foundation hardening](https://github.com/Berima1/glrchain-backend/pull/1).
- Kept `main` untouched and did not intentionally deploy the branch.
- Replaced the placeholder CI workflow with compilation, PostgreSQL/PostGIS migrations, API tests and Docker image build.
- A prior foundation commit `eb4862dad3e0969fc1eeb93231adeb8e027d283b` passed the then-current workflow: 8 tests passed, migration passed, and Docker build passed. Later changes to audit-chain handling, Firebase authentication, and migrations were subsequently added; the latest verification must be checked against the newest commit before merging.

### Implementation changes in the branch

- Centralised async database engine/session and URL normalisation.
- Added report/evidence models and Alembic migration steps for roles, ownership, timestamps, evidence metadata, audit events and Firebase UID mapping.
- Added local-mode short-lived bearer JWT authentication with server-controlled roles and password-hash upgrade logic.
- Added Firebase ID-token verification/provisioning path for production; production startup requires Firebase provider configuration.
- Added description encryption and later location encryption with explicit key versions; legacy encrypted descriptions are marked version 1 and legacy plaintext locations version 0 rather than silently rewritten.
- Added private GCS evidence code with file signature/size limits and SHA-256 validation.
- Added transactional hash-chained audit events for registration/login/report/evidence/admin-stat operations, plus privileged verification and event listing.
- Added a controlled one-time initial-admin command (not an HTTP route).
- Removed inactive fake intelligence/scoring/anchoring and temp-file evidence route modules from the branch.
- Added API-only, optional worker, and optional ML dependency lists.
- Added architecture, project charter, data dictionary, threat model, Google Cloud setup, operations runbook, testing strategy, release gates and architecture decisions.

### Known limitations and actions

- Real Google Cloud resources are **not** provisioned/validated by this change.
- Current Firebase token verification path requires a real Firebase project/service identity integration test.
- Current GCS upload/retrieval path requires a real private staging bucket test.
- Audit chain is tamper-evident but not immutable; independent audit export/retention is not yet implemented.
- Legacy report data may need a verified key/ownership migration before moving from Render.
- No validated satellite change-detection pipeline is implemented.
- No real blockchain contract deployment/transaction anchoring is implemented.
- Further tests are required for final commit, including audit chain concurrency/tamper test, Firebase mode, fresh/upgrade migrations, and Docker build.
- Review the complete PR diff; do not merge while checks are pending/failing and do not deploy until all release gates that apply are approved.


### Additional hardening after the initial audit/Firebase pass

- New report locations are encrypted alongside descriptions. Migration `0005_location_encryption` marks old plaintext locations as version 0 and widens the database field to safely hold ciphertext. The downgrade is intentionally blocked because shrinking back to the old width could truncate encrypted values.
- Added a strict CORS origin allowlist; production startup and the Cloud Run release workflow require approved frontend origins.
- Changed initial administrator bootstrap to require a pre-approved, verified Firebase UID and to create a Firebase-backed admin profile, not a local-password account that production Firebase mode would reject.
- Current CI must be rechecked at the newest commit to verify these later code and test changes; earlier green results do not automatically apply to newer commits.
