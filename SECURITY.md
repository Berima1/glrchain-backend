# GLRChain Security Policy

## Scope and current status

GLRChain is intended to support secure land and natural-resource reporting and evidence review. The current repository branch is a foundation under development, not a certified or fully operational national platform. Satellite detection, production blockchain anchoring, and live government operations must not be claimed until independently implemented and verified.

## Reporting a vulnerability

Do not publish exploit details, credentials, private keys, personal data, or real case evidence in public issues or pull requests. Contact the project owner through a private, verified channel and include:
- affected commit or deployment version;
- affected endpoint/component;
- reproducible steps using synthetic data;
- impact and any suggested mitigation.

Do not test against real government systems, real reports, or infrastructure without explicit authorization.

## Secrets and cryptographic keys

- Never commit passwords, tokens, private keys, service-account JSON, database URLs containing credentials, or live evidence.
- Use a secret manager and least-privilege runtime identity.
- `SECRET_KEY` must be high entropy and persistent for the deployment; rotating it can invalidate existing tokens.
- `REPORT_ENCRYPTION_KEY` must be a valid persistent Fernet key. Key loss can make encrypted report descriptions unrecoverable. Maintain an access-controlled recovery plan and test rotation before attempting it.
- Never print secrets in logs, CI output, screenshots, issue reports, or documentation.
- If a secret is exposed, revoke/rotate it, investigate access, preserve relevant logs, and document the incident.

## Evidence handling

- Keep evidence objects private; do not enable public bucket access.
- Authorize every evidence download against the report/evidence owner or a documented privileged role.
- Store SHA-256 digests and relevant provenance metadata; verify content against the recorded digest where applicable.
- A hash alone does not prove collection time, collector identity, or truthfulness of a claim.
- Do not put evidence bytes or sensitive report text in logs.
- Define retention, legal hold, deletion, access audit and backup policies before accepting real case evidence.
- Use synthetic evidence for development and CI.

## API and deployment controls

- Require authentication for sensitive endpoints and enforce server-side authorization.
- Do not trust role values supplied by public clients.
- Use HTTPS, strict CORS, request size limits, rate limiting, secure error handling and dependency vulnerability scanning before production.
- Production must fail closed when its database, persistent keys, or private evidence storage are missing.
- Keep production deployment credentials out of pull-request builds. Require protected branches and explicit release approval.
- Apply database migrations as a reviewed release operation, not during container image build.

## Detection and blockchain claims

- Satellite change alerts are candidate observations, not legal conclusions; require human review and preserve uncertainty/provenance.
- Do not use fabricated alert data, demo transaction IDs, or simulated anchoring in operational flows.
- A blockchain event does not by itself establish the authenticity or legality of evidence.

## Security review checklist

- [ ] Authentication and authorization negative tests
- [ ] Rate limiting and abuse controls
- [ ] Dependency and container vulnerability scan
- [ ] Secret exposure/history review
- [ ] Database least privilege, TLS, backups and restore test
- [ ] Private object storage IAM and access audit
- [ ] Key recovery and rotation procedure
- [ ] Audit logging and monitoring
- [ ] Incident response and disclosure contact confirmed
- [ ] Independent review before production release
