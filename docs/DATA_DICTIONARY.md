# GLRChain Data Dictionary

**Status:** conceptual dictionary for the foundation. Confirm exact column names/types against the SQLAlchemy models and Alembic migrations for the release commit before treating this as a schema contract.

## User / principal

Represents an account that can authenticate to the API.

- **ID:** stable internal identifier.
- **Username or login identifier:** unique account identifier; avoid treating it as a verified legal identity.
- **Password hash:** one-way password verifier; plaintext passwords must never be stored.
- **Role:** server-controlled authorization role. Public registration must not permit self-assignment of administrative roles.
- **Created timestamp:** server-side account creation time.
- **Status fields (if implemented):** account enabled/disabled and security lifecycle metadata.

## Report / case submission

Represents a user-submitted report. It is not automatically a legally verified finding.

- **Report ID:** server-generated stable identifier.
- **Reporter/user ID:** authenticated owner reference.
- **Location:** user-provided location description or coordinates; coordinate reference system must be explicit when coordinates are stored.
- **Description:** sensitive report text; the foundation encrypts this field before persistence.
- **Created/updated timestamps:** server-controlled UTC timestamps.
- **Status:** workflow state, if implemented; transitions must be authorized and audited.
- **Evidence references:** links to evidence metadata, not embedded raw files.
- **Review outcome:** should include reviewer, timestamp, decision and rationale when review workflow is implemented.

## Evidence metadata

Represents a submitted file or derived artefact. The object bytes live in private object storage.

- **Evidence ID:** server-generated identifier.
- **Report ID:** parent report/case reference.
- **Owner/submitting principal:** authenticated account reference.
- **Object identifier/version:** private storage reference; never a public URL.
- **SHA-256 digest:** server-computed digest of received bytes.
- **Media type and byte size:** validated server-side.
- **Original filename:** metadata only; must not determine a storage path.
- **Received timestamp:** server-generated UTC time.
- **Capture timestamp/source:** separate from receipt time and explicitly marked as claimed or verified.
- **Provenance/processing metadata:** source references, parent evidence IDs, pipeline/model version and output digest where applicable.

## Audit event (required design)

A durable append-oriented record for security-relevant actions, including login/security events, report/evidence create/read/update/delete, authorization failures, privileged actions, migration/deployment changes, review decisions and key operational events. Each event should record actor, action, target ID, server timestamp, outcome, correlation ID and minimal safe context. Do not store secrets, passwords, tokens, or evidence body content in audit events.

## Satellite candidate (future capability)

A candidate observation, not a legal conclusion. Expected fields include AOI/geometry and CRS, acquisition timestamps, source product IDs, processing/model version, feature/score explanation, uncertainty, evidence references, reviewer decision and rationale.

## Anchoring record (future capability)

A record of a real, independently verifiable transaction only. Expected fields include chain ID, contract address, canonical digest or batch root, transaction hash, block number, confirmation/finality status and verification timestamp. Never store fake transaction IDs or claim success before the transaction is confirmed and independently checked.
