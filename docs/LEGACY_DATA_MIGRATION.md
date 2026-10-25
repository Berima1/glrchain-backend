# Legacy Data Migration Plan

**Status:** Plan only. No production database, report export, evidence archive, or encryption key has been copied by this change.

This plan applies only if the existing Render deployment contains records that must be retained. Do not assume data exists or that a database backup is sufficient until the source inventory has been verified.

## Non-negotiable rule

Never migrate the live source database directly as an experiment. Create and protect a backup, restore it to an isolated staging database, rehearse the exact migration/import, verify record counts and decryption, and obtain an owner-approved cutover decision.

## Phase 1 — Discover and preserve the source

1. Identify the real Render database/service and the exact deployed commit.
2. Record schema version, table counts, available evidence files/objects, timestamps, configuration and retention policy without copying secret values into documentation.
3. Take a managed database backup/export and preserve it in an approved restricted location.
4. Preserve the historical SECRET_KEY (or exact LEGACY_REPORT_ENCRYPTION_KEY) in a secret manager. Do not print or send it to the migration log.
5. Identify whether evidence ever lived on ephemeral container storage. A filename/DB row is not proof that the corresponding bytes still exist.
6. Pause writes or plan a short maintenance window for final export/cutover. Record the final source snapshot ID and time.

## Phase 2 — Restore and inspect in staging

1. Restore the source data to an isolated PostgreSQL staging database. Do not expose it publicly.
2. Verify the original schema and which Alembic revision the source reports. If alembic_version is missing or does not reflect the actual schema, reconcile through a reviewed one-time migration plan; never stamp a revision without checking every expected table/column/index.
3. Run the forward migrations to current head on the restored copy.
4. Validate:
   - number of users/reports before and after;
   - all existing report ciphertext is preserved byte-for-byte unless a separately reviewed re-encryption transform is executed;
   - version-1 descriptions decrypt using the correct historical key;
   - legacy locations are marked location_encryption_key_version=0 and remain readable as plaintext to authorised users;
   - old reports whose user_id is null remain unassigned until a verified identity-mapping review;
   - evidence metadata can be reconciled to the actual raw evidence bytes and source hashes;
   - the audit chain starts cleanly at its new baseline, without fabricating historical actors/actions.
5. Any failed decryption, missing evidence object, unexplained count difference or unverifiable source key is a stop condition.

## Phase 3 — Identity mapping

Legacy local accounts have no Firebase UID unless mapped explicitly. Do not link a Firebase identity by username or email alone without an approved identity-proofing procedure. Record which source profile was mapped, evidence/approval for the mapping, actor, timestamp and result.

Reports created before the audit chain was introduced do not acquire genuine historical audit events retroactively. The migration process must emit a clearly labelled baseline/import event describing the source snapshot, record counts and manifest digest, and state the known historical audit gap. Never create invented reporter, reviewer, timestamp or approval events to make the new ledger look complete.

## Phase 4 — Evidence migration

1. Inventory original bytes and establish a per-file SHA-256 manifest before transfer.
2. Upload to the private Cloud Storage bucket with object create preconditions and a controlled import identity.
3. Recalculate hashes after transfer and verify byte count/hash against the manifest.
4. Link the imported objects to database metadata using stable IDs and record the source manifest digest, source object/path, import time, and operator.
5. Keep unlinked or hash-mismatched objects quarantined; do not mark them as valid evidence.
6. Confirm retention/versioning policy before deleting any source copy.

## Phase 5 — Cutover and rollback

1. Approve a final source freeze and create the final export.
2. Replay the rehearsed process against the final snapshot.
3. Verify users/profile mapping, reports, ciphertext decryption, evidence hashes, migration head, audit verification, health checks and backups.
4. Switch the client/API route only after the defined checks and responsible approval.
5. Preserve the original backup and rollback route under restricted access until the agreed retention/rollback window closes.
6. Record cutover time, source snapshot hash, target database/revision, migration job execution, counts, discrepancies, approver and rollback decision.

## Open implementation requirement

A dedicated, idempotent import tool, signed manifest format and baseline audit-event generator still need to be implemented and tested before this plan can be executed at scale. This document does not claim that legacy migration is complete.
