# Google Cloud Setup and Deployment

**Status:** Deployment guide/target configuration; no real cloud resource has been provisioned or validated by this repository change.  
**Important:** Complete this guide in a dedicated GLRChain Google Cloud project. Do not reuse credentials or service identities from unrelated products.

## 1. Create and protect the project

1. In the Google Cloud Console, create/select a dedicated project for GLRChain and record its project ID.
2. Enable billing and create budget alerts before enabling expensive services.
3. Choose a region only after confirming data-residency/legal requirements, product availability, latency and cost. Keep Cloud Run, Cloud SQL and the evidence bucket in compatible approved locations where possible.
4. Enable at least Cloud Run, Cloud SQL Admin, Artifact Registry, Secret Manager, Cloud Storage, Cloud Build if used, and Firebase Authentication APIs/services as required.
5. Do not grant all project users Owner/Editor. Protect the project owner account with strong MFA and keep emergency access separate.

## 2. Configure Firebase Authentication

1. In Firebase Console, add Firebase to the dedicated Google Cloud project.
2. Open **Authentication → Sign-in method** and enable only the identity providers approved for the intended users.
3. Configure authorised domains and the client app (web/Android) with the correct Firebase project settings.
4. Decide whether public self-registration is permitted. National/agency accounts may require invitation or controlled onboarding rather than open registration.
5. The client must send its Firebase **ID token** to this API in the header `Authorization: Bearer <ID_TOKEN>`. Do not send a Firebase custom token as if it were an ID token.
6. After sign-in, call `POST /auth/provision` with a chosen username and the Firebase ID token. The backend verifies the token and creates only a normal `user` profile. It never accepts a client-supplied privileged role.
7. The Cloud Run service uses its service identity/Application Default Credentials and `FIREBASE_PROJECT_ID`; do not download and embed a service-account JSON key.

Official reference: [Firebase server-side ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens).

## 3. Create Cloud SQL PostgreSQL and enable PostGIS

1. Create a Cloud SQL for PostgreSQL instance in the approved region. Start with a non-production/staging instance until resource sizing and costs are understood.
2. Enable automated backups and point-in-time recovery per the approved recovery target.
3. Create a GLRChain database and separate database users:
   - **Migration user:** controlled DDL privileges, used only by the migration Cloud Run Job.
   - **Runtime user:** only the table/sequence permissions required by the API; no ownership or schema-alter privileges.
4. Connect through Cloud Run's Cloud SQL integration. Give the Cloud Run runtime and migration service identities the Cloud SQL Client role as required.
5. Enable PostGIS on the primary instance using an authorised database account: `CREATE EXTENSION postgis;`. Verify the extension version and supported service configuration first.
6. Store two separate connection strings in Secret Manager:
   - `glrchain-runtime-database-url`: connection URL for the runtime user.
   - `glrchain-migration-database-url`: connection URL for the migration user.
7. The URL should use the Cloud SQL Unix socket path in the form supported by your Cloud Run/Cloud SQL configuration, e.g. `postgresql+asyncpg://USER:PASSWORD@/DATABASE?host=/cloudsql/INSTANCE_CONNECTION_NAME`. URL-encode special characters in the user/password, verify connectivity in staging, and never paste the real URL into GitHub or chat.

