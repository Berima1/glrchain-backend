# GLRChain Architecture Decision Log

This is a living decision record. New material architecture decisions should be added with date, context, options, decision, consequences and review owner.

## ADR-001 — Keep changes on a review branch

**Date:** 2026-10-25  
**Status:** Adopted

**Context:** GLRChain is a national-project candidate and must be reviewable. Changes made directly to the default branch would make rollback and independent review harder.

**Decision:** Use `foundation/production-hardening-2026-10` and a pull request for the initial hardening pass. Do not merge or deploy automatically from this working branch.

**Consequences:** The project owner can review the diff and CI evidence before approving a merge. Production deployment must be a separate, explicitly approved action.

## ADR-002 — Fail closed for production dependencies

**Date:** 2026-10-25  
**Status:** Adopted

**Context:** Silent fallback to a local SQLite file, generated encryption key, mock storage, or fabricated alert can make a cloud service appear healthy while losing persistence or misrepresenting evidence.

**Decision:** Production must require explicit database and persistent secret configuration. Missing private evidence storage must prevent evidence operations instead of writing files to ephemeral local disk. Non-operational satellite and blockchain features must not return fake success.

**Consequences:** Some routes will return an error or remain unavailable until real dependencies are provisioned. This is intentional and safer than simulated success.

## ADR-003 — Relational database remains the current system of record

**Date:** 2026-10-25  
**Status:** Adopted provisionally

**Context:** The existing API foundation uses SQLAlchemy models and Alembic migrations. The project owner has access to Google Cloud and mentioned Firebase/Firestore as a possible service.

**Decision:** Keep the current relational model and migration path for the foundation. Do not silently replace it with Firestore. Evaluate Firestore separately only if a documented requirement justifies it.

**Consequences:** Managed PostgreSQL is the expected database for staging/production until a reviewed decision changes it. Google Cloud Storage is for evidence objects, not the relational case metadata.

## ADR-004 — Satellite detections are decision support, not legal findings

**Date:** 2026-10-25  
**Status:** Adopted

**Context:** Satellite change can be caused by agriculture, river movement, logging, fire, construction, clouds, shadows or other non-mining activity. A false positive can harm communities and undermine trust.

**Decision:** The pipeline must output candidate observations with provenance and uncertainty. Authorized human review is required before an alert is treated as a case finding.

**Consequences:** Model validation, reviewer rationale and audit events are mandatory for operational detection.

## ADR-005 — Evidence integrity requires more than a hash or blockchain event

**Date:** 2026-10-25  
**Status:** Adopted

**Context:** A SHA-256 digest can detect byte changes when compared with a trusted recorded digest, but does not prove who collected a file, when it was collected, or whether the original observation was truthful. A blockchain event alone does not establish those facts.

**Decision:** Build a chain of custody containing identity, timestamps, provenance, hash, object version, access history, processing versions and reviewer actions. Blockchain anchoring is a later independent layer, not a substitute for secure storage and audit controls.

**Consequences:** Anchoring remains non-operational until the contract/network and verification workflow are deployed and independently tested.
