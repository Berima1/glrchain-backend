# GLRChain API — Ghana Land & Natural Resources

GLRChain is intended to support auditable land and natural-resource records, protected incident reporting, evidence chain of custody, and eventually validated geospatial change detection for authorised human review.

This repository is under staged hardening. **It is not currently approved for national production deployment.** Do not describe satellite detection, AI risk scoring, blockchain anchoring, or Firebase integration as operational unless their implementation, configuration, and independent tests are merged and verified.

## Implemented in the current API branch

- User registration creates only the normal `user` role. Privileged roles cannot be assigned through public registration.
- Password login issues time-limited bearer JWTs; protected routes check the token and database account.
- Reports are persisted in PostgreSQL and their descriptions are encrypted with a separately configured Fernet key.
- Report access is scoped to the submitter unless the database account has a privileged role.
- Evidence upload uses a private Google Cloud Storage bucket, verifies supported file signatures, enforces a size limit, records SHA-256 metadata, and verifies the digest on download.
- Missing secrets or evidence-storage configuration cause explicit failures instead of fake success responses.
- Alembic migrations and automated API tests are part of CI.

## Required runtime configuration

- `DATABASE_URL`: PostgreSQL connection URL (PostGIS-enabled PostgreSQL is recommended for the future geospatial layer).
- `SECRET_KEY`: a persistent random secret of at least 32 characters for JWT signing.
- `REPORT_ENCRYPTION_KEY`: a persistent Fernet key for new report descriptions (key version 2), generated once and stored in a secret manager. Do not regenerate it on every restart.
- `LEGACY_REPORT_ENCRYPTION_KEY`: set to the original Fernet-compatible `SECRET_KEY` used by the previous deployment if existing version-1 reports need to be read and that value is no longer the current `SECRET_KEY`. Keep it only for the required migration window, then perform a controlled re-encryption/key-rotation operation before retiring it. Never guess or silently replace a missing legacy key.
- `GLRCHAIN_EVIDENCE_BUCKET`: the name of a private Google Cloud Storage bucket. The deployed service identity needs only the permissions required to write, read, and delete the evidence objects it owns.

Use Google Cloud Secret Manager or an equivalent managed secret store. Never commit production values to GitHub. Configure the bucket with uniform bucket-level access, public access prevention, appropriate retention/versioning policies, and an audited service identity before accepting sensitive evidence.

For a local-only test run, install `requirements-dev.txt`. The test suite explicitly enables schema creation only in the test process; deployed environments must run Alembic migrations. The API-only image does not install the optional deep-learning stack; see `requirements-worker.txt` and `requirements-ml.txt` for separated worker dependencies.

## API overview

- `GET /`: service metadata.
- `GET /health/live`: process liveness.
- `GET /health/ready`: database readiness.
- `POST /auth/register`, `POST /auth/login`, `GET /auth/me`: account and token endpoints.
- `POST /reports`, `GET /reports`, `GET /reports/{report_id}`: authenticated, access-controlled reporting.
- `POST /evidence`, `GET /evidence/{evidence_id}`, `GET /evidence/{evidence_id}/content`: private evidence storage and integrity-checked retrieval.
- `GET /admin/stats`: real database counts, administrators only.

Interactive API documentation is available at `/docs` when the service is running.

## Not yet approved / remaining engineering work

1. Provisioning and governance for authorised MLNR/admin/validator accounts, including audited role changes and multi-factor identity controls.
2. Formal audit events and tamper-evident chain-of-custody logging, retention rules, backup/restore drills, and access reviews.
3. Google Cloud deployment, service-account least privilege, private networking, managed secrets, monitoring, alerting, and disaster recovery.
4. Real Sentinel-1/Sentinel-2 acquisition and geospatial change detection with a labelled Ghana validation set, measured false-positive rates, and a human-review workflow. No placeholder detector should be enabled.
5. Real blockchain anchoring using a governed network and verified transaction receipts; no demo transaction IDs are accepted.
6. Security review, load testing, threat modelling, and an independently signed release checklist.

An HTTP 200 response only confirms the corresponding endpoint responded; it does not certify the whole national system.
