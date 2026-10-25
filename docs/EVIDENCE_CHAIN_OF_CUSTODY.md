# Evidence Chain of Custody

**Status:** requirements and workflow specification. The complete chain-of-custody system is not yet claimed as operational.

## Goal

Preserve enough verifiable metadata to answer: what was submitted, by whom, when, through which process, where the bytes are stored, who accessed or transformed them, and whether the current bytes match the originally recorded digest.

## Evidence lifecycle

1. **Submission:** authenticate the submitting principal; authorize creation against a report/case; validate size and allowed content types; assign a server-generated evidence ID. Never trust a client filename as a storage path.
2. **Hashing:** compute SHA-256 from the actual byte stream on the server. Record the digest, byte count, validated media type, submission time and authenticated principal.
3. **Storage:** write to a private bucket using a server-generated object key. Record bucket/object identifier and object generation/version when available. Do not store the only copy on ephemeral application disk.
4. **Verification:** after upload, verify stored object metadata or read back the object in a controlled integration test. On download, check authorization and optionally re-compute the digest before returning bytes.
5. **Access history:** record a security event for upload, download, failed authorization, replacement attempt, deletion, retention change and privileged access. Avoid recording the evidence body or secret-bearing headers.
6. **Processing:** every derived artefact must link to its parent evidence IDs, source object versions, processing code/version, configuration, execution time and output digest.
7. **Review:** record reviewer identity, timestamp, decision, reason and any correction. Never overwrite the original submission when a reviewer annotates or rejects it.
8. **Retention/deletion:** apply an approved retention schedule and legal-hold process. Record who authorized a deletion and the object/version affected, subject to applicable law.
9. **Optional blockchain anchor:** only after real contract/network deployment, submit a canonical digest or batch/Merkle root, record chain ID, contract address, transaction hash, block number, confirmation/finality status and verification result. The on-chain record is supplemental; preserve off-chain evidence and provenance.

## Minimum metadata

- Evidence ID and linked report/case ID.
- Authenticated submitter principal and tenant/agency scope where applicable.
- Server receipt timestamp in UTC.
- Claimed capture time (separate from server receipt time) and its source/uncertainty.
- Original filename as metadata only, sanitized for display.
- Detected media type, byte size, SHA-256 digest.
- Private storage object ID and object version/generation.
- Collection method, device/source and location metadata when lawfully available.
- Source-system or satellite product identifier for remote-sensing assets.
- Parent evidence IDs for derived files.
- Processing software/model version and configuration digest.
- Access/review/retention audit-event references.
- Integrity verification outcome and verification timestamp.

## Integrity and provenance rules

- The server-computed digest is authoritative for the received bytes; client-supplied hashes are advisory and must be recomputed.
- Store timestamps as UTC and distinguish claimed capture time from server receipt time.
- Do not infer that a file is authentic merely because its digest is stable.
- Never silently replace an evidence object. A correction creates a new version and an audit event.
- Fail closed if storage is unavailable or the digest cannot be recorded.
- Keep real evidence out of CI fixtures, screenshots, public issues and model-training datasets unless explicitly authorized and governed.

## Current implementation boundary

The foundation branch has evidence storage integration logic and automated tests using controlled/mock storage. That verifies application logic only. The live bucket, cloud IAM, immutable/versioned retention, complete audit-event ledger, end-to-end restore, and blockchain anchoring require separate implementation/configuration and real-environment verification.
