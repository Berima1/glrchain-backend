# Google Cloud Deployment and Evidence Storage Runbook

**Status:** deployment guide; steps are not proof that the resources have already been provisioned.  
**Scope:** Google Cloud Platform (GCP) resources for GLRChain. Firebase/Firestore is not assumed to be the system of record unless the architecture decision explicitly changes.

## Architecture choice

The current API foundation uses SQLAlchemy and Alembic for relational persistence. The repository's current data model and migration workflow are relational. **Do not silently replace this with Firestore.** Firestore may be evaluated for specific document/event workloads, but adding it requires a documented data-model decision, access-control rules, backup/export plan, migration strategy and integration tests.

Cloud Storage is the proposed private object store for evidence files. It is separate from the relational database: store evidence bytes in the bucket and keep metadata, ownership, report linkage, content type, byte size, digest, and object identifier in the database.

## Required resources

Before a real environment test, the project owner or authorized cloud administrator must provision and document:

1. A dedicated GCP project with billing and organization policies appropriate to the intended deployment.
2. A private Cloud Storage bucket in a selected region, with uniform bucket-level access, public access prevention, encryption, retention policy where required, and audit logging.
3. A dedicated runtime service account with only the permissions needed for the specific bucket and application services. Do not use a downloaded service-account JSON key if workload identity or an attached service identity is available.
4. A managed PostgreSQL instance with private connectivity where possible, TLS, automated backups, point-in-time recovery if supported, and a documented restore test.
5. A secret manager for JWT signing and report-encryption keys.
6. A supported application hosting environment, network policy, TLS, health checks, logs, metrics, alerting, and deployment rollback.
7. A separate non-production environment and test bucket/database.

Do not place project IDs, credentials, private keys, connection strings, service-account JSON, or real report contents in GitHub files, issues, screenshots, or CI logs.

## Configuration inventory

The API configuration currently expects these environment variables where applicable:

| Variable | Purpose | Production requirement |
|---|---|---|
| `APP_ENV` | Environment mode | Set to `production` in production |
| `DATABASE_URL` | SQLAlchemy database connection | Required; must point to managed production PostgreSQL, never a local SQLite file |
| `SECRET_KEY` | JWT signing secret | Persistent, high-entropy secret from a secret manager |
| `REPORT_ENCRYPTION_KEY` | Fernet key for report-description encryption | Valid persistent key from a secret manager; never generate a new key at every restart |
| `LEGACY_REPORT_ENCRYPTION_KEY` | Optional old key for controlled key migration/decryption if implemented | Configure only under a reviewed key-rotation plan |
| `GLRCHAIN_EVIDENCE_BUCKET` | Private Cloud Storage bucket name | Required for production evidence upload/download |

Exact variable names and behaviour must be checked against the reviewed release commit before deployment. Do not copy secrets into a repository or this document.

## IAM principles

- Runtime service account: grant the minimum object read/write permissions to the one evidence bucket; avoid project-wide owner/editor roles.
- Deployment identity: separate from runtime identity; scope to the deployment target.
- Human administrators: use named identities, MFA and reviewed least-privilege roles.
- CI: do not grant production deploy permission to feature branches. Production deployment requires a protected main branch, approved environment and explicit approval.
- Never make the evidence bucket public. Downloads must be authorized by the API and checked against report/evidence ownership or an explicitly authorized administrative role.

## Verification procedure

Run this only in a designated non-production environment first.

1. Record the commit SHA, environment name, region, database instance identifier and bucket name (names only; no secrets).
2. Confirm the runtime identity is attached and can access only the intended resources.
3. Apply reviewed Alembic migrations as a controlled release step. Do not run schema changes from the image build stage.
4. Start the API and verify `GET /health/live`.
5. Verify `GET /health/ready` reports ready only when the configured database connection works.
6. Register a test account; confirm the public registration route cannot grant an administrator role.
7. Create a test report; query the database through an authorized administrative path and confirm the plaintext description is not stored.
8. Upload a synthetic, non-sensitive evidence file. Confirm the object is private, the database stores the expected SHA-256 and metadata, and download bytes match the uploaded bytes.
9. Attempt to retrieve the evidence as a different user and confirm access is denied without disclosing whether another user's record exists.
10. Review cloud audit logs for the test operations.
11. Test backup restore and secret recovery/rotation procedures in a separate test environment.
12. Record the outcomes, timestamps, commit SHA, responsible reviewer, and any failures in the release evidence record.

A mocked storage test is not a substitute for steps 2, 8, 9 and 10 against real GCP resources.

## Rollback and incident response

- Keep the last known-good image digest and deployment configuration.
- Roll back application versions without dropping or destructively rewriting database data.
- Database schema changes must be backward-compatible where possible; destructive migrations require a separate approved plan.
- If a key or service identity is compromised, revoke access, rotate the secret using the documented migration procedure, assess evidence access, preserve audit logs, and record the incident.
- If evidence integrity is in doubt, suspend automated downstream use and preserve the original object, digest, timestamps and access records for independent review.

## Status checklist

- [ ] GCP project and billing verified
- [ ] Production and staging separated
- [ ] Private evidence bucket provisioned
- [ ] Runtime service identity and least-privilege IAM reviewed
- [ ] Managed PostgreSQL configured with TLS and backups
- [ ] Secret manager configured and recovery procedure tested
- [ ] Alembic migration executed as a release step
- [ ] Real upload/download/hash/access-control test passed
- [ ] Cloud audit logs reviewed
- [ ] Restore test completed
- [ ] Monitoring and alerting tested
- [ ] Security and operational owner sign-off recorded
