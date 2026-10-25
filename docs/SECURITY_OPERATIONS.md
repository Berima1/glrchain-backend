# Security Operations Checklist

## Identity and account lifecycle
- Approve sign-in providers and onboarding policy with the sponsoring institution.
- Require stronger authentication for privileged users; consider MFA and managed/agency identities.
- Remove roles and revoke identity access promptly on offboarding.
- Record role changes with actor, approver, reason, effective time and before/after values.
- Do not provide public role-upgrade endpoints.
- The initial-admin command is one-time bootstrap only; unset its allow flag immediately after use.

## Secrets and key management
- Store secrets in Secret Manager with access restricted to specific runtime/workflow identities.
- Pin a specific tested version to each deployment; record the version reference, not secret value.
- Keep report encryption keys separate from authentication/deployment secrets.
- Back up critical encryption keys under an approved recovery policy; key loss can cause permanent ciphertext loss.
- Rotate a key through a tested re-encryption migration; test on a restored copy first.
- Never use report encryption keys in logs, GitHub, issue text, browser storage, or chat messages.

## Evidence handling
- Use private bucket-level IAM and block public access.
- Keep source file byte digests; preserve original uploaded files and record transformations as separate artifacts.
- Check the digest on every retrieval and do not mark a file “verified source” based only on its hash.
- Record failed object cleanup and reconcile orphaned objects safely.
- Establish malware scanning and file-retention/disclosure policy before production evidence intake.

## Audit and monitoring
- Schedule an audit-chain verification check and emit an alert if invalid.
- Export audit events to separately controlled Cloud Logging/retention; verify the exported copy.
- Alert on repeated failed login/token verification, unusual report access, privileged changes, storage failures, database failures and secret access.
- Avoid logging report text, precise sensitive coordinates, raw tokens, passwords or secrets.
- Preserve logs/exports and a database snapshot before incident remediation.

## Change management
- Require PR review and a green current-commit CI result.
- Pin action dependencies where practical and limit workflow permissions.
- Use Workload Identity Federation rather than long-lived GCP service-account keys.
- Keep feature branches from deploying to production.
- Record release SHA, image digest, migration execution, service revision, approver and rollback plan.
