# GLRChain — Ghana Land & Natural Resources

GLRChain is intended to support auditable land and natural-resource reporting, protected evidence handling, and eventually validated satellite-change candidates for authorised human review.

**Current release state: engineering foundation under review, not approved for national production use.** This repository does not currently deliver a validated satellite detector or a real blockchain anchoring service. Do not describe either as operational.

## What the current foundation contains

- PostgreSQL-backed users, reports, evidence metadata and schema migrations.
- Local username/password mode for controlled development and automated tests.
- A production path for server-side Firebase ID-token verification and profile provisioning. Public provisioning assigns only the normal `user` role.
- New report descriptions and locations are encrypted with explicit key versions; legacy plaintext locations and legacy encrypted descriptions are versioned separately for backward-compatible migration.
- Private Google Cloud Storage upload/download code, size and file-signature checks, SHA-256 recording and verification.
- Transactional, hash-chained application audit events for key report/evidence/account operations, plus privileged chain verification.
- Real database-backed admin statistics.
- CI checks for Python compilation, PostgreSQL/PostGIS migrations, automated API tests and Docker image build.
- A manual Google Cloud Run deployment workflow gated to `main`, using Workload Identity Federation rather than a service-account key file.

## Important system boundaries

- **Authoritative database:** Cloud SQL/PostgreSQL with PostGIS is the target for official records and future geometry queries. Firestore is not used as the authoritative store by this API; it may support carefully designed realtime features later.
- **Evidence:** bucket configuration and real Google Cloud IAM must be tested before sensitive evidence is accepted. The current automated evidence tests use a controlled storage stub; they do not prove a real bucket is configured.
- **Audit:** the hash chain is tamper-evident, not immutable. A database superuser could rewrite the entire table and head. Independent audit export and retention are still required.
- **Geospatial detection:** no production Sentinel-1/Sentinel-2 acquisition or change-detection algorithm is released.
- **Blockchain:** no working contract deployment/transaction confirmation is released. Fake anchoring routes have been removed from active API code.
- **Deployment:** no deployment should occur simply because the workflow exists. Real Google Cloud resources, identity, secrets, database roles, bucket policy, backup and monitoring configuration must be completed first.

## API endpoints

| Endpoint | Purpose |
|---|---|
| `GET /` | Service metadata |
| `GET /health/live` | Process liveness |
| `GET /health/ready` | Database readiness |
| `POST /auth/register`, `POST /auth/login` | Local development/test identity only |
| `POST /auth/provision` | Create/idempotently return a GLRChain profile for an already verified Firebase ID token |
| `GET /auth/me` | Return the caller's current profile |
| `POST /reports`, `GET /reports`, `GET /reports/{report_id}` | Authenticated, access-controlled report operations |
| `POST /evidence`, `GET /evidence/{evidence_id}`, `GET /evidence/{evidence_id}/content` | Private evidence handling and integrity-checked retrieval |
| `GET /admin/stats` | Real database counts; administrator only |
| `GET /admin/audit/events` | Audit events; administrator/validator only |
| `GET /admin/audit/verify` | Audit-chain verification; administrator/validator only |

Interactive API docs are available at `/docs` when a configured instance is running.

## Configuration

Runtime configuration expected for a production API:

- `APP_ENV=production`
- `GLRCHAIN_AUTH_PROVIDER=firebase`
- `FIREBASE_PROJECT_ID`
- `DATABASE_URL` for the least-privilege runtime PostgreSQL user
- `SECRET_KEY` (persistent compatibility/application secret; never commit it)
- `REPORT_ENCRYPTION_KEY` (persistent Fernet key; store in Secret Manager and pin a tested version)
- `GLRCHAIN_EVIDENCE_BUCKET` (private bucket name)

If migrating legacy records, configure `LEGACY_REPORT_ENCRYPTION_KEY` to the correct historical Fernet key as documented in the operations guide. Never rotate or replace the old key before verifying legacy decryption on a restored copy.

Use `requirements-dev.txt` for tests. Optional worker and ML packages are separated into `requirements-worker.txt` and `requirements-ml.txt`.

## Documentation

- [Project charter](docs/PROJECT_CHARTER.md)
- [Architecture and data flow](docs/ARCHITECTURE.md)
- [Data dictionary](docs/DATA_DICTIONARY.md)
- [Security threat model](docs/SECURITY_THREAT_MODEL.md)
- [Security operations](docs/SECURITY_OPERATIONS.md)
- [Google Cloud/Firebase setup and deployment](docs/GOOGLE_CLOUD_SETUP.md)
- [Operations runbook](docs/OPERATIONS_RUNBOOK.md)
- [Testing and validation strategy](docs/TESTING_AND_VALIDATION.md)
- [Release gates](docs/RELEASE_GATES.md)
- [Architecture decisions](docs/DECISIONS.md)
- [Engineering work log](docs/WORK_LOG.md)

## Local validation

```bash
pip install -r requirements-dev.txt
python -m compileall -q app
alembic upgrade head
python -m pytest -q
docker build -t glrchain-backend:test .
```

Use test-only keys and synthetic data. Never run database migrations against production merely to experiment. Review `docs/RELEASE_GATES.md` before any release.

## Project status and team discipline

The first foundation pass repaired the reporting/database/authentication path and established a real CI pipeline. Further audit, Firebase, migration and Cloud Run changes are under review and must pass CI at the exact final commit before merging. A green CI run validates only the checks that it actually ran; it is not evidence that the national system, cloud integrations, detection model or blockchain are production-ready.
