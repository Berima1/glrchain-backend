# GLRChain Architecture

**Status:** Target architecture plus current implementation notes  
**Authoritative repository:** `Berima1/glrchain-backend`

## Architectural choice

Use each service for a clear purpose:

- **Cloud Run service:** stateless HTTPS API. It must not depend on container-local files for durable data.
- **Cloud SQL for PostgreSQL with PostGIS:** authoritative relational records, report workflow, users/roles, evidence metadata, audit chain, and future parcel/incident geometries. Cloud SQL documents support for PostGIS across PostgreSQL major versions: [supported PostgreSQL extensions](https://docs.cloud.google.com/sql/docs/postgres/extensions).
- **Private Cloud Storage bucket:** raw evidence objects, with public access prevention and bucket-level IAM. The database stores object names, file size, content type, uploader, report association, and digest—not public object URLs.
- **Firebase Authentication:** client sign-in and identity. The API verifies Firebase ID tokens server-side and maps a verified Firebase UID to a GLRChain profile. See [Firebase ID-token verification](https://firebase.google.com/docs/auth/admin/verify-id-tokens).
- **Secret Manager:** persistent report encryption key, database connection strings, JWT compatibility secret where needed, and other credentials. Use least privilege and pinned secret versions for deployment; see [Secret Manager best practices](https://docs.cloud.google.com/secret-manager/docs/best-practices).
- **Cloud Logging/Monitoring:** service logs, deployment events, error rates, health, and alerts. Export security/audit records to a separately controlled sink as part of the production design.
- **Cloud Run Jobs (future geospatial worker):** scheduled or queued satellite processing, with persistent checkpoints and idempotent job IDs. See [Cloud Run Jobs retry/checkpoint guidance](https://docs.cloud.google.com/run/docs/jobs-retries).
- **Firestore (optional, not authoritative):** may support realtime user-facing status or low-risk operational notifications after a consistency policy is defined. Do not duplicate official report, evidence, parcel, or audit records as independent writable records.

## Request and evidence flow

1. A client signs in through Firebase Authentication and sends a Firebase ID token over HTTPS.
2. The API verifies the token (including revocation where supported), resolves the Firebase UID to a GLRChain profile, then checks the profile's current database role.
3. A new report's description and human-readable location are encrypted with the configured report key before insertion. The report row, owner/status fields, and audit event are committed in one database transaction.
4. Evidence is checked for allowed file signature and size, then uploaded to private Cloud Storage with a SHA-256 metadata field and a create-only generation precondition.
5. Evidence metadata and its audit event are committed to PostgreSQL. If this transaction fails, the API attempts to delete the uploaded object; production operations must also monitor and clean up any orphaned object if compensation itself fails.
6. On evidence download, the API authorises access, retrieves the private object, recomputes SHA-256, rejects a digest mismatch, logs the access event, and returns it as an attachment with `no-store` and `nosniff` headers.

The database transaction and Cloud Storage upload are not one distributed atomic transaction. That limitation is explicit and requires orphan monitoring, retry-safe operations, and tested recovery procedures.

## Audit trail

The application creates ordered audit events in the same transaction as relevant record mutations. Each event includes a canonical payload, the previous event hash, and its own SHA-256 hash. A singleton audit-head row is locked during append on PostgreSQL so normal concurrent API writes serialise the chain.

The chain is **tamper-evident, not immutable**. A sufficiently privileged database operator could rewrite all events and the head. Independent assurance therefore requires exporting audit events to a separately administered logging/retention system and regularly verifying them there as well. The application endpoint `GET /admin/audit/verify` only verifies the chain currently present in the database.

## Geospatial processing flow (not yet implemented)

1. Record the satellite source/product ID, acquisition time, scene footprint, processing level, projection, source checksum, cloud/quality flags, and licence/usage metadata.
2. Harmonise and align time-separated observations; reject misaligned or low-quality inputs.
3. Calculate documented optical/SAR change features. The input/outputs and algorithm version must be deterministic and reproducible.
4. Produce georeferenced polygons in a documented CRS, store them in PostGIS, and attach confidence/quality reasons rather than only a single opaque score.
5. Compare candidates with available licences/protected-area/waterway layers only where those source datasets are authorised, dated, and provenance-tracked.
6. Route candidates to an authorised human review queue. Record reviewer, outcome, reason, timestamps, evidence, and any escalation separately from model output.
7. Validate against a Ghana-relevant labelled dataset and publish false-positive/false-negative rates, coverage gaps, and model version before operational use.

Current repository stubs for NBR/SAR/U-Net and fake score/transaction endpoints were removed from active code paths. There is no live satellite detection or blockchain anchoring endpoint in this foundation release.

## Deployment topology

Use separate service identities for (a) API runtime, (b) database migration job, (c) geospatial processing job, and (d) GitHub Actions deployment. Limit database migration privileges to the migration identity; grant the runtime identity only its required DML access. Grant Cloud Storage access at the evidence bucket level, not project-wide where avoidable.

Keep Cloud Run, Cloud SQL, and the bucket in locations approved by the project's data-protection and operational requirements. Verify service availability, data-residency obligations, and cost before selecting a production region.


## Historical data boundary

The audit chain starts when the audit schema and application logging are introduced. Legacy report rows do not acquire authentic historical audit events retroactively. If an earlier deployment is migrated, record a clearly labelled baseline/import event and manifest digest; keep the historical gap explicit. The detailed procedure is in [Legacy Data Migration](LEGACY_DATA_MIGRATION.md).
