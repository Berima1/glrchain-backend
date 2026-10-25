# GLRChain Deployment Guide

**Current status:** foundation branch / staging preparation. This guide does not certify a production deployment.

## Environments

- **Development:** synthetic data only; local SQLite is allowed only for development/test.
- **CI:** isolated PostgreSQL/PostGIS service and synthetic data. Evidence-storage calls may be mocked.
- **Staging:** production-like managed database, private evidence bucket and secrets; required before any live data.
- **Production:** only after all release gates are evidenced and the project owner approves the exact commit.

The existing Render URL, if still active, is a prototype/staging host—not evidence of national production readiness. Google Cloud is the proposed target for managed PostgreSQL, private Cloud Storage, secret management, IAM and operational logging. See [Google Cloud Deployment and Evidence Storage Runbook](docs/GOOGLE_CLOUD_DEPLOYMENT.md).

## Before deployment

1. Review [Project Status and Limitations](docs/PROJECT_STATUS_AND_LIMITATIONS.md).
2. Review the exact pull request and commit SHA.
3. Provision a separate staging environment and non-sensitive test data.
4. Configure managed PostgreSQL and verify backups/restore.
5. Configure the private evidence bucket and least-privilege runtime identity.
6. Store `SECRET_KEY` and `REPORT_ENCRYPTION_KEY` in a secret manager. The report encryption key must be a valid Fernet key and must remain persistent across restarts. Never generate a new key automatically in production.
7. Set `APP_ENV=production`, `DATABASE_URL`, `SECRET_KEY`, `REPORT_ENCRYPTION_KEY`, and `GLRCHAIN_EVIDENCE_BUCKET` for the deployed runtime.
8. Apply the reviewed Alembic migration as an explicit release operation against the target database. Do not run migrations during the container image build.
9. Verify `GET /health/live` and `GET /health/ready`.
10. Complete the real cloud evidence upload/download/hash/authorization test and record results.

## GitHub Actions

The CI workflow is for validation; it is not an implicit production deployment. Production credentials must not be exposed to pull-request builds or feature branches. Use a protected environment and explicit approval for deployment credentials.

## Render (prototype/staging only)

If the project owner chooses to keep Render for a temporary staging environment:

1. Connect the repository in the Render dashboard.
2. Configure the required environment variables in the Render service settings.
3. Do not enable production mode until the persistent database, valid secrets and private evidence bucket are actually configured.
4. Apply migrations as a controlled release step, not in the image build command.
5. Verify the deployed commit and perform staging smoke and authorization tests.

The repository's `render.yaml` is deployment configuration, not proof that any service or resource has been provisioned. If it conflicts with the reviewed release configuration, do not deploy until reconciled.

## Do not configure yet

Do not add unused blockchain RPC, IPFS, KMS, or service-account secrets merely because an older deployment guide listed them. Blockchain anchoring is not operational. Add secrets only when the corresponding feature has been implemented, reviewed, and tested.

## Rollback

Keep the prior image digest and commit reference. Roll back application code without dropping database tables. Database changes require a reviewed migration/rollback plan. See [Testing and Release Procedure](docs/TESTING_AND_RELEASE.md) and [Google Cloud Deployment Runbook](docs/GOOGLE_CLOUD_DEPLOYMENT.md).
