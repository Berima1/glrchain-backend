# GLRChain Security Threat Model

**Status:** Initial threat model; must be reviewed with the sponsoring institution and security specialists before any operational pilot.

## Assets to protect

- Informants/reporters' identity and safety.
- Reports and precise location descriptions.
- Original evidence files and their provenance.
- Land/permit data and any official-status determinations.
- Access tokens, encryption keys, database credentials, and deployment identities.
- Audit records and review decisions.
- Satellite products, model inputs, code, and resulting candidates.
- Availability and integrity of the service.

## Adversaries and failure modes

1. An unauthenticated caller attempts to read or submit sensitive reports.
2. A normal user attempts to become an admin/validator by adding a role field or forging a token.
3. A user guesses record IDs and reads another user's report or evidence.
4. An attacker uploads oversized, malformed, executable, or misleading files, or uses a filename/path traversal string.
5. An operator misconfigures a bucket as public or gives a runtime identity project-wide administrator access.
6. A leaked encryption key exposes stored report descriptions; rotating a key without migration makes old records unreadable.
7. A database operator alters an event or removes earlier audit events.
8. A false or misaligned satellite signal is misinterpreted as galamsey and harms an innocent person.
9. A migration, deployment, cloud outage, or transient retry creates lost, duplicated, or orphaned records.
10. A compromised GitHub workflow or developer identity deploys unreviewed code or exfiltrates secrets.

## Controls implemented in the foundation branch

- Short-lived signed bearer JWTs in local development mode; Firebase ID-token verification path for production identity.
- Server-side profile lookup: current role comes from PostgreSQL, not from client-supplied role fields.
- Public registration and Firebase provisioning assign only `user`.
- Report owner scoping; admin/validator exceptions are explicit in current routes.
- Report description encryption with explicit encryption-key version.
- Private GCS interface with size/type checks, create-only object writes, SHA-256 metadata and digest check on download.
- Attachment response headers (`no-store`, `nosniff`) for evidence downloads.
- Transactional audit events and a hash-chain verification endpoint.
- Fail-closed production configuration checks and no silent SQLite fallback for `APP_ENV=production`.
- PostgreSQL migration, API test, Python compile and Docker build gates in GitHub Actions.
- Deployment is manual and gated to a configured production environment; no feature-branch auto-deploy.

## Residual gaps / release blockers

- This foundation is not yet deployed or tested against a real Firebase project, private GCS bucket, Cloud SQL instance, or Google IAM policy.
- Rate limiting, abuse detection, session/device management and a formal lockout policy need implementation and validation.
- Formal review of cryptographic key lifecycle, KMS/CMEK needs, key rotation, and legacy report re-encryption remains.
- A production-ready external identity setup should include an approved Firebase provider policy, MFA or equivalent controls for privileged users, disabled/self-restricted public account creation as required, and audited offboarding.
- Role changes and routine admin creation need a controlled, audited workflow; the bootstrap command is only for first-admin setup.
- Malware scanning/quarantine, content disarm/reconstruction where appropriate, and policy for evidence file retention have not been implemented.
- Application-level audit rows can be modified by a sufficiently privileged database operator; external export, retention lock and independent verification remain required.
- Formal backup/restore and disaster-recovery drills, dependency/SBOM review, vulnerability scans, penetration test and load test remain open.
- No working satellite algorithm or real blockchain anchoring has been released.
- Incident response and reporting workflows need legal, privacy, records-retention and insider-threat review.

## Security response rules

- Never return success if persistence, encryption, evidence upload, hash verification or audit write fails.
- Never log report descriptions, tokens, passwords, secret values or sensitive source details.
- Do not weaken a failing test to obtain green CI. Fix the defect and retain a regression test.
- Revoke credentials and preserve incident evidence if exposure is suspected; do not commit replacement secrets to Git.
- Pause intake of sensitive real-world cases if the database, encryption keys, bucket privacy, authorisation or audit integrity is uncertain.
