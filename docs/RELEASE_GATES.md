# GLRChain Release Gates

No release may be called production-ready until all gates that apply to that release are passed and evidenced. A passing API CI job is necessary but not sufficient.

## Gate 0 — Source and review integrity

- [ ] Branch and exact commit SHA are recorded.
- [ ] No placeholder, demo, fake transaction, fake detection or synthetic production data path is active.
- [ ] Draft PR diff is reviewed by an independent engineer (Codex/Claude review plus human owner review).
- [ ] Secret scanning, dependency review, SBOM and licence review are complete.
- [ ] Required review/branch protection is enabled for protected branches.
- [ ] Rollback/recovery method is documented.

## Gate 1 — API and data integrity

- [ ] CI compiles the package, runs tests against PostgreSQL/PostGIS, applies migrations from an empty database and from a representative upgrade fixture, and builds the container.
- [ ] Tests cover authentication, authorisation, account provisioning, data persistence, encryption/decryption, evidence type/size rejection, evidence digest checks, audit chain verification/tamper detection, and failure handling.
- [ ] Race/concurrency tests cover audit append serialization, duplicate profile provisioning, idempotency and retries.
- [ ] Legacy report encryption and ownership mapping are tested against a backed-up, representative copy of existing records.
- [ ] All roles are tested for permitted and denied operations.
- [ ] No admin account can be created by public registration or self-promotion.
- [ ] External failure never returns a false success receipt.

## Gate 2 — Google Cloud and identity

- [ ] Separate project/environment approved for GLRChain; budget/quota alerts configured.
- [ ] Cloud Run API and migration job use separate identities.
- [ ] Cloud SQL connection path, PostGIS extension, backups and point-in-time recovery are configured and tested.
- [ ] Runtime database user is least-privilege; migration user is separately controlled.
- [ ] Private GCS bucket has public access prevention/uniform bucket-level access and approved retention/versioning settings.
- [ ] Bucket access is scoped to the runtime service identity; no service-account JSON key is committed or embedded in images.
- [ ] Secret Manager references use approved, pinned versions with least-privilege access.
- [ ] Firebase Authentication is configured, tokens are verified server-side, sign-in providers are approved, and privileged identities have stronger controls.
- [ ] Production configuration fails at startup when essential settings are missing or invalid.
- [ ] Monitoring, alerting, structured logs, service health and budget alerts are live.
- [ ] HTTPS, abuse/rate controls, CORS/app-client policy and denial of unauthenticated sensitive routes are reviewed.

## Gate 3 — Operations and privacy

- [ ] Data owner, legal basis, access policies, privacy notice, retention schedule and disclosure rules are approved.
- [ ] Backup restore is demonstrated with a timed recovery record.
- [ ] Incident response, account offboarding, key rotation, data correction, legal hold and deletion procedures are exercised.
- [ ] Evidence chain-of-custody export is reproducible; files can be retrieved and hashes re-verified.
- [ ] Audit events are exported to an independently controlled destination and verified.
- [ ] Load, availability and failure-recovery tests meet an approved service-level objective.
- [ ] Penetration test and threat-model review findings are resolved or formally accepted by the responsible authority.

## Gate 4 — Satellite intelligence (before any detection claims)

- [ ] Live data acquisition uses authorised source products and recorded product IDs/checksums.
- [ ] Geospatial alignment, CRS, quality/cloud/water/sensor checks and edge conditions are tested.
- [ ] Algorithm/model, parameters, processing environment and version are pinned.
- [ ] A Ghana-relevant labelled dataset is separated into development and evaluation sets without leakage.
- [ ] Precision/recall, false-positive/false-negative rates, confidence calibration, regional/seasonal limitations and review workload are reported.
- [ ] Human review and correction flows are implemented; model output is never automatically treated as proof of a criminal offence.
- [ ] Reprocessing a recorded input produces a reproducible output digest or explains permitted nondeterminism.

## Gate 5 — Blockchain anchoring (before any anchor claims)

- [ ] Network ownership, governance, validator policy, key custody and recovery arrangements are approved.
- [ ] No private key is committed or held in application source; use a managed signing arrangement.
- [ ] Transaction input, chain ID, contract address/code, receipt status, block number, transaction hash and finality rule are verified.
- [ ] Failure/retry/idempotency and duplicate-anchoring tests pass.
- [ ] Only a hash/approved metadata is anchored; private report content is not published on-chain.
- [ ] An independent verifier can recalculate the digest and confirm the real chain receipt.

## Release decision record

For each release, record: reviewer names/roles, commit SHA, CI run URL, migration result, staging environment, security findings, unresolved risks, approval authority, release timestamp, deployment revision, and rollback target.
