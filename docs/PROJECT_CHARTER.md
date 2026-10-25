# GLRChain Project Charter

**Project:** Ghana Land & Natural Resources Chain (GLRChain)  
**Sponsor/audience:** Intended to support Ghana's Ministry of Lands and Natural Resources (MLNR) and authorised land/resource agencies  
**Status:** Engineering foundation; not approved for national production use  
**Repository:** `Berima1/glrchain-backend`

## Mission

Build a small, auditable digital system that helps authorised people record land and natural-resource reports, preserve evidence with a verifiable chain of custody, and later review geospatial changes that may warrant inspection for illegal mining (galamsey) or other land/resource violations.

GLRChain should make the path from observation to review to decision easier to audit. The system is decision support; it does not replace statutory land registration, licensing, environmental assessment, police investigation, judicial process, or human judgement.

## Initial outcomes

1. A report is tied to an authenticated submitter and persisted in the authoritative database.
2. Sensitive report descriptions are encrypted before database storage, with explicit key versions and a controlled key-rotation plan.
3. Evidence is stored privately outside the API container; metadata includes a SHA-256 digest and the API checks the digest on retrieval.
4. Important application actions are written to a transactional, hash-chained audit log that authorised auditors can verify.
5. Release evidence includes code review, automated tests, migration results, deployment configuration, and open limitations.
6. A future satellite pipeline produces geospatial *candidates* with traceable input imagery, processing versions, uncertainty, and human-review outcomes.

## Operating principles

- **Truth over appearance:** no fake detections, fake transaction IDs, synthetic evidence, invented statistics, or silent demo fallback in production paths.
- **Human review:** satellite signals identify possible change, not guilt or legal status.
- **Least privilege:** citizens, field officers, reviewers, validators, administrators, and machine workers receive different permissions.
- **Auditable by design:** record who did what, when, to which record, and what hash/processing version was involved; avoid logging report descriptions or unnecessary personal details.
- **Recoverable:** documented backups, restoration tests, migration rollback/forward-fix plan, and disaster-recovery ownership.
- **Simple and explainable:** explain system behaviour in plain language and keep decisions traceable.
- **Mobile-first operation:** public and field workflows must remain practical on ordinary Android phones and unreliable connections.

## Explicit non-goals for the first release

- Do not claim to register, transfer, adjudicate, or legally certify land title.
- Do not make automated accusations or enforcement decisions.
- Do not claim an AI model exists until its source, data, training/evaluation methodology, and measured performance are delivered.
- Do not claim blockchain anchoring until a real governed network is deployed and transaction receipts are verified.
- Do not make Firestore a second conflicting source of truth for official land/resource records.
- Do not put private evidence, raw location details, passwords, tokens, or secret keys in public GitHub.

## Intended roles

| Role | Minimum scope |
|---|---|
| Reporter | Submit reports and access own records/evidence |
| Field officer | Access assigned reports and submit field observations under approved policy |
| Validator/reviewer | Review assigned reports and evidence; record decisions and rationale |
| Administrator | Manage approved accounts, workflow configuration, and access under audited procedures |
| Auditor | Read audit events and run integrity verification |
| Worker/service identity | Perform only its specific database, storage, or processing job |

The current code only implements a subset of these permissions. Production role assignment and assignment-based scope are release blockers until implemented, tested, and documented.

## Success criteria

Success is not a polished landing page or an HTTP 200 response. Success means records persist to the intended database; authorisation is enforced; evidence can be recovered and its integrity verified; reviewers can reproduce a detection result from recorded inputs; operational failures are visible; and an independent reviewer can verify the release evidence.

## Governance

A national deployment requires an authorised Ghanaian institution to approve data ownership, legal basis, access policy, retention, disclosure, audit review, incident response, and decision rights. GLRChain code alone cannot establish those institutional approvals.
