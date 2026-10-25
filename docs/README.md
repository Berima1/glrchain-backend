# GLRChain Documentation Index

This directory is the auditable project record. Each document must distinguish implemented code, automated test evidence, external configuration, and work not yet operational.

## Project and architecture

- [Project status and limitations](PROJECT_STATUS_AND_LIMITATIONS.md)
- [Architecture decision log](DECISION_LOG.md)
- [Data dictionary](DATA_DICTIONARY.md)

## Security and evidence

- [Threat model](THREAT_MODEL.md)
- [Evidence chain of custody](EVIDENCE_CHAIN_OF_CUSTODY.md)
- [Security policy](../SECURITY.md)

## Deployment and operations

- [Google Cloud deployment and evidence storage](GOOGLE_CLOUD_DEPLOYMENT.md)
- [Operations runbook](OPERATIONS_RUNBOOK.md)
- [Deployment guide](../DEPLOY.md)

## Geospatial intelligence

- [Satellite monitoring and detection design](SATELLITE_DETECTION_DESIGN.md)

## Quality and release

- [Testing and release procedure](TESTING_AND_RELEASE.md)
- [Release gates](RELEASE_GATES.md)
- [Engineering work log](WORK_LOG.md)

## Change-control rule

Every significant change must update the relevant documentation and work log in the same pull request. Do not record a capability as operational without a reproducible test or external verification record tied to a specific commit and environment.
