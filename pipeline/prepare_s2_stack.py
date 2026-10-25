"""Prepare a provenance-tagged 20 m Sentinel-2 L2A analysis stack.

This tool prepares one granule/tile from supplied product files; it does not search
or download scenes from Copernicus. Band resampling and radiometric offsets are
explicit and included in a companion manifest.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import tempfile
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Any

import numpy as np
import rasterio
from rasterio.enums import Resampling
from rasterio.features import bounds as geometry_bounds, geometry_mask
from rasterio.warp import reproject, transform_geom
from rasterio.windows import Window, from_bounds, transform as window_transform

from pipeline.eo_change import BAND_NAMES, STACK_SCHEMA

# Sentinel-2 MSI spectral-band identifiers used in product metadata BOA_ADD_OFFSET entries.
BAND_ID = {"B02": 1, "B04": 3, "B08": 7, "B11": 11, "B12": 12}
TARGET_RESOLUTION_M = 20.0


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source_file:
        while chunk := source_file.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _first_text(root: ET.Element, name: str) -> str | None:
    for element in root.iter():
        if _local_name(element.tag) == name and element.text and element.text.strip():
            return element.text.strip()
    return None


def _baseline_number(value: str) -> float:
    match = re.search(r"(\d{2})[.\-]?(\d{2})", value)
    if not match:
        raise ValueError(f"Unrecognised Sentinel-2 PROCESSING_BASELINE value: {value!r}")
    return int(match.group(1)) + int(match.group(2)) / 100.0


def _read_product_metadata(metadata_path: Path) -> dict[str, Any]:
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Product metadata XML does not exist: {metadata_path}")
    metadata_sha256 = _sha256_file(metadata_path)
    try:
        root = ET.parse(metadata_path).getroot()
    except ET.ParseError as exc:
        raise ValueError(f"Product metadata is not valid XML: {metadata_path.name}") from exc

    product_id = _first_text(root, "PRODUCT_URI")
    if not product_id:
        product_id = _first_text(root, "PRODUCT_ID")
    if not product_id:
        raise ValueError("Product metadata must contain PRODUCT_URI or PRODUCT_ID.")

    baseline = _first_text(root, "PROCESSING_BASELINE")
    if not baseline:
        raise ValueError("Product metadata must contain PROCESSING_BASELINE.")
    baseline_number = _baseline_number(baseline)

    sensing_time = (
        _first_text(root, "SENSING_TIME")
        or _first_text(root, "PRODUCT_START_TIME")
        or _first_text(root, "DATATAKE_SENSING_START")
    )
    if not sensing_time:
        raise ValueError("Product metadata must contain a sensing/acquisition timestamp.")
    try:
        acquisition_date = date.fromisoformat(sensing_time[:10])
    except ValueError as exc:
        raise ValueError(f"Invalid product acquisition timestamp: {sensing_time!r}") from exc

    quantification_text = _first_text(root, "BOA_QUANTIFICATION_VALUE")
    if not quantification_text:
        raise ValueError("Product metadata must contain BOA_QUANTIFICATION_VALUE.")
    try:
        quantification = float(quantification_text)
    except ValueError as exc:
        raise ValueError("BOA_QUANTIFICATION_VALUE must be numeric.") from exc
    if not math.isfinite(quantification) or quantification <= 0:
        raise ValueError("BOA_QUANTIFICATION_VALUE must be finite and positive.")

    offset_elements: dict[int, float] = {}
    for element in root.iter():
        if _local_name(element.tag) != "BOA_ADD_OFFSET":
            continue
        band_id = element.attrib.get("band_id")
        if band_id is None or element.text is None:
            raise ValueError("Each BOA_ADD_OFFSET entry must include band_id and a numeric value.")
        try:
            offset_value = float(element.text.strip())
            numeric_band_id = int(band_id)
        except ValueError as exc:
            raise ValueError("Malformed BOA_ADD_OFFSET entry in product metadata.") from exc
        if not math.isfinite(offset_value):
            raise ValueError("BOA_ADD_OFFSET values must be finite.")
        offset_elements[numeric_band_id] = offset_value

    required_band_ids = {BAND_ID[name] for name in BAND_NAMES[:-1]}
    if offset_elements:
        missing = required_band_ids - set(offset_elements)
        if missing:
            raise ValueError(
                "BOA_ADD_OFFSET list is present but missing required band IDs: "
                + ", ".join(str(item) for item in sorted(missing))
            )
        offsets = {name: offset_elements[BAND_ID[name]] for name in BAND_NAMES[:-1]}
    elif baseline_number < 4.0:
        # ESA introduced BOA_ADD_OFFSET with processing baseline 04.00.
        # For older baseline products, no offset entry means a zero offset.
        offsets = {name: 0.0 for name in BAND_NAMES[:-1]}
    else:
        raise ValueError(
            "Processing baseline 04.00 or later requires BOA_ADD_OFFSET metadata; "
            "refusing to guess missing radiometric offsets."
        )

    return {
        "source_product_id": product_id,
        "acquisition_date": acquisition_date.isoformat(),
        "processing_baseline": baseline,
        "baseline_number": baseline_number,
        "quantification_value": quantification,
        "offsets": offsets,
        "metadata_sha256": metadata_sha256,
    }


def _read_aoi(path: Path, target_crs: rasterio.crs.CRS) -> tuple[list[dict[str, Any]], str]:
    if not path.is_file():
        raise FileNotFoundError(f"AOI GeoJSON does not exist: {path}")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError("AOI must be a readable GeoJSON file.") from exc

    if payload.get("type") == "FeatureCollection":
        geometries = [
            feature.get("geometry")
            for feature in payload.get("features", [])
            if feature.get("geometry") is not None
        ]
    elif payload.get("type") == "Feature":
        geometries = [payload.get("geometry")]
    elif payload.get("type") in {"Polygon", "MultiPolygon"}:
        geometries = [payload]
    else:
        raise ValueError("AOI GeoJSON must be a Polygon, MultiPolygon, Feature, or FeatureCollection.")
    geometries = [geometry for geometry in geometries if geometry]
    if not geometries or any(
        geometry.get("type") not in {"Polygon", "MultiPolygon"} for geometry in geometries
    ):
        raise ValueError("AOI GeoJSON must contain at least one Polygon or MultiPolygon geometry.")

    # RFC 7946 GeoJSON coordinates are WGS84 longitude/latitude.
    projected = [
        transform_geom("EPSG:4326", target_crs, geometry, precision=-1)
        for geometry in geometries
    ]
    return projected, _sha256_file(path)


def _validate_reference(
    path: Path,
    *,
    aoi_geojson: Path | None,
    max_pixels: int,
) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Input band file does not exist: {path}")
    with rasterio.open(path) as dataset:
        if dataset.crs is None or not dataset.crs.is_projected:
            raise ValueError(f"{path.name}: band CRS must be projected.")
        units = (dataset.crs.linear_units or "").lower()
        if units not in {"metre", "meter", "metres", "meters"}:
            raise ValueError(f"{path.name}: reference grid must use metres; found {units!r}.")
        if (
            abs(abs(dataset.transform.a) - TARGET_RESOLUTION_M) > 0.5
            or abs(abs(dataset.transform.e) - TARGET_RESOLUTION_M) > 0.5
            or abs(dataset.transform.b) > 1e-7
            or abs(dataset.transform.d) > 1e-7
        ):
            raise ValueError("B11 reference grid must be north-up with 20 m pixels.")
        source_transform = dataset.transform
        source_width = dataset.width
        source_height = dataset.height
        aoi_geometries = None
        aoi_sha256 = None

        if aoi_geojson is not None:
            aoi_geometries, aoi_sha256 = _read_aoi(aoi_geojson, dataset.crs)
            bounds = [geometry_bounds(geometry) for geometry in aoi_geometries]
            min_x = min(item[0] for item in bounds)
            min_y = min(item[1] for item in bounds)
            max_x = max(item[2] for item in bounds)
            max_y = max(item[3] for item in bounds)
            fractional = from_bounds(min_x, min_y, max_x, max_y, source_transform)
            col_start = max(0, math.floor(fractional.col_off))
            row_start = max(0, math.floor(fractional.row_off))
            col_stop = min(source_width, math.ceil(fractional.col_off + fractional.width))
            row_stop = min(source_height, math.ceil(fractional.row_off + fractional.height))
            if col_stop <= col_start or row_stop <= row_start:
                raise ValueError("AOI GeoJSON does not overlap the B11 reference scene.")
            target_width = col_stop - col_start
            target_height = row_stop - row_start
            target_window = Window(col_start, row_start, target_width, target_height)
            target_transform = window_transform(target_window, source_transform)
        else:
            target_width = source_width
            target_height = source_height
            target_window = Window(0, 0, target_width, target_height)
            target_transform = source_transform

        pixel_count = target_width * target_height
        if pixel_count > max_pixels:
            hint = " Provide --aoi-geojson or split the area into smaller tiles." if aoi_geojson is None else " Split the AOI into smaller tiles."
            raise ValueError(
                f"Target grid has {pixel_count:,} pixels, exceeding the configured limit "
                f"{max_pixels:,}.{hint}"
            )
        inside_aoi = None
        if aoi_geometries is not None:
            inside_aoi = geometry_mask(
                aoi_geometries,
                out_shape=(target_height, target_width),
                transform=target_transform,
                invert=True,
                all_touched=False,
            )
            if not np.any(inside_aoi):
                raise ValueError("AOI does not cover any pixel centres on the target grid.")

        return {
            "width": target_width,
            "height": target_height,
            "crs": dataset.crs,
            "transform": target_transform,
            "profile": dataset.profile.copy(),
            "source_width": source_width,
            "source_height": source_height,
            "source_transform": source_transform,
            "window": target_window,
            "inside_aoi": inside_aoi,
            "aoi_sha256": aoi_sha256,
        }


def _resample_band(
    source_path: Path,
    reference: dict[str, Any],
    resampling: Resampling,
    band_name: str,
    inside_aoi: np.ndarray | None = None,
) -> np.ndarray:
    if not source_path.is_file():
        raise FileNotFoundError(f"{band_name} input band does not exist: {source_path}")
    with rasterio.open(source_path) as source:
        if source.count < 1:
            raise ValueError(f"{source_path.name}: no raster band found.")
        if source.crs != reference["crs"]:
            raise ValueError(
                f"{source_path.name}: CRS differs from B11 reference grid; "
                "reproject bands to a common granule CRS first."
            )
        source_data = source.read(1)
        source_nodata = source.nodata if source.nodata is not None else 0
        destination = np.zeros(
            (reference["height"], reference["width"]), dtype=np.float32
        )
        reproject(
            source=source_data,
            destination=destination,
            src_transform=source.transform,
            src_crs=source.crs,
            src_nodata=source_nodata,
            dst_transform=reference["transform"],
            dst_crs=reference["crs"],
            dst_nodata=0,
            resampling=resampling,
            init_dest_nodata=True,
        )
        if inside_aoi is not None:
            destination[~inside_aoi] = 0
        if not np.any(np.isfinite(destination) & (destination != 0)):
            raise ValueError(
                f"{band_name} band produced no valid pixels on the target grid/AOI."
            )
        return destination


def _json_write(path: Path, payload: dict[str, Any]) -> None:
    with path.open("w", encoding="utf-8") as stream:
        json.dump(payload, stream, sort_keys=True, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())


def prepare_s2_stack(
    *,
    metadata_xml: str | Path,
    b02_path: str | Path,
    b04_path: str | Path,
    b08_path: str | Path,
    b11_path: str | Path,
    b12_path: str | Path,
    scl_path: str | Path,
    output_path: str | Path,
    aoi_geojson: str | Path | None = None,
    max_pixels: int = 4_000_000,
) -> dict[str, Any]:
    """Prepare the processor's six-band 20 m stack from one supplied L2A granule."""
    source_paths = {
        "B02": Path(b02_path).expanduser().resolve(),
        "B04": Path(b04_path).expanduser().resolve(),
        "B08": Path(b08_path).expanduser().resolve(),
        "B11": Path(b11_path).expanduser().resolve(),
        "B12": Path(b12_path).expanduser().resolve(),
        "SCL": Path(scl_path).expanduser().resolve(),
    }
    metadata_path = Path(metadata_xml).expanduser().resolve()
    final_path = Path(output_path).expanduser().resolve()
    manifest_path = final_path.with_suffix(final_path.suffix + ".manifest.json")
    if final_path.exists() or manifest_path.exists():
        raise FileExistsError(
            "Stack or companion manifest already exists; choose a new output path."
        )
    if final_path in source_paths.values() or final_path == metadata_path:
        raise ValueError("Output path must not overwrite an input file.")

    if max_pixels < 1:
        raise ValueError("max_pixels must be a positive integer.")
    aoi_path = Path(aoi_geojson).expanduser().resolve() if aoi_geojson is not None else None
    metadata = _read_product_metadata(metadata_path)
    reference = _validate_reference(
        source_paths["B11"], aoi_geojson=aoi_path, max_pixels=max_pixels
    )
    target_pixels = reference["width"] * reference["height"]
    if target_pixels < 1:
        raise ValueError("B11 target grid is empty.")

    resampling_methods = {
        "B02": "average",
        "B04": "average",
        "B08": "average",
        "B11": "average",
        "B12": "average",
        "SCL": "nearest",
    }
    resampled: dict[str, np.ndarray] = {}
    input_hashes: dict[str, str] = {}
    for band_name in BAND_NAMES:
        method = Resampling.nearest if band_name == "SCL" else Resampling.average
        resampled[band_name] = _resample_band(
            source_paths[band_name],
            reference,
            method,
            band_name,
            inside_aoi=reference["inside_aoi"],
        )
        input_hashes[band_name] = _sha256_file(source_paths[band_name])

    final_path.parent.mkdir(parents=True, exist_ok=True)
    staging_dir = Path(
        tempfile.mkdtemp(prefix=f".{final_path.name}.staging-", dir=final_path.parent)
    )
    staged_stack = staging_dir / final_path.name
    staged_manifest = staging_dir / manifest_path.name

    try:
        profile = {
            "driver": "GTiff",
            "width": reference["width"],
            "height": reference["height"],
            "count": len(BAND_NAMES),
            "dtype": "float32",
            "crs": reference["crs"],
            "transform": reference["transform"],
            "nodata": 0,
            "compress": "deflate",
        }
        with rasterio.open(staged_stack, "w", **profile) as output:
            for index, band_name in enumerate(BAND_NAMES, start=1):
                output.write(resampled[band_name], index)
                output.set_band_description(index, band_name)

            tags = {
                "GLRCHAIN_STACK_SCHEMA": STACK_SCHEMA,
                "SOURCE_PRODUCT_ID": metadata["source_product_id"],
                "ACQUISITION_DATE": metadata["acquisition_date"],
                "PROCESSING_BASELINE": metadata["processing_baseline"],
                "REFLECTANCE_QUANTIFICATION_VALUE": str(metadata["quantification_value"]),
                "SOURCE_METADATA_SHA256": metadata["metadata_sha256"],
                "GRID_PIXEL_LIMIT": str(max_pixels),
                "RESAMPLING_METHODS": json.dumps(
                    resampling_methods, sort_keys=True, separators=(",", ":")
                ),
                "SOURCE_BAND_SHA256S": json.dumps(
                    input_hashes, sort_keys=True, separators=(",", ":")
                ),
            }
            if reference["aoi_sha256"]:
                tags["AOI_GEOJSON_SHA256"] = reference["aoi_sha256"]
            tags.update(
                {
                    f"BOA_ADD_OFFSET_{band}": str(offset)
                    for band, offset in metadata["offsets"].items()
                }
            )
            output.update_tags(**tags)

        stack_sha256 = _sha256_file(staged_stack)
        manifest = {
            "manifest_schema": "GLRCHAIN_S2_STACK_MANIFEST_V1",
            "source_product_id": metadata["source_product_id"],
            "acquisition_date": metadata["acquisition_date"],
            "processing_baseline": metadata["processing_baseline"],
            "source_metadata_sha256": metadata["metadata_sha256"],
            "source_band_files": {
                band: {
                    "filename": source_paths[band].name,
                    "sha256": input_hashes[band],
                    "resampling": resampling_methods[band],
                }
                for band in BAND_NAMES
            },
            "radiometry": {
                "formula": "(DN + BOA_ADD_OFFSET) / REFLECTANCE_QUANTIFICATION_VALUE",
                "quantification_value": metadata["quantification_value"],
                "boa_add_offsets": metadata["offsets"],
            },
            "grid": {
                "crs": reference["crs"].to_string(),
                "width": reference["width"],
                "height": reference["height"],
                "transform": list(reference["transform"]),
                "resolution_m": TARGET_RESOLUTION_M,
                "source_reference_width": reference["source_width"],
                "source_reference_height": reference["source_height"],
                "aoi_geojson_sha256": reference["aoi_sha256"],
                "max_pixels": max_pixels,
            },
            "output": {"filename": final_path.name, "sha256": stack_sha256},
            "warning": (
                "The processor prepares supplied bands only. This manifest does not prove "
                "product authenticity or that the stack is cloud-free; retain the original "
                "product and retrieval provenance."
            ),
        }
        _json_write(staged_manifest, manifest)

        os.replace(staged_stack, final_path)
        try:
            os.replace(staged_manifest, manifest_path)
        except Exception:
            final_path.unlink(missing_ok=True)
            raise
    except Exception:
        shutil.rmtree(staging_dir, ignore_errors=True)
        raise
    finally:
        shutil.rmtree(staging_dir, ignore_errors=True)

    return {
        "status": "completed",
        "stack_path": str(final_path),
        "manifest_path": str(manifest_path),
        "stack_sha256": stack_sha256,
        "source_product_id": metadata["source_product_id"],
        "acquisition_date": metadata["acquisition_date"],
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Prepare one supplied Sentinel-2 L2A granule as a tagged six-band, 20 m "
            "GeoTIFF. This command does not download product files."
        )
    )
    parser.add_argument("--metadata-xml", required=True, type=Path)
    parser.add_argument("--b02", required=True, type=Path)
    parser.add_argument("--b04", required=True, type=Path)
    parser.add_argument("--b08", required=True, type=Path)
    parser.add_argument("--b11", required=True, type=Path, help="20 m grid reference.")
    parser.add_argument("--b12", required=True, type=Path)
    parser.add_argument("--scl", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path, help="New output GeoTIFF path.")
    parser.add_argument(
        "--aoi-geojson",
        type=Path,
        help="Optional RFC 7946 WGS84 polygon GeoJSON to clip the stack to an area of interest.",
    )
    parser.add_argument(
        "--max-pixels",
        type=int,
        default=4_000_000,
        help="Maximum output pixels (default 4,000,000); large full-scene inputs must be clipped.",
    )
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    try:
        result = prepare_s2_stack(
            metadata_xml=args.metadata_xml,
            b02_path=args.b02,
            b04_path=args.b04,
            b08_path=args.b08,
            b11_path=args.b11,
            b12_path=args.b12,
            scl_path=args.scl,
            output_path=args.output,
            aoi_geojson=args.aoi_geojson,
            max_pixels=args.max_pixels,
        )
    except (FileNotFoundError, FileExistsError, OSError, RuntimeError, ValueError) as exc:
        parser.exit(2, f"error: {exc}\n")
    print(json.dumps(result, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
