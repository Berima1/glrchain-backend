# GLRChain Data Dictionary

This describes the current database models and the initial target for the geospatial extension. Column details must be kept in sync with `app/models.py` and Alembic migrations.

## Current tables

### `users`

| Field | Purpose | Notes |
|---|---|---|
| `id` | Internal profile ID | Primary key |
| `username` | Unique GLRChain display/login name | Do not treat as legal identity proof |
| `hashed_password` | Local-mode password hash or Firebase-managed marker | Never return in API responses; Firebase mode disables local password login |
| `firebase_uid` | Firebase Authentication UID | Nullable for legacy/local accounts; unique when present |
| `role` | Authorisation role | Public provision/register paths must not set privileged roles |
| `created_at` | Creation timestamp | Database-generated |

**Sensitivity:** account/identity metadata. Role changes require a controlled, separately audited administrative procedure. The current first-admin bootstrap command is intended only for initial controlled setup; routine role administration still requires a governed process.

### `reports`

| Field | Purpose | Notes |
|---|---|---|
| `id` | Internal report ID | Primary key |
| `reporter` | Submitter's profile name at submission | Not proof of legal identity |
| `location` | Encrypted location ciphertext for new reports; legacy rows remain plaintext until safely migrated | Sensitive where it could reveal a person or source; new values use Fernet key version 2 |
| `location_encryption_key_version` | Selects location encoding/key | Version 0 means legacy plaintext; version 2 means encrypted using `REPORT_ENCRYPTION_KEY` |
| `description` | Encrypted report text | Fernet ciphertext; API decrypts only after access control |
| `encryption_key_version` | Selects the key used for ciphertext | Version 1 is legacy; new reports use version 2 |
| `user_id` | Owning profile | Legacy rows may be null and need a documented data-migration decision |
| `status` | Workflow state | Current initial state is `submitted`; formal transition rules are still needed |
| `created_at` | Creation timestamp | Database-generated |

### `evidence_records`

| Field | Purpose | Notes |
|---|---|---|
| `id` | UUID for evidence metadata | Not a public storage URL |
| `report_id` | Associated report | Foreign key |
| `object_name` | Private Cloud Storage object name | Never make the bucket public |
| `sha256` | Digest of the stored bytes | Recomputed on download; digest match does not prove source authenticity |
| `size_bytes` | Stored object size | API limit is currently 20 MiB per upload |
| `content_type` | File type inferred from signature | Accepted signatures currently JPEG, PNG, PDF, and MP4 |
| `original_filename` | Sanitised display filename | Not used as object path |
| `uploaded_by` | Uploader profile ID | Foreign key |
| `created_at` | Creation timestamp | Database-generated |

### `audit_heads` and `audit_events`

- `audit_heads`: one row (`id=1`) holds the last event hash. Appends lock this row on PostgreSQL.
- `audit_events`: sequential ID, unique event UUID, actor (nullable for future system events), action, object type/ID, canonicalised details JSON, timestamp, previous hash, and event hash.

Audit details must not contain passwords, tokens, secret keys, raw report descriptions, or unnecessary personal information. The chain is designed to make unauthorised modification detectable, not to withstand a database superuser who rewrites all events and the head.

## Future geospatial tables (not yet implemented)

Do not infer that these tables exist. Proposed entities are:

- **Parcel/land unit:** source authority, source reference, geometry and CRS, version/effective date, public/private classification, provenance, and verification status.
- **Resource licence/permit:** issuing authority, permit identifier, holder reference, geometry or authorised area, commodity/activity, start/end dates, conditions, verification status, source document digest.
- **Observation/acquisition:** provider, product ID, acquisition time, footprint, projection, processing level, cloud/quality metadata, input checksum.
- **Change candidate:** geometry, baseline/target acquisition IDs, algorithm/model version, features and quality flags, measured score with documented interpretation, output digest, lifecycle status.
- **Review decision:** reviewer identity, decision, reasons, timestamps, evidence links, escalation disposition and any corrections.
- **Audit export receipt:** destination, export range, digest/signature, verification result and export timestamp.

Each future entity needs a retention class, access matrix, validation rules, and migration before being implemented.
