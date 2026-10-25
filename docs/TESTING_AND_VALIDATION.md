# Testing and Validation Strategy

## Current automated checks

The repository workflow `.github/workflows/ci.yml` is designed to:

1. Install API/test dependencies on Python 3.11.
2. Compile the application modules.
3. Apply Alembic migrations to a fresh PostgreSQL/PostGIS service database.
4. Run automated API security, persistence and evidence/audit tests.
5. Build the API container.

The initial API foundation achieved a successful CI run at commit `eb4862dad3e0969fc1eeb93231adeb8e027d283b` with eight tests passing and the image build complete. Additional audit-chain, Firebase identity and migration changes were added after that commit; they require their own current successful CI run before they can be treated as verified. Always use the latest result for the exact commit SHA rather than relying on an earlier green run.

## Test categories

### Unit/contract tests

- URL normalisation and production fail-closed configuration.
- Password hash verification and legacy hash upgrade.
- Report encryption key version behaviour.
- SHA-256 calculation, evidence type signature checks, filename sanitisation.
- Canonical audit payload serialization and hash recomputation.

### API tests

- Public registration/provisioning always receives the normal user role.
- Local-mode login issues a short-lived token; unauthenticated routes cannot read protected data.
- Firebase-mode token verification maps a verified UID to a profile; password login is rejected in Firebase mode.
- Report descriptions and new report locations persist as ciphertext and decrypt correctly on authorised reads; legacy location version 0 remains backward-compatible.
- Owner scoping denies other users access.
- Evidence uploads fail closed without bucket config and enforce the accepted signatures/size limit.
- Successful upload/download records digest metadata and refuses modified content.
- Privileged audit endpoints deny normal users.
- Audit chain verification succeeds for unchanged rows and detects modified event data.

### Database/migration tests

- Upgrade an empty PostgreSQL database to the current head.
- Upgrade a representative database containing the legacy `users` and `reports` schema.
- Verify the migration preserves existing report ciphertext and labels key version 1 rather than silently re-encrypting it.
- Verify nullable legacy ownership is treated according to a documented remediation plan.
- Exercise duplicate usernames/Firebase UIDs and concurrent audit appends.
- Exercise downgrade in an isolated disposable database only; never use a downgrade as an unreviewed production rollback.

### Cloud integration tests (not yet completed)

- Firebase Authentication with a real project and revoked/expired token cases.
- Cloud SQL connectivity using Cloud Run runtime and migration identities.
- Private Cloud Storage upload, retrieval, generation preconditions, digest verification and failed-cleanup alerts.
- Secret Manager version access and key rotation.
- Cloud Logging export, audit export verification, backup restoration and recovery-time measurement.

### Satellite model evaluation (not yet implemented)

Use a labelled Ghana-specific reference set and a written validation protocol. Record input scene IDs, time windows, cloud/quality masks, region/season, model and processing versions. Report false positives and false negatives at both pixel and polygon/incident level. Keep the evaluation set independent from training/tuning data. Do not launch enforcement based on a score without human confirmation.

## How to reproduce locally

Install dependencies with `pip install -r requirements-dev.txt`, set a test database URL and test-only keys, then run:

```bash
python -m compileall -q app
alembic upgrade head
python -m pytest -q
docker build -t glrchain-backend:test .
```

Do not use production report-encryption keys or real reporter data in local tests. Test-created database files are ignored by Git.

## CI interpretation

- **Green** means the checks in that workflow passed at that exact commit; it does not prove the whole system is production-ready.
- **Red** is a useful defect report. Save the log, fix the cause and add/retain a regression test.
- **Cancelled/pending** is not a pass.
- A Docker image build is not a deployment, and a successful process health check is not evidence that workflows or integrations work.
