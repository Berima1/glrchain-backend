# Operations Runbook

This runbook is for the controlled engineering environment. It is not a substitute for a signed institutional operating procedure.

## Health and readiness

- `GET /health/live` checks that the process responds.
- `GET /health/ready` checks database connectivity.
- Neither endpoint proves Firebase, evidence storage, audit export, satellite processing, or blockchain integrations work.

Monitor request failures, database connection errors, failed migrations, evidence upload/cleanup failures, report decryption errors, audit verification failures, unusual authentication failures and deployment changes. Do not include tokens, secret values, report descriptions or raw sensitive evidence in logs.

## Initial administrator bootstrap

The command `python -m app.commands.bootstrap_admin USERNAME FIREBASE_UID` is intended only for the initial controlled Firebase-backed admin profile after migrations.

Required environment conditions:
- `APP_ENV=production`
- `GLRCHAIN_ALLOW_INITIAL_ADMIN_BOOTSTRAP=true` for one operation only
- `FIREBASE_PROJECT_ID` for the intended Firebase project
- `GLRCHAIN_INITIAL_ADMIN_USERNAME` set to the exact pre-approved unused username
- `GLRCHAIN_INITIAL_ADMIN_FIREBASE_UID` set to the separately approved Firebase UID
- authorised Application Default Credentials for the one-time administrative command, including permission to look up the Firebase user
- configured database connection, audit tables, and dependencies installed

The command verifies that the Firebase user exists and has a verified email, refuses if an administrator already exists or the user/username is already mapped, assigns the Firebase UID, and records an audit event. After success, immediately remove/disable the bootstrap flag and one-time UID variable. Do not grant the API runtime identity Firebase user-administration privileges just for bootstrap. This is not a day-to-day account management process; routine admin/validator assignment needs a separately reviewed workflow.

Production uses Firebase Authentication for sign-in. A Firebase user is not an administrator merely because their client token is valid; profile role is stored in PostgreSQL and public provisioning assigns `user` only.

## Release process

1. Create/update a feature branch and PR.
2. Inspect the complete diff and documentation.
3. Run CI on the final exact commit and resolve every failure.
4. Review migration SQL and rehearse against a disposable copy with a backup.
5. Confirm production secret versions, identity policies, bucket access, DB roles, backup configuration and monitoring.
6. Use the protected, manual Cloud Run workflow only for approved code on `main`.
7. The workflow builds an immutable commit-tagged image, applies the Alembic migration through a Cloud Run Job, and deploys the API service.
8. Verify revision, `/health/live`, `/health/ready`, authenticated report creation/read, private evidence transfer and audit verification in the approved staging environment.
9. Record the release evidence in the release register and retain the preceding deployable image/revision.

## Incident: report description cannot be decrypted

1. Stop intake of sensitive reports if data readability is at risk.
2. Preserve logs and database backup/snapshot before changing keys.
3. Identify `encryption_key_version` and the exact historical key version required.
4. Check Secret Manager version/reference without printing the key.
5. Test decryption on an isolated restored copy.
6. Do not generate a replacement key and assume old data will remain readable.
7. Document the cause, scope and recovery, then follow formal key-rotation requirements.

## Incident: evidence hash mismatch or inaccessible object

1. Do not return the file as verified.
2. Record the evidence ID, stored digest, computed digest and relevant object generation metadata without logging the file body.
3. Preserve the object and database records; do not overwrite the evidence in place.
4. Check bucket IAM, object version/generation, lifecycle/retention changes and upload/cleanup logs.
5. Verify against a known-good backup/version and escalate to an authorised reviewer.
6. A corrected evidence item must be stored as a new version/record with provenance, not silently substituted.

## Incident: audit chain fails verification

1. Treat the integrity alarm as material; preserve a database snapshot and export current audit events.
2. Restrict further administrative changes pending review, without destroying records.
3. Verify the external audit export/retention sink, not only the live database.
4. Compare the first invalid sequence and surrounding events with database/cloud audit logs.
5. Never rebuild the chain to make it look valid before the incident is investigated.
6. Record the independent reviewer, findings, evidence hashes and disposition.

## Recovery and backup

- Enable Cloud SQL automated backups and point-in-time recovery according to the approved RPO/RTO.
- Test a restore into an isolated instance regularly; a successful backup job alone is not a restore test.
- Keep evidence retention/versioning aligned with legal policy and cost controls.
- Ensure migration identity and application runtime identity are separate.
- Reconcile orphaned GCS objects and dangling metadata via a documented, dry-run-first maintenance job.
