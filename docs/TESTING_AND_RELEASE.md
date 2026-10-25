# Testing, Verification and Release Procedure

## Testing principles

- Tests must exercise real application behaviour, not print success messages or call stubs that return fabricated results.
- External services may be mocked for deterministic unit/integration tests, but a mocked result must be labelled as such.
- Every critical security rule needs a negative test (attempt the forbidden action and verify it fails).
- Every release candidate must be tied to a Git commit SHA and a saved CI run.
- CI success is necessary but not sufficient for production readiness.

## Current foundation CI

The foundation branch CI is intended to run:

1. Dependency installation.
2. Python compilation/syntax checks.
3. PostgreSQL/PostGIS service startup and Alembic migration validation.
4. Automated API tests.
5. Container image build.

Use the GitHub Actions history for the branch and record the exact run URL, commit SHA, outcome and any warnings in the PR. Do not treat an older green run as evidence for a later commit.

## API test coverage

The foundation test suite is intended to cover:

- Liveness and database readiness.
- Account registration and login.
- Public users cannot elevate their role during registration.
- Protected endpoints reject requests without a bearer token.
- Reports persist and report descriptions are encrypted in the database.
- Report owners can read their own report; another user cannot.
- The fabricated intelligence endpoint is not exposed.
- Evidence upload fails closed if private storage is not configured.
- Evidence upload/download logic records and checks SHA-256 and enforces owner access, with storage calls mocked in CI.
- Production database configuration fails closed rather than silently falling back to SQLite.

Review the actual test file and current CI logs for the exact coverage at each commit. Passing tests do not replace a live GCP end-to-end test.

## Local developer commands

Use a supported Python version matching CI. In a clean virtual environment:

```bash
python -m pip install -r requirements.txt
python -m pytest -q
python -m compileall -q app
```

Database migration verification requires the test PostgreSQL/PostGIS service and the environment variables used by CI. Do not run destructive migration tests against a live production database.

## Pull-request workflow

1. Work on a feature branch; do not commit directly to `main`.
2. Make one cohesive change per PR where possible.
3. Add or update tests for every behaviour change.
4. Update relevant docs and the work log in the same PR.
5. Run CI; inspect failed-step logs, not only the overall badge.
6. Request independent review of authentication, cryptography, migrations and evidence access changes.
7. Confirm no secrets, real evidence, personal data or private keys are included in the diff.
8. Review schema migration compatibility and rollback implications.
9. Record known limitations and test evidence.
10. Merge only after the project owner approves the diff and release gates are satisfied.

## Required release evidence

A release candidate is not approved until the PR records:

- [ ] Commit SHA and CI run URL for that exact SHA
- [ ] All required checks green, with warnings explained
- [ ] Database migration reviewed and tested against a clean database
- [ ] Authorization-negative tests passed
- [ ] Encryption-key persistence, recovery and rotation documented
- [ ] Real private-bucket end-to-end test passed in staging
- [ ] Backup restore test passed
- [ ] Security review completed
- [ ] Dependency vulnerability scan reviewed
- [ ] Observability, alerting and incident-response procedure tested
- [ ] Satellite detection validation evidence (before enabling detection)
- [ ] Blockchain deployment and independent transaction verification (before enabling anchoring)
- [ ] Project owner sign-off and rollback plan recorded

## Release states

- **Development:** rapid changes; synthetic data only.
- **Staging:** production-like configuration; controlled test data; end-to-end validation.
- **Production candidate:** all technical and operational release gates evidenced.
- **Production:** explicitly approved deployment with a named operational owner.

Do not call a scaffold, prototype or staging deployment "production-ready" solely because the web process starts or CI passes.