Official references: [Connect Cloud Run to Cloud SQL PostgreSQL](https://docs.cloud.google.com/sql/docs/postgres/connect-instance-cloud-run), [Cloud SQL extension support](https://docs.cloud.google.com/sql/docs/postgres/extensions).

## 4. Create private evidence storage

1. Create a dedicated Cloud Storage bucket for GLRChain evidence.
2. Enable **uniform bucket-level access** and **public access prevention**. Do not grant `allUsers` or `allAuthenticatedUsers` object access.
3. Set retention, versioning, lifecycle and deletion rules only after the institution approves records retention and legal-hold requirements.
4. Give the **runtime service identity only** the required bucket-level role. `roles/storage.objectUser` supports object creation/read/update/delete; if a custom least-privilege role is approved, use that instead. Avoid granting Storage Admin at project scope.
5. Store the bucket name in `GLRCHAIN_EVIDENCE_BUCKET`.
6. Test actual upload/download/hash checks with a non-sensitive synthetic test file and a real staging bucket before accepting real evidence.

Official reference: [Cloud Storage IAM roles](https://docs.cloud.google.com/storage/docs/access-control/iam-roles).

## 5. Configure secrets

Create persistent secrets through Secret Manager (or the approved equivalent):
- `glrchain-runtime-database-url`
- `glrchain-migration-database-url`
- `glrchain-secret-key`
- `glrchain-report-encryption-key`
- `glrchain-legacy-report-encryption-key` only if existing version-1 ciphertext requires the historical key.

Generate a Fernet key once for `REPORT_ENCRYPTION_KEY`, store it securely, and pin a tested secret version in deployment. Key loss means the associated ciphertext cannot be decrypted. Do not rotate the encryption key casually. Keep the legacy key only for the migration window and retire it after a reviewed re-encryption/migration plan.

Google recommends least privilege and pinned secret versions: [Secret Manager best practices](https://docs.cloud.google.com/secret-manager/docs/best-practices).

## 6. Configure service identities

Create distinct identities:

| Identity | Needed access |
|---|---|
| API runtime | Connect to Cloud SQL with runtime DB user; read the required Secret Manager versions; read/write evidence objects in the approved bucket; use Firebase Admin verification |
| Migration job | Connect to Cloud SQL with migration DB user; read the pinned migration DB URL and required migration configuration |
| Geospatial worker (future) | Read approved imagery inputs; write job outputs and authorised candidate records; no user administration privileges |
| GitHub deployer | Deploy Cloud Run services/jobs and publish images; impersonate only the approved runtime/migration service accounts; no report/evidence data access |

Never create long-lived service-account JSON keys for GitHub Actions if Workload Identity Federation is available. Configure the Workload Identity Provider to trust only the intended GitHub repository and approved branch/environment.

## 7. GitHub Actions configuration

The workflow `.github/workflows/deploy_cloud_run.yml` is manual and must run from `main` after review and protected-environment approval. Configure these GitHub repository/environment **Variables** (not secrets unless noted):

- `GCP_PROJECT_ID`
- `GCP_REGION`
- `GCP_ARTIFACT_REGISTRY_REPOSITORY`
- `GCP_CLOUD_RUN_SERVICE`
- `GCP_CLOUD_SQL_INSTANCE` (connection name: project:region:instance)
- `GCP_RUNTIME_SERVICE_ACCOUNT`
- `GCP_MIGRATION_SERVICE_ACCOUNT`
- `GCP_EVIDENCE_BUCKET`
- `GCP_WORKLOAD_IDENTITY_PROVIDER`
- `GCP_DEPLOYER_SERVICE_ACCOUNT`
- `GCP_RUNTIME_DB_SECRET_REF` (for example secret-name:approved-version-number)
- `GCP_MIGRATION_DB_SECRET_REF`
- `GCP_SECRET_KEY_SECRET_REF`
- `GCP_REPORT_ENCRYPTION_SECRET_REF`

Add a protected GitHub Environment named `production` with required approvers. Do not copy actual secrets into repository files, workflow source, screenshots, issues or chat. The workflow should fail closed if any required variable is missing.

## 8. Migration and deploy order

The intended manual release workflow:

1. Authenticate to Google Cloud via GitHub OIDC/Workload Identity Federation.
2. Build and publish an image tagged with the exact Git commit SHA to Artifact Registry.
3. Run `alembic upgrade head` as a Cloud Run Job using the migration service account/DB identity.
4. Stop if the migration job fails.
5. Deploy Cloud Run API using the runtime service account, Cloud SQL connection, pinned secrets and production settings:
   - `APP_ENV=production`
   - `GLRCHAIN_AUTH_PROVIDER=firebase`
   - `FIREBASE_PROJECT_ID=<project-id>`
   - `GLRCHAIN_EVIDENCE_BUCKET=<private-bucket>`
6. Verify the deployed revision and `/health/live`, `/health/ready`, Firebase-authenticated profile, report create/read, private evidence upload/download, audit verification, and logs.
7. Record the commit SHA, image digest, Cloud Run revision, migration job execution, checks, approver and rollback target.

Cloud Run's public HTTPS URL may be reachable without Google IAM authentication for client access, but all sensitive application data endpoints must enforce Firebase identity and application-level authorisation. Do not interpret an open liveness endpoint as access to report data.

## 9. Firestore policy

Firestore is not currently used by this API for official records. It may later be used for realtime notifications/status views if the write model is defined. If so:
- PostgreSQL/PostGIS remains the source of truth.
- Use an outbox/synchronisation design with idempotent event IDs and retries.
- Specify acceptable lag, conflict resolution and reconciliation.
- Do not make authoritative decisions from a stale mirror.
- Test Firestore Security Rules independently and prevent client writes to server-owned fields.

Firestore geohash queries are approximate and require false-positive filtering; they are not a replacement for precise polygon operations. See [Firestore geoqueries](https://firebase.google.com/docs/firestore/solutions/geoqueries).

## 10. What is not automatic

This repository change does not create Google Cloud resources, enable billing, configure Firebase providers, establish IAM policies, create secrets, perform data migration from Render, approve Ghana data policy, or deploy the service. Those are explicit controlled setup steps with real cloud credentials and approval.
