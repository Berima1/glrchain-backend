# Architecture Decision Log

Decisions are written as short records so future contributors can understand why the system is shaped this way. Supersede a decision by adding a new record; do not silently erase history.

## ADR-001 — Keep official records relational and geospatial

**Status:** Accepted  
**Decision:** Use PostgreSQL/PostGIS as the authoritative record store for reports, evidence metadata, workflow state and future land/resource geometries.  
**Reason:** Relational constraints, transactions, migrations, spatial types and queries make authoritative records easier to validate and audit. Cloud SQL for PostgreSQL supports PostGIS (see [Google Cloud SQL extension docs](https://docs.cloud.google.com/sql/docs/postgres/extensions)).  
**Consequence:** The API must persist and migrate records in PostgreSQL before claiming success.  
**Revisit when:** the sponsoring authority requires an approved alternative or measured operational evidence justifies a change.

## ADR-002 — Firebase Authentication for production identity

**Status:** Accepted for production target; live cloud integration pending  
**Decision:** The client signs in with Firebase Authentication; the backend verifies ID tokens and maps the verified UID to a GLRChain profile. Local username/password auth remains for controlled development/test only.  
**Reason:** Identity-provider controls should not be recreated casually inside a national application. Firebase documents server-side ID-token verification at [Verify ID tokens](https://firebase.google.com/docs/auth/admin/verify-id-tokens).  
**Consequence:** Production startup must reject a non-Firebase provider; public provisioning can create only a normal user. Real Firebase configuration and security tests remain required.  
**Revisit when:** the institutional identity/security policy selects another approved provider.

## ADR-003 — Private object storage for evidence

**Status:** Accepted  
**Decision:** Store raw evidence in a private Cloud Storage bucket; store reference metadata and SHA-256 in PostgreSQL.  
**Reason:** Raw evidence should not depend on ephemeral API-container disks or be exposed by a public object URL.  
**Consequence:** GCS permissions, object retention, orphan cleanup, malware handling and real-cloud tests are release requirements. The digest detects byte changes relative to the recorded digest but does not alone prove the origin or truth of a file.

## ADR-004 — Hash-chained application audit trail

**Status:** Accepted with limitation  
**Decision:** Append audit events in the same database transaction as important mutations, link each event to the previous digest, and expose privileged verification.  
**Reason:** A reviewer needs a verifiable record of report/evidence operations.  
**Consequence:** This is tamper-evident, not immutable. Export to a separately administered logging/retention system and independently verify the exported chain before national production. Admin access and role changes need their own controlled procedures.

## ADR-005 — No operational endpoints for unfinished detectors or anchors

**Status:** Accepted  
**Decision:** Remove fake alert/scoring/transaction routes instead of returning plausible-looking placeholders.  
**Reason:** False positives and false evidence anchoring can cause real harm and destroy trust.  
**Consequence:** Real satellite pipeline and real blockchain anchoring must be built and gated separately; API documentation must label them unavailable until validated.

## ADR-006 — Use explicit release gates and protected PRs

**Status:** Accepted  
**Decision:** Use a dedicated branch, draft PR, automated CI, independent review and explicit cloud release workflow. Do not update or deploy `main` from experimental changes.  
**Reason:** A green CI run is necessary but not sufficient, and cloud resources may contain sensitive information.  
**Consequence:** The current PR remains draft until all checks and reviewers have assessed it.
