# GLRChain Security Threat Model

**Status:** baseline threat model; not a completed independent security assessment.  
**Review cadence:** at each major release, after material architecture changes, and after any security incident.

## Assets

1. Report text and reporter identity.
2. Evidence files, SHA-256 digests, metadata and provenance.
3. User accounts, password hashes, access tokens and role assignments.
4. Case/incident records and reviewer decisions.
5. Database contents, backups, encryption keys and cloud credentials.
6. Satellite source assets, derived geometries, model outputs and validation datasets.
7. Audit records, deployment artefacts and source-control history.

## Trust boundaries

- Unauthenticated internet client → API.
- Authenticated user → owner-scoped report/evidence operations.
- Privileged administrator → administrative operations.
- API runtime → relational database.
- API runtime → private evidence object storage.
- CI identity → source repository and build pipeline.
- Deployment identity → cloud resources.
- Satellite providers/data sources → ingestion and processing jobs.
- Future anchoring worker → blockchain RPC/network.

Each boundary must have explicit authentication, authorization, input validation, logging and failure handling. A successful health check does not validate every boundary.

## Threats and controls

| Threat | Required controls | Verification evidence |
|---|---|---|
| Account takeover | Password hashing, token expiry, TLS, rate limiting, secure recovery, monitoring | Auth tests, abuse tests, security review |
| Privilege escalation | Server-side role assignment, least privilege, protected admin provisioning | Negative test for client-supplied role; admin-access tests |
| Cross-user report/evidence access | Owner-scoped queries and object authorization on every request | Tests with two distinct accounts |
| SQL injection or malformed input | ORM/parameterized queries, schema validation, safe errors | Automated tests and security review |
| Evidence replacement or corruption | Immutable/versioned object storage where configured, SHA-256 verification, audit history | Real bucket integration test and integrity test |
| Key loss or exposure | Secret manager, access separation, backup/recovery and rotation procedure | Recovery drill and secret scanning |
| Public object exposure | Public access prevention, least-privilege IAM, API-mediated downloads | Cloud IAM review and anonymous access test |
| Fake or fabricated detections | Provenance, source IDs, model/version record, human review, no fake-success responses | Data provenance tests and analyst validation |
| False-positive galamsey alerts | Multi-source corroboration, uncertainty display, geographic/temporal validation, human review | Independent geospatial evaluation |
| Supply-chain compromise | Pinned/reviewed dependencies, vulnerability scans, controlled builds and image provenance | CI scan reports and release records |
| Unauthorized deployment | Protected branch, separate deployment identity, approval gates | Repository/environment settings review |
| Insider misuse | Least privilege, audit events, dual review for sensitive operations, alerting | Access review and audit-log review |
| Cloud outage/data loss | Managed backups, restore tests, monitoring, documented recovery objectives | Successful restore drill |
| Blockchain RPC/contract abuse (future) | Reviewed contract, signer isolation, transaction validation, idempotency and independent verification | Testnet/mainnet evidence appropriate to deployment |

## Security assumptions and limitations

- HTTPS and cloud IAM must be configured correctly outside the application.
- A password hash does not replace MFA or rate limiting.
- A hash is an integrity check only when the expected digest is protected.
- Encryption at rest does not protect plaintext while the application processes it.
- A blockchain anchor does not prove that the original evidence is truthful or legally obtained.
- The model is incomplete until the deployed architecture, actual cloud permissions, data classification and operational actors are reviewed.

## Minimum go-live security gate

Do not accept real sensitive reports until a reviewer has signed off authentication, authorization, secret/key management, storage privacy, audit logging, backups/restore, monitoring, incident response and privacy/legal requirements.
