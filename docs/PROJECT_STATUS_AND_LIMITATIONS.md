# GLRChain — Project Status and Limitations

**Status date:** 2026-10-25  
**Repository:** `Berima1/glrchain-backend`  
**Working branch:** `foundation/production-hardening-2026-10`  
**Audience:** project owner, reviewers, auditors, MLNR technical stakeholders

## Purpose

GLRChain is intended to support Ghanaian land and natural-resource integrity: secure reporting, evidence handling, auditable case workflows, and—after independent implementation and validation—geospatial monitoring to help identify potential illegal mining and land/resource changes. It is a decision-support and evidence-management system, not an autonomous enforcement authority. Human review and documented procedures are required before an alert is treated as a finding.

## Status vocabulary

- **Implemented:** code exists in the repository.
- **Automated-tested:** a named automated test exercises the behaviour in CI.
- **Environment-dependent:** code requires cloud resources, secrets, permissions, or deployment configuration not proven by a local/CI test.
- **Not implemented / not operational:** no production capability should be claimed.
- **Not verified:** evidence is insufficient to claim a capability works in the target deployment.

## Foundation milestone

The working branch introduces or hardens these API foundations:

- SQLAlchemy models and Alembic migrations for persistent application data.
- Authentication endpoints using signed bearer tokens and password hashing.
- Role assignment safeguards so public registration cannot self-assign privileged roles.
- Authenticated report creation and owner-scoped report retrieval.
- Encryption of report descriptions before persistence.
- Evidence object-storage integration code, with SHA-256 metadata and owner-scoped download logic.
- Health/liveness and database-readiness endpoints.
- Administrative statistics backed by database queries.
- Automated API tests, migration checks, Python compilation, and a container-build CI job.

These statements describe repository code and the checks run against the working branch. They do **not** prove that a live cloud deployment, Google Cloud project, real storage bucket, production identity setup, or government operational workflow has been configured and independently tested.

## Current capability boundaries

| Capability | Current status | What is required before production use |
|---|---|---|
| API authentication and authorization | Implemented; automated-tested for core cases | Review token settings, account lifecycle, rate limits, audit events, admin provisioning and recovery |
| Report persistence | Implemented; automated-tested | Run migrations on the target managed database; verify backup, restore, retention and access controls |
| Report-description encryption | Implemented; automated-tested | Provision and protect persistent encryption keys; define rotation, recovery and incident procedures |
| Evidence upload/download | Integration code and mocked storage tests | Configure a real private Cloud Storage bucket, service identity, IAM, retention, audit logs, malware/content validation, size limits and end-to-end tests |
| SHA-256 evidence digest | Implemented in upload flow | Independently verify digest on retrieval and preserve signed chain-of-custody events |
| Administrative statistics | Database-backed foundation | Define roles and least privilege; audit all privileged access and changes |
| Satellite imagery ingestion | Not production-operational | Select authoritative data sources, credentials/terms, ingestion scheduler, retry and provenance design |
| Galamsey/change detection | Not production-operational | Implement geospatial processing, geographic validation, calibration, independent validation and human-review workflow |
| Blockchain anchoring | Not production-operational | Deploy and verify the chosen network/contract, transaction signing, retry/idempotency, finality and independent verification |
| National-scale operations | Not verified | Capacity/load tests, disaster recovery, security review, monitoring, incident response, privacy/legal review and operational ownership |

## Important interpretation of CI

A green CI run means only that the checks configured in that run passed for the tested commit. It does not establish regulatory compliance, penetration-test completion, production availability, accurate satellite detections, real cloud-bucket connectivity, blockchain immutability, or suitability for live government cases.

## Release rule

Do not merge to `main`, deploy to a production environment, or present the system as a fully operational national platform until the release gates in [RELEASE_GATES.md](RELEASE_GATES.md) have documented evidence and the project owner approves the release.

## Product principles

1. No fabricated alerts, fake transaction IDs, simulated evidence, or demo records presented as real.
2. Fail closed when a production dependency or required secret is missing.
3. Every evidence item must have a verifiable digest, provenance, access history, and retention policy.
4. Keep the system simple enough for independent review and audit.
5. Satellite outputs are candidate observations, not legal conclusions.
6. Every material change must have tests, documentation, a reviewable diff, and a recorded decision.
7. Keep secrets, private keys, personal data, and live evidence out of Git history and CI logs.
