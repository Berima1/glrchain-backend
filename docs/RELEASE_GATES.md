# GLRChain Release Gates

**Current disposition:** do not approve national production use based on the foundation PR alone.

Every gate must have an evidence link, the commit/environment tested, reviewer, date, result and follow-up issue if incomplete.

## Gate 1 — Source and build integrity

- [ ] Protected main branch and reviewed pull request
- [ ] Latest required CI checks pass for the exact release commit
- [ ] Container build succeeds and image digest is recorded
- [ ] Dependency and container vulnerability scan reviewed
- [ ] No credentials, private keys, personal data or real evidence in repository history
- [ ] Reproducible build/deployment inputs recorded

## Gate 2 — Identity and access control

- [ ] Authentication and token lifecycle reviewed
- [ ] Role assignment is server-controlled
- [ ] Negative tests cover anonymous access, privilege escalation and cross-user access
- [ ] Admin account provisioning, recovery, MFA and offboarding documented
- [ ] Rate limits, abuse controls and safe error responses tested
- [ ] Security-relevant actions are durably audited

## Gate 3 — Data and cryptography

- [ ] Production managed database configured with TLS and least privilege
- [ ] Migrations reviewed and tested against a clean database
- [ ] Backups enabled and restore drill passed
- [ ] Persistent encryption/signing keys stored in secret management
- [ ] Key recovery and rotation tested
- [ ] Retention, legal hold, export and deletion policies approved
- [ ] Logs exclude secrets, passwords, tokens and sensitive report content

## Gate 4 — Evidence storage and chain of custody

- [ ] Private object storage and least-privilege IAM verified
- [ ] Real upload/download test passed using synthetic evidence
- [ ] SHA-256 digest verified against stored bytes
- [ ] Owner-scoped access and denied cross-user access tested against real storage
- [ ] Object versioning/retention and audit logs reviewed
- [ ] Evidence provenance and reviewer history recorded
- [ ] Restore/recovery procedure tested

## Gate 5 — Geospatial monitoring (required before enabling alerts)

- [ ] Source data permissions, product IDs and provenance recorded
- [ ] Ingestion, retries, deduplication and quality checks implemented
- [ ] CRS, co-registration, geometry and area calculations validated
- [ ] Reference dataset and independent geographic/temporal evaluation completed
- [ ] Precision, recall, false-positive/negative rates and calibration documented
- [ ] Seasonal and non-mining change causes assessed
- [ ] Analyst review, uncertainty labels and correction workflow tested
- [ ] No unreviewed candidate is represented as a legal finding

## Gate 6 — Blockchain anchoring (required before claiming anchoring)

- [ ] Target network, governance and threat model approved
- [ ] Contract reviewed and deployed to the intended network
- [ ] Chain ID, contract address, deployment transaction and bytecode verified
- [ ] Signer keys isolated and access-controlled
- [ ] Retry/idempotency, confirmation/finality and failure recovery tested
- [ ] Evidence digest/manifest is canonical and independently verifiable
- [ ] Real transaction is independently checked from a separate client
- [ ] No mock transaction or fabricated success response remains in operational paths

## Gate 7 — Operations and governance

- [ ] Named service owner and incident lead
- [ ] Monitoring, alerting, log retention and escalation tested
- [ ] Capacity/load and availability tests completed
- [ ] Incident response, disclosure, rollback and disaster recovery rehearsed
- [ ] Privacy, legal basis, data sharing and retention reviewed by appropriate Ghanaian stakeholders
- [ ] User roles, case review procedures and audit access approved
- [ ] Training and operational handover completed
- [ ] Project owner explicitly approves the release

## Current release decision

Until these gates are completed and evidenced, classify the system as **foundation / staging candidate**. A passing API test suite or HTTP 200 response is not sufficient for production approval.
