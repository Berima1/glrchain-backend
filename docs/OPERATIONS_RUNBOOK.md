# GLRChain Operations Runbook

**Status:** baseline runbook to adapt and test before staging/production.

## 1. Health checks

- Liveness endpoint: confirms the application process responds; it does not prove database or storage availability.
- Readiness endpoint: should verify the required database dependency and return a non-ready status when unavailable.
- Evidence-storage readiness: must be monitored separately; do not claim evidence upload is ready based only on API liveness.
- Monitor HTTP error rate, authentication failures, database connection pool exhaustion, migration failures, storage errors, processing queue depth, job age, and alert/review backlog.

Use the deployed environment's actual endpoint paths and verify them against the release commit before configuring probes.

## 2. Deployment

1. Confirm the approved PR, commit SHA and green required checks.
2. Confirm the target is staging or production and that secrets are set through the secret manager.
3. Verify database backup status and migration plan.
4. Build once and deploy the same immutable image digest that was tested.
5. Run migrations as a controlled release step.
6. Run smoke tests with synthetic accounts and files.
7. Check logs/metrics and confirm no sensitive values are emitted.
8. Record deployment time, image digest, commit SHA, operator and outcome.

## 3. Evidence upload failure

If private object storage is unavailable:
- Stop accepting evidence uploads; do not silently write to local ephemeral disk.
- Preserve the report metadata only if the API contract explicitly supports that partial state; otherwise fail the request and report a safe error.
- Do not return a fake storage object ID or success response.
- Check runtime identity, IAM, bucket configuration, network access, quota and cloud audit logs.
- Retry only idempotently; do not create duplicate evidence records.
- Record incident ID and recovery actions without copying evidence content into logs.

## 4. Database incident

- Treat connection failures, migration mismatch or unexpected schema as an incident.
- Do not delete tables or rerun destructive migrations to restore service.
- Preserve logs and database diagnostics while redacting credentials and report content.
- Restore from backup only under an approved recovery plan and record the recovery point.
- After restore, verify schema version, report counts and sample integrity using authorized procedures.

## 5. Secret/key incident

- Revoke compromised identity or secret.
- Determine which tokens or encrypted records may be affected.
- Rotate through the approved key lifecycle procedure; do not replace the encryption key blindly because existing encrypted values may become unreadable.
- Preserve relevant audit logs, investigate access and document the incident.
- Validate the recovery procedure in staging before using it in production.

## 6. Suspected evidence-integrity incident

- Restrict access to the affected case without destroying data.
- Preserve original object versions, recorded digests, timestamps and access events.
- Recompute the SHA-256 digest and compare with the trusted recorded value.
- Document who performed verification, when, which bytes/object version was checked, and the result.
- Do not treat a mismatch as proof of malicious activity until storage/versioning and processing history are examined.

## 7. Satellite pipeline incident (future capability)

- Pause alert publication if source data, georeferencing, model version or provenance is missing.
- Retain source scenes and processing logs; do not substitute fabricated or stale imagery.
- Mark affected candidate alerts as under review and notify authorized reviewers.
- Resume only after the issue is understood, reprocessing is reproducible, and the responsible reviewer approves.

## 8. Rollback

- Roll back application code to the last known-good image if needed.
- Avoid destructive database rollback; use backward-compatible schema migrations and a separately reviewed data-recovery plan.
- Verify health, authentication, report ownership checks and evidence access after rollback.
- Record the trigger, affected versions, operator, time, impact and follow-up actions.

## 9. Incident record template

- Incident ID:
- Start/end time (UTC):
- Environment and commit/image:
- Reporter and incident lead:
- Impacted component/data scope:
- Detection method:
- Containment and recovery steps:
- Evidence/log references:
- Root cause and contributing factors:
- User/agency notification decision:
- Corrective actions, owner and due date:
- Review/sign-off:
