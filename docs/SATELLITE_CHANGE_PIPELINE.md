# Sentinel-2 Surface-Change Screening Pipeline

**Status:** A real, deterministic raster-processing stage is implemented and has automated synthetic-data tests. Live catalog search/download, production stack preparation, Cloud Run job orchestration, database candidate ingestion, Ghana calibration, and operational approval are still incomplete. Do not present this as a live national galamsey detector.

## What this stage does

Given two prepared Sentinel-2 Level-2A (L2A) stacks of the same AOI, it validates their grid/provenance, computes three spectral indices, applies scene-classification quality masks, screens for multi-index surface change, polygonises connected candidate regions, and writes a run manifest with SHA-256 input/output hashes.

This tool reports **surface-change screening candidates only**. It cannot determine whether a change is illegal mining, whether a permit applies, who caused the change, or whether a crime occurred. An authorised reviewer must evaluate each candidate using other evidence and official datasets.

## Source data and grid contract

The input for `python -m pipeline.eo_change` is two analysis-ready GeoTIFF stacks. Each stack must have exactly six bands in this order, with the same projected metre-unit CRS, dimensions, and affine transform across both dates:

| Band description | Meaning | Native Sentinel-2 resolution |
|---|---|---:|
| `B02` | Blue | 10 m |
| `B04` | Red | 10 m |
| `B08` | Near-infrared (NIR) | 10 m |
| `B11` | Short-wave infrared 1 (SWIR1) | 20 m |
| `B12` | Short-wave infrared 2 (SWIR2) | 20 m |
| `SCL` | Scene classification layer | 20 m |

