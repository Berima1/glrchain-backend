"""Reproducible Sentinel-2 L2A surface-change screening.

This module processes two analysis-ready, co-registered stacks. It does not fetch
imagery or claim that a candidate is illegal mining. Candidates are for authorised
human review only; thresholds and imagery provenance are included in every run.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import shutil
import tempfile
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.features import shapes
from rasterio.warp import transform_geom
from scipy import ndimage

ALGORITHM_VERSION = "glrchain-s2-change-v1"
STACK_SCHEMA = "GLRCHAIN_S2_L2A_STACK_V1"
BAND_NAMES = ("B02", "B04", "B08", "B11", "B12", "SCL")
REFLECTANCE_BANDS = BAND_NAMES[:-1]
SCL_BAND = "SCL"
INVALID_SCL_CLASSES = (0, 1, 2, 3, 7, 8, 9, 10, 11)
EPSILON = 1e-6
DEFAULT_MAX_PIXELS = 4_000_000


@dataclass(frozen=True)
class ChangeThresholds:
    """Explicit screening thresholds; they must be calibrated for the target area."""

    ndvi_drop: float
    bsi_rise: float
    nbr_drop: float
    min_signals: int = 2
    min_area_m2: float = 1_000.0

    def validate(self) -> None:
        for name in ("ndvi_drop", "bsi_rise", "nbr_drop"):
            value = getattr(self, name)
            if not math.isfinite(value) or value <= 0 or value > 2:
                raise ValueError(f"{name} must be finite and in the interval (0, 2].")
        if self.min_signals not in (1, 2, 3):
            raise ValueError("min_signals must be 1, 2, or 3.")
        if not math.isfinite(self.min_area_m2) or self.min_area_m2 <= 0:
            raise ValueError("min_area_m2 must be a finite positive number.")


@dataclass(frozen=True)
class SceneMetadata:
    path: Path
    width: int
    height: int
    crs: rasterio.crs.CRS
    transform: rasterio.Affine
    nodata: float | int | None
    source_product_id: str
    acquisition_date: date
    processing_baseline: str
    quantification_value: float
    offsets: dict[str, float]
    file_sha256: str


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _parse_scene_date(value: str, path: Path) -> date:
    try:
        return date.fromisoformat(value[:10])
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"{path.name}: ACQUISITION_DATE must begin with an ISO date YYYY-MM-DD."
        ) from exc


def _require_tag(tags: dict[str, str], key: str, path: Path) -> str:
    value = tags.get(key, "").strip()
    if not value:
        raise ValueError(f"{path.name}: required GeoTIFF tag {key!r} is missing.")
    return value


def _inspect_scene(path: Path, max_pixels: int) -> SceneMetadata:
    if not path.is_file():
        raise FileNotFoundError(f"Input scene does not exist or is not a file: {path}")

    digest = _sha256_file(path)
    with rasterio.open(path) as dataset:
        if dataset.count != len(BAND_NAMES):
            raise ValueError(
                f"{path.name}: expected exactly {len(BAND_NAMES)} bands in the "
                f"order {BAND_NAMES}; found {dataset.count}."
            )
        if dataset.width * dataset.height > max_pixels:
            raise ValueError(
                f"{path.name}: {dataset.width * dataset.height:,} pixels exceeds "
                f"the safety limit {max_pixels:,}. Clip/split the AOI into smaller tiles."
            )
        if dataset.crs is None or not dataset.crs.is_projected:
            raise ValueError(f"{path.name}: input CRS must be projected in linear units.")
        units = (dataset.crs.linear_units or "").lower()
        if units not in {"metre", "meter", "metres", "meters"}:
            raise ValueError(
                f"{path.name}: projected CRS linear units must be metres; found {units!r}."
            )
        if any(abs(float(value)) == 0 for value in (dataset.transform.a, dataset.transform.e)):
            raise ValueError(f"{path.name}: raster pixel width and height must be non-zero.")
        pixel_area_m2 = abs(
            dataset.transform.a * dataset.transform.e
            - dataset.transform.b * dataset.transform.d
        )
        if not math.isfinite(pixel_area_m2) or pixel_area_m2 <= 0:
            raise ValueError(f"{path.name}: raster affine transform has zero/non-finite pixel area.")

        descriptions = tuple((item or "").strip().upper() for item in dataset.descriptions)
        if descriptions != BAND_NAMES:
            raise ValueError(
                f"{path.name}: band descriptions must be exactly {BAND_NAMES}; "
                f"found {descriptions}. Do not rely on ambiguous band positions."
            )

        tags = dataset.tags()
        schema = _require_tag(tags, "GLRCHAIN_STACK_SCHEMA", path)
        if schema != STACK_SCHEMA:
            raise ValueError(
                f"{path.name}: GLRCHAIN_STACK_SCHEMA must be {STACK_SCHEMA!r}; found {schema!r}."
            )
        source_product_id = _require_tag(tags, "SOURCE_PRODUCT_ID", path)
        acquisition_date = _parse_scene_date(
            _require_tag(tags, "ACQUISITION_DATE", path), path
        )
        baseline = _require_tag(tags, "PROCESSING_BASELINE", path)
        try:
            quantification_value = float(
                _require_tag(tags, "REFLECTANCE_QUANTIFICATION_VALUE", path)
            )
        except ValueError as exc:
            raise ValueError(
                f"{path.name}: REFLECTANCE_QUANTIFICATION_VALUE must be numeric."
            ) from exc
        if not math.isfinite(quantification_value) or quantification_value <= 0:
            raise ValueError(
                f"{path.name}: REFLECTANCE_QUANTIFICATION_VALUE must be finite and positive."
            )

        offsets: dict[str, float] = {}
        for band in REFLECTANCE_BANDS:
            key = f"BOA_ADD_OFFSET_{band}"
            try:
                offsets[band] = float(_require_tag(tags, key, path))
            except ValueError as exc:
                raise ValueError(f"{path.name}: {key} must be numeric.") from exc
            if not math.isfinite(offsets[band]):
                raise ValueError(f"{path.name}: {key} must be finite.")

        return SceneMetadata(
            path=path,
            width=dataset.width,
            height=dataset.height,
            crs=dataset.crs,
            transform=dataset.transform,
            nodata=dataset.nodata,
            source_product_id=source_product_id,
            acquisition_date=acquisition_date,
            processing_baseline=baseline,
            quantification_value=quantification_value,
            offsets=offsets,
            file_sha256=digest,
        )


def _load_scene_arrays(scene: SceneMetadata) -> tuple[dict[str, np.ndarray], np.ndarray, np.ndarray]:
    reflectance: dict[str, np.ndarray] = {}
    with rasterio.open(scene.path) as dataset:
        if dataset.width != scene.width or dataset.height != scene.height:
            raise ValueError(f"{scene.path.name}: dimensions changed after validation.")
        tags = dataset.tags()
        if tags.get("SOURCE_PRODUCT_ID") != scene.source_product_id:
            raise ValueError(f"{scene.path.name}: metadata changed after validation.")

        valid = dataset.dataset_mask() > 0
        for index, band in enumerate(REFLECTANCE_BANDS, start=1):
            raw = dataset.read(index).astype(np.float32, copy=False)
            # Sentinel-2 L2A reflectance requires the band-specific BOA offset
            # before division by the product's quantification value.
            values = (raw + np.float32(scene.offsets[band])) / np.float32(
                scene.quantification_value
            )
            reflectance[band] = values
            valid &= dataset.read_masks(index) > 0
            valid &= np.isfinite(values)

        scl = dataset.read(len(BAND_NAMES))
        valid &= dataset.read_masks(len(BAND_NAMES)) > 0

    return reflectance, scl, valid


def _normalized_difference(left: np.ndarray, right: np.ndarray) -> np.ndarray:
    denominator = left + right
    output = np.full(left.shape, np.nan, dtype=np.float32)
    np.divide(
        left - right,
        denominator,
        out=output,
        where=np.isfinite(denominator) & (np.abs(denominator) > EPSILON),
    )
    return output


def _indices(reflectance: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    blue = reflectance["B02"]
    red = reflectance["B04"]
    nir = reflectance["B08"]
    swir1 = reflectance["B11"]
    swir2 = reflectance["B12"]

    ndvi = _normalized_difference(nir, red)
    nbr = _normalized_difference(nir, swir2)
    # Bare Soil Index: ((SWIR1 + Red) - (NIR + Blue)) / ((SWIR1 + Red) + (NIR + Blue))
    bsi_numerator = (swir1 + red) - (nir + blue)
    bsi_denominator = (swir1 + red) + (nir + blue)
    bsi = np.full(red.shape, np.nan, dtype=np.float32)
    np.divide(
        bsi_numerator,
        bsi_denominator,
        out=bsi,
        where=np.isfinite(bsi_denominator) & (np.abs(bsi_denominator) > EPSILON),
    )
    return {"ndvi": ndvi, "nbr": nbr, "bsi": bsi}


def _scl_valid(scl: np.ndarray) -> np.ndarray:
    # This general land-disturbance screen excludes SCL water class 6 as well;
    # water/sediment changes should use a separately validated river-monitoring model.
    invalid = np.isin(scl, INVALID_SCL_CLASSES + (6,))
    return ~invalid


def _label_candidates(mask: np.ndarray) -> tuple[np.ndarray, int]:
    # Eight-neighbour connectivity is used consistently by labeling and polygonization.
    structure = np.ones((3, 3), dtype=np.uint8)
    labels, count = ndimage.label(mask, structure=structure)
    return labels.astype(np.int32, copy=False), int(count)


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, path)


def process_pair(
    before_path: str | Path,
    after_path: str | Path,
    output_dir: str | Path,
    thresholds: ChangeThresholds,
    *,
    max_pixels: int = DEFAULT_MAX_PIXELS,
) -> dict[str, Any]:
    """Create an auditable surface-change screening result from two L2A stacks.

    Both input stacks must be aligned, projected metre-unit GeoTIFFs with band
    descriptions B02,B04,B08,B11,B12,SCL and required provenance/radiometry tags.
    The output directory must not already exist; artifacts are built in a staging
    directory and then renamed into place so partial runs are not mistaken for success.
    """
    thresholds.validate()
    if max_pixels < 1:
        raise ValueError("max_pixels must be a positive integer.")

    before_file = Path(before_path).expanduser().resolve()
    after_file = Path(after_path).expanduser().resolve()
    final_dir = Path(output_dir).expanduser().resolve()
    if before_file == after_file:
        raise ValueError("Before and after scenes must be distinct files.")
    if final_dir.exists():
        raise FileExistsError(
            f"Output directory already exists: {final_dir}. Choose a new output directory."
        )

    before = _inspect_scene(before_file, max_pixels)
    after = _inspect_scene(after_file, max_pixels)
    if before.source_product_id == after.source_product_id:
        raise ValueError("Before and after scenes have the same SOURCE_PRODUCT_ID.")
    if after.acquisition_date <= before.acquisition_date:
        raise ValueError("After scene ACQUISITION_DATE must be later than before scene.")
    if before.width != after.width or before.height != after.height:
        raise ValueError("Before/after dimensions differ; resample/clip them to the same grid first.")
    if before.crs != after.crs:
        raise ValueError("Before/after CRS differs; reproject them to the same grid first.")
    if before.transform != after.transform:
        raise ValueError("Before/after affine transform differs; coregister them to the same grid first.")

    before_reflectance, before_scl, before_valid = _load_scene_arrays(before)
    after_reflectance, after_scl, after_valid = _load_scene_arrays(after)
    valid = before_valid & after_valid & _scl_valid(before_scl) & _scl_valid(after_scl)

    before_indices = _indices(before_reflectance)
    after_indices = _indices(after_reflectance)
    for index_name in ("ndvi", "nbr", "bsi"):
        valid &= np.isfinite(before_indices[index_name])
        valid &= np.isfinite(after_indices[index_name])

    ndvi_drop = before_indices["ndvi"] - after_indices["ndvi"]
    bsi_rise = after_indices["bsi"] - before_indices["bsi"]
    nbr_drop = before_indices["nbr"] - after_indices["nbr"]

    ndvi_signal = ndvi_drop >= thresholds.ndvi_drop
    bsi_signal = bsi_rise >= thresholds.bsi_rise
    nbr_signal = nbr_drop >= thresholds.nbr_drop
    support_count = (
        ndvi_signal.astype(np.uint8)
        + bsi_signal.astype(np.uint8)
        + nbr_signal.astype(np.uint8)
    )
    candidate_mask = valid & (support_count >= thresholds.min_signals)

    labels, label_count = _label_candidates(candidate_mask)
    pixel_counts = np.bincount(labels.ravel(), minlength=label_count + 1)
    pixel_area_m2 = abs(
        before.transform.a * before.transform.e
        - before.transform.b * before.transform.d
    )
    accepted_labels = pixel_counts.astype(np.float64) * pixel_area_m2 >= thresholds.min_area_m2
    accepted_labels[0] = False
    accepted_mask = accepted_labels[labels]

    candidate_pixel_count = int(np.count_nonzero(accepted_mask))
    valid_pixel_count = int(np.count_nonzero(valid))
    invalid_pixel_count = int(valid.size - valid_pixel_count)

    flat_labels = labels.ravel()
    weights = {
        "mean_ndvi_drop": ndvi_drop,
        "mean_bsi_rise": bsi_rise,
        "mean_nbr_drop": nbr_drop,
        "mean_support_count": support_count.astype(np.float32),
    }
    feature_means: dict[str, np.ndarray] = {}
    for name, values in weights.items():
        finite_values = np.where(candidate_mask, values, 0.0).astype(np.float64, copy=False)
        sums = np.bincount(
            flat_labels,
            weights=finite_values.ravel(),
            minlength=label_count + 1,
        )
        feature_means[name] = np.divide(
            sums,
            pixel_counts,
            out=np.zeros_like(sums, dtype=np.float64),
            where=pixel_counts > 0,
        )

    geojson_features: list[dict[str, Any]] = []
    for geometry, raw_label in shapes(
        labels,
        mask=(labels > 0),
        connectivity=8,
        transform=before.transform,
    ):
        label_id = int(raw_label)
        if label_id > label_count or not accepted_labels[label_id]:
            continue
        area_m2 = float(pixel_counts[label_id] * pixel_area_m2)
        candidate_id = hashlib.sha256(
            (
                f"{before.source_product_id}|{after.source_product_id}|"
                f"{ALGORITHM_VERSION}|{label_id}"
            ).encode("utf-8")
        ).hexdigest()[:24]
        wgs84_geometry = transform_geom(
            before.crs,
            "EPSG:4326",
            geometry,
            precision=7,
        )
        properties = {
            "candidate_id": candidate_id,
            "candidate_type": "surface_change_screening",
            "review_status": "pending_human_review",
            "area_m2": area_m2,
            "pixel_count": int(pixel_counts[label_id]),
            "mean_ndvi_drop": float(feature_means["mean_ndvi_drop"][label_id]),
            "mean_bsi_rise": float(feature_means["mean_bsi_rise"][label_id]),
            "mean_nbr_drop": float(feature_means["mean_nbr_drop"][label_id]),
            "mean_support_count": float(feature_means["mean_support_count"][label_id]),
            "before_product_id": before.source_product_id,
            "after_product_id": after.source_product_id,
            "before_date": before.acquisition_date.isoformat(),
            "after_date": after.acquisition_date.isoformat(),
            "algorithm_version": ALGORITHM_VERSION,
        }
        geojson_features.append(
            {"type": "Feature", "id": candidate_id, "geometry": wgs84_geometry, "properties": properties}
        )

    final_dir.parent.mkdir(parents=True, exist_ok=True)
    stage_dir = Path(tempfile.mkdtemp(prefix=f".{final_dir.name}.staging-", dir=final_dir.parent))
    try:
        mask_path = stage_dir / "candidate_mask.tif"
        geojson_path = stage_dir / "change_candidates.geojson"
        manifest_path = stage_dir / "run_manifest.json"

        nodata = np.uint8(255)
        mask_band = np.where(valid, accepted_mask.astype(np.uint8), nodata)
        support_band = np.where(valid, support_count, nodata).astype(np.uint8)
        output_profile = {
            "driver": "GTiff",
            "height": before.height,
            "width": before.width,
            "count": 2,
            "dtype": "uint8",
            "crs": before.crs,
            "transform": before.transform,
            "nodata": 255,
            "compress": "deflate",
        }
        with rasterio.open(mask_path, "w", **output_profile) as output:
            output.write(mask_band.astype(np.uint8), 1)
            output.write(support_band, 2)
            output.set_band_description(1, "surface_change_candidate_0_no_1_yes_255_nodata")
            output.set_band_description(2, "supporting_signal_count_0_to_3_255_nodata")
            output.update_tags(
                ALGORITHM_VERSION=ALGORITHM_VERSION,
                BEFORE_PRODUCT_ID=before.source_product_id,
                AFTER_PRODUCT_ID=after.source_product_id,
                BEFORE_DATE=before.acquisition_date.isoformat(),
                AFTER_DATE=after.acquisition_date.isoformat(),
                THRESHOLDS_JSON=json.dumps(asdict(thresholds), sort_keys=True),
                CANDIDATE_SEMANTICS="screening candidate only; requires authorised human review",
            )

        geojson = {
            "type": "FeatureCollection",
            "name": "GLRChain Sentinel-2 surface change screening candidates",
            "features": geojson_features,
        }
        _json_write(geojson_path, geojson)

        outputs = {
            mask_path.name: _sha256_file(mask_path),
            geojson_path.name: _sha256_file(geojson_path),
        }
        manifest: dict[str, Any] = {
            "manifest_schema": "GLRCHAIN_EO_RUN_MANIFEST_V1",
            "algorithm_version": ALGORITHM_VERSION,
            "created_utc": datetime.now(timezone.utc).isoformat(),
            "status": "completed",
            "interpretation": (
                "Surface-change screening only. A candidate is not a determination of "
                "galamsey, illegality, licence status, or criminal liability."
            ),
            "inputs": [
                {
                    "filename": before.path.name,
                    "sha256": before.file_sha256,
                    "source_product_id": before.source_product_id,
                    "acquisition_date": before.acquisition_date.isoformat(),
                    "processing_baseline": before.processing_baseline,
                    "reflectance_quantification_value": before.quantification_value,
                    "boa_add_offsets": before.offsets,
                },
                {
                    "filename": after.path.name,
                    "sha256": after.file_sha256,
                    "source_product_id": after.source_product_id,
                    "acquisition_date": after.acquisition_date.isoformat(),
                    "processing_baseline": after.processing_baseline,
                    "reflectance_quantification_value": after.quantification_value,
                    "boa_add_offsets": after.offsets,
                },
            ],
            "grid": {
                "crs": before.crs.to_string(),
                "width": before.width,
                "height": before.height,
                "transform": list(before.transform),
                "pixel_area_m2": pixel_area_m2,
            },
            "scl_policy": {
                "invalid_classes": list(INVALID_SCL_CLASSES),
                "water_class_6_excluded": True,
                "reason": (
                    "This run screens land-surface change. Water and sediment changes "
                    "require a separately validated river-monitoring method."
                ),
            },
            "thresholds": asdict(thresholds),
            "counts": {
                "pixels_total": int(valid.size),
                "pixels_valid_for_comparison": valid_pixel_count,
                "pixels_masked_or_invalid": invalid_pixel_count,
                "connected_components_before_area_filter": label_count,
                "candidate_features_after_area_filter": len(geojson_features),
                "candidate_pixels_after_area_filter": candidate_pixel_count,
            },
            "outputs": outputs,
        }
        _json_write(manifest_path, manifest)

        # Detect source mutation while this run was processing.
        if _sha256_file(before.path) != before.file_sha256:
            raise RuntimeError("Before input changed during processing; output will not be published.")
        if _sha256_file(after.path) != after.file_sha256:
            raise RuntimeError("After input changed during processing; output will not be published.")

        os.replace(stage_dir, final_dir)
    except Exception:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise

    return {
        "status": "completed",
        "output_directory": str(final_dir),
        "candidate_count": len(geojson_features),
        "candidate_pixel_count": candidate_pixel_count,
        "valid_pixel_count": valid_pixel_count,
        "masked_pixel_count": invalid_pixel_count,
        "manifest": str(final_dir / "run_manifest.json"),
    }


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Create reproducible Sentinel-2 L2A surface-change candidates from two "
            "co-registered GLRCHAIN_S2_L2A_STACK_V1 GeoTIFFs. Results require human review."
        )
    )
    parser.add_argument("--before", type=Path, required=True, help="Earlier analysis-ready stack.")
    parser.add_argument("--after", type=Path, required=True, help="Later analysis-ready stack.")
    parser.add_argument("--output-dir", type=Path, required=True, help="New output directory; it must not exist.")
    parser.add_argument("--ndvi-drop", type=float, required=True, help="Minimum NDVI decrease.")
    parser.add_argument("--bsi-rise", type=float, required=True, help="Minimum Bare Soil Index increase.")
    parser.add_argument("--nbr-drop", type=float, required=True, help="Minimum NBR decrease.")
    parser.add_argument("--min-signals", type=int, choices=(1, 2, 3), default=2)
    parser.add_argument("--min-area-m2", type=float, default=1_000.0)
    parser.add_argument("--max-pixels", type=int, default=DEFAULT_MAX_PIXELS)
    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    thresholds = ChangeThresholds(
        ndvi_drop=args.ndvi_drop,
        bsi_rise=args.bsi_rise,
        nbr_drop=args.nbr_drop,
        min_signals=args.min_signals,
        min_area_m2=args.min_area_m2,
    )
    try:
        result = process_pair(
            args.before,
            args.after,
            args.output_dir,
            thresholds,
            max_pixels=args.max_pixels,
        )
    except (FileNotFoundError, FileExistsError, OSError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
