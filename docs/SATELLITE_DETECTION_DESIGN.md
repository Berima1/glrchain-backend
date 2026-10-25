# Satellite Monitoring and Potential Illegal-Mining Detection Design

**Status:** target design and implementation plan. This document does not claim that an operational detection model or ingestion pipeline currently exists.

## Objective

Identify geospatial areas that may have experienced land-surface disturbance consistent with mining or other land-use change, generate reviewable candidate alerts, and preserve the source imagery and processing provenance. GLRChain must not automatically label an area as illegal mining solely from a model score or image difference.

## Proposed processing stages

1. **Define area of interest (AOI):** versioned administrative boundaries and user-authorized monitoring polygons, with CRS and provenance recorded.
2. **Acquire imagery:** select authoritative satellite sources and record provider, product ID, sensing time, processing level, bands/polarizations, cloud cover or quality flags, licenses/terms, and source checksums where available.
3. **Validate inputs:** confirm timestamps, CRS, resolution, band identities, nodata handling, scene coverage and data completeness. Reject malformed or incompatible scenes.
4. **Preprocess:** use documented atmospheric/cloud masking for optical imagery; apply appropriate calibration, terrain correction and speckle handling for SAR where required. Keep the original source assets immutable.
5. **Align scenes:** co-register before pixel-wise comparison; record the alignment method and error estimate.
6. **Compute candidate change features:** use validated optical indices (for example, NBR/NDVI where scientifically appropriate), SAR backscatter change, spectral change and terrain/context features. Do not assume a fixed band number across providers or products.
7. **Generate spatial candidates:** convert connected change regions to geometries in a known CRS, transform to the agreed geographic CRS, validate geometry, calculate area in an appropriate projected CRS, and reject artifacts below documented thresholds.
8. **Corroborate:** compare multi-date imagery, nearby historical baselines, water/seasonality context and independent sources. A single change signal is not sufficient to infer mining or illegality.
9. **Score and rank:** only use a calibrated model after training data, validation split, metrics, calibration, bias checks and model versioning are documented. A hand-written heuristic must be labelled a heuristic, not AI.
10. **Human review:** authorized reviewers inspect imagery, geometry, uncertainty, dates and provenance; record accept/reject/defer decisions and rationale.
11. **Create case/evidence package:** preserve source references, transformation history, code/model version, output geometry, score explanation, reviewer actions, timestamps and file hashes.
12. **Publish an alert:** expose only a reviewed, permission-scoped candidate with a clear uncertainty label. Never invent coordinates, scores, source imagery, or detection results.

## Required alert fields

- Stable alert/case identifier.
- AOI and geometry in a declared CRS.
- Acquisition and comparison timestamps.
- Satellite provider/product IDs and source references.
- Processing pipeline version and configuration digest.
- Model name/version and validation record, or explicit "rule-based" designation.
- Change features and score explanation.
- Estimated area and method used.
- Quality flags, uncertainty and known limitations.
- Evidence object IDs and SHA-256 hashes.
- Reviewer, review timestamp, decision and rationale.
- Full audit-event references.

## Validation plan

Before public or government operational use:

- Build a geographically and temporally representative reference dataset with documented permissions.
- Include positive and negative examples and difficult cases (seasonal agriculture, river movement, cloud/shadow, fire, logging, road construction and natural erosion).
- Split training/validation/test data by geography and time to reduce leakage.
- Report precision, recall, false-positive rate, false-negative rate, calibration and performance by region/season/land-cover type.
- Conduct blind review by qualified geospatial analysts.
- Test CRS transformations, polygon validity, area calculations, missing bands, misaligned scenes and duplicate ingestion.
- Establish thresholds based on operational review capacity and documented risk tolerance.
- Preserve model cards, dataset documentation, reproducible configurations and change history.

## Engineering requirements

- Idempotent ingestion: repeated delivery of the same source product must not create duplicate alerts.
- Retryable jobs with bounded retries, observable failures and dead-letter handling.
- Versioned configuration and immutable source references.
- Explicit timezone and UTC timestamps.
- Metrics for acquisition lag, processing failures, scene coverage, candidate count, and reviewer outcomes.
- No secrets or personal data in processing logs.
- Human override and correction workflows with an audit trail.

## Current status

The repository's historical `pipeline/nbr_diff.py` and `ml/unet_stub.py` were starter placeholders. They must not be described as a real detection system. The pipeline must be implemented and validated against this design before any satellite intelligence capability is advertised as operational.