Sources: [Copernicus Data Space Sentinel-2 L2A bands and resolutions](https://documentation.dataspace.copernicus.eu/APIs/SentinelHub/Data/S2L2A.html) and [Sentinel-2 L2A product description](https://sentinels.copernicus.eu/sentinel-data-access/sentinel-products/sentinel-2-data-products/collection-1-level-2a).

Use the 20 m B11/B12 grid as the output grid for this processing stage. When creating the stack, continuous reflectance bands resampled from 10 m to 20 m must use a documented aggregation method (such as average); the categorical SCL must use nearest-neighbour resampling. The source scenes must cover the same AOI and be coregistered. The processor rejects mismatched grids rather than silently warping them.

### Required GeoTIFF tags

Each stack must contain:

- `GLRCHAIN_STACK_SCHEMA=GLRCHAIN_S2_L2A_STACK_V1`
- `SOURCE_PRODUCT_ID`: original Copernicus product identifier.
- `ACQUISITION_DATE`: ISO date starting with `YYYY-MM-DD`.
- `PROCESSING_BASELINE`: the source product processing baseline.
- `REFLECTANCE_QUANTIFICATION_VALUE`: positive number from the source metadata.
- `BOA_ADD_OFFSET_B02`, `BOA_ADD_OFFSET_B04`, `BOA_ADD_OFFSET_B08`, `BOA_ADD_OFFSET_B11`, and `BOA_ADD_OFFSET_B12`: source metadata values, in the source DN scale.

The radiometric conversion is:

`surface reflectance = (source DN + BOA_ADD_OFFSET) / REFLECTANCE_QUANTIFICATION_VALUE`

This matters because Sentinel-2 processing baseline 04.00 introduced band-dependent radiometric offsets for L2A data; using a simple DN/10000 conversion without checking source metadata can be wrong. See [ESA's Sentinel-2 L2A data-quality report](https://sentinels.copernicus.eu/documents/d/sentinel/ompc-cs-dqr-002-03-2023-i60r0-msi-l2a-dqr-april-2023) and [Sentinel-2 product specification](https://sentinels.copernicus.eu/documents/d/sentinel/s2-pdgs-cs-di-psd-v15-0).

For a stack already converted to unitless reflectance, use quantification value `1` and zero offsets only when that conversion is documented and the processing manifest makes it explicit. Do not guess offsets or product IDs. The metadata parser/stack-preparation step that constructs these tags from the downloaded product is a separate remaining task.

## Quality controls and masking

The processor refuses a run if the files are missing, exceed the configured pixel safety limit, use the wrong band descriptions, are not projected in metres, lack provenance/radiometry tags, have duplicate product IDs, have out-of-order acquisition dates, or are not on the same grid.

It uses the SCL mask to exclude classes 0 (no data), 1 (saturated/defective), 2 (dark area), 3 (cloud shadow), 7 (low-probability cloud/unclassified), 8 (medium-probability cloud), 9 (high-probability cloud), 10 (cirrus), and 11 (snow/ice). It also excludes class 6 (water) for this land-surface screen. Water/sediment change is a separate use case and needs its own validated algorithm; this tool intentionally does not claim to detect river pollution.

A pixel is compared only if both dates have valid raster masks, valid SCL classes, and finite index values. Missing or low-quality pixels are marked NoData in the output mask.

## Indices and candidate rule

The implementation calculates:

- NDVI: `(B08 - B04) / (B08 + B04)`
- NBR: `(B08 - B12) / (B08 + B12)`
- Bare Soil Index (BSI): `((B11 + B04) - (B08 + B02)) / ((B11 + B04) + (B08 + B02))`

NBR is commonly used for vegetation/burn-related analysis; it is **not, by itself, a galamsey detector**. This screen uses it alongside vegetation decline and increased bare-soil response. See the [USGS Normalized Burn Ratio glossary](https://burnseverity.cr.usgs.gov/glossary) for the NBR definition and common interpretation.

For each pixel, it evaluates three configured signals:
1. NDVI decrease meets the explicitly supplied `ndvi_drop` threshold.
2. BSI increase meets the explicitly supplied `bsi_rise` threshold.
3. NBR decrease meets the explicitly supplied `nbr_drop` threshold.

A pixel becomes a screening candidate when at least `min_signals` (1–3) signals meet their thresholds. Contiguous candidate pixels are labelled using 8-neighbour connectivity; components smaller than the explicitly supplied minimum area are removed. The default minimum number of signals is 2, but the three thresholds and minimum area must be supplied to the command. No thresholds in this repository have been calibrated or approved for nationwide Ghana deployment.

## Run locally or in a controlled processing job

Install only the test/geospatial dependencies:

```bash
pip install -r requirements-dev.txt
```

Example with two prepared stacks (the thresholds below are illustrative test parameters, not approved Ghana operating values):

```bash
python -m pipeline.eo_change \
  --before before_stack.tif \
  --after after_stack.tif \
  --output-dir ./eo-run-001 \
  --ndvi-drop 0.20 \
  --bsi-rise 0.10 \
  --nbr-drop 0.15 \
  --min-signals 2 \
  --min-area-m2 1000
```

The output directory must not already exist. A run writes:

- `candidate_mask.tif`: band 1 is 0 (not a retained candidate), 1 (retained candidate), or 255 (NoData); band 2 is the number of threshold signals met (0–3) or 255 (NoData).
- `change_candidates.geojson`: WGS84 geometries and attributes for retained components, including area estimate, pixel count, index-change summaries, source product IDs/dates, algorithm version, and `pending_human_review` status.
- `run_manifest.json`: input product IDs/dates/baselines, input SHA-256s, radiometry offsets, grid, SCL policy, thresholds, pixel/component counts, and output SHA-256s.

The program writes files into a staging directory and publishes the output directory only after outputs are complete and source-file hashes are checked again. The output manifest is generated for auditability; it does not prove that the input product is genuine or that an interpretation is legally correct.

## Current limitations and release requirements

- The stack preparation tool that downloads/opens the official Copernicus product, harmonises bands, reads product XML, and writes this six-band stack still needs to be built and tested.
- The processor is an offline input-pair tool; there is no scheduler, automatic Sentinel-2 catalog search/download, durable processing queue, API-triggered job, Cloud Run worker deployment, or PostgreSQL/PostGIS candidate ingestion yet.
- No Sentinel-1 SAR fusion, multi-temporal compositing, approved protected-area/licence overlay, river-water change model, or model training is implemented here.
- The thresholds must be calibrated using a labelled Ghana dataset with independent validation, measured precision/recall, false-positive/false-negative rates, seasonal/region limitations, and reviewer workload.
- Candidate outputs require a human review workflow and immutable/redundant audit export before any enforcement use.
- Tests use deterministic synthetic raster fixtures to validate the maths, CRS conversion, cloud masking, area filtering, and file integrity. Those tests are not proof of accuracy on real imagery.

See [Release Gates](RELEASE_GATES.md) before connecting this stage to an operational workflow.
