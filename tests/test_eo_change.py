from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from pipeline.eo_change import (
    BAND_NAMES,
    STACK_SCHEMA,
    ChangeThresholds,
    _inspect_scene,
    _load_scene_arrays,
    process_pair,
)

WIDTH = 32
HEIGHT = 32
TRANSFORM = from_origin(500_000, 700_000, 20, 20)
CRS = "EPSG:32631"
QUANTIFICATION = 10_000.0
OFFSETS = {name: -1_000.0 for name in BAND_NAMES[:-1]}


def _reflectance_stack(
    path: Path,
    *,
    product_id: str,
    acquisition_date: str,
    transform=TRANSFORM,
    mining_pixels: tuple[tuple[slice, slice], ...] | None = None,
    cloud_pixels: np.ndarray | None = None,
) -> Path:
    """Create deterministic, non-real synthetic pixels for algorithm tests."""
    blue = np.full((HEIGHT, WIDTH), 0.10, dtype=np.float32)
    red = np.full((HEIGHT, WIDTH), 0.10, dtype=np.float32)
    nir = np.full((HEIGHT, WIDTH), 0.80, dtype=np.float32)
    swir1 = np.full((HEIGHT, WIDTH), 0.20, dtype=np.float32)
    swir2 = np.full((HEIGHT, WIDTH), 0.20, dtype=np.float32)
    scl = np.full((HEIGHT, WIDTH), 4, dtype=np.uint16)

    if mining_pixels is not None:
        for region in mining_pixels:
            blue[region] = 0.20
            red[region] = 0.30
            nir[region] = 0.25
            swir1[region] = 0.50
            swir2[region] = 0.50

    if cloud_pixels is not None:
        scl[cloud_pixels] = 9

    reflectance = {"B02": blue, "B04": red, "B08": nir, "B11": swir1, "B12": swir2}
    raw_bands = [
        np.rint(reflectance[name] * QUANTIFICATION - OFFSETS[name]).astype(np.uint16)
        for name in BAND_NAMES[:-1]
    ]
    raw_bands.append(scl)
    data = np.stack(raw_bands, axis=0)

    profile = {
        "driver": "GTiff",
        "width": WIDTH,
        "height": HEIGHT,
        "count": len(BAND_NAMES),
        "dtype": "uint16",
        "crs": CRS,
        "transform": transform,
        "nodata": 0,
        "compress": "deflate",
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(data)
        for index, band_name in enumerate(BAND_NAMES, start=1):
            dataset.set_band_description(index, band_name)
        tags = {
            "GLRCHAIN_STACK_SCHEMA": STACK_SCHEMA,
            "SOURCE_PRODUCT_ID": product_id,
            "ACQUISITION_DATE": acquisition_date,
            "PROCESSING_BASELINE": "CI-SYNTHETIC-ONLY",
            "REFLECTANCE_QUANTIFICATION_VALUE": str(QUANTIFICATION),
        }
        tags.update({f"BOA_ADD_OFFSET_{name}": str(value) for name, value in OFFSETS.items()})
        dataset.update_tags(**tags)
    return path


def _thresholds(min_area_m2: float = 2_000.0) -> ChangeThresholds:
    return ChangeThresholds(
        ndvi_drop=0.25,
        bsi_rise=0.20,
        nbr_drop=0.25,
        min_signals=2,
        min_area_m2=min_area_m2,
    )


def test_reflectance_conversion_applies_per_band_boa_offsets(tmp_path: Path) -> None:
    scene_path = _reflectance_stack(
        tmp_path / "before.tif",
        product_id="SYNTHETIC-BEFORE",
        acquisition_date="2026-01-01",
    )
    scene = _inspect_scene(scene_path, max_pixels=100_000)
    reflectance, scl, valid = _load_scene_arrays(scene)

    assert reflectance["B02"][12, 12] == pytest.approx(0.10, abs=1e-4)
    assert reflectance["B08"][12, 12] == pytest.approx(0.80, abs=1e-4)
    assert scl[12, 12] == 4
    assert valid.all()


def test_generates_georeferenced_candidates_and_hash_manifest(tmp_path: Path) -> None:
    main_change = np.s_[10:15, 10:15]
    small_change = np.s_[20:22, 20:22]
    before_path = _reflectance_stack(
        tmp_path / "before.tif",
        product_id="SYNTHETIC-BEFORE",
        acquisition_date="2026-01-01",
    )
    after_path = _reflectance_stack(
        tmp_path / "after.tif",
        product_id="SYNTHETIC-AFTER",
        acquisition_date="2026-03-01",
        mining_pixels=(main_change, small_change),
        cloud_pixels=np.s_[0:4, :],
    )

    result = process_pair(
        before_path,
        after_path,
        tmp_path / "result",
        _thresholds(min_area_m2=2_000),
        max_pixels=100_000,
    )

    assert result["status"] == "completed"
    assert result["candidate_count"] == 1
    assert result["candidate_pixel_count"] == 25
    assert result["valid_pixel_count"] < WIDTH * HEIGHT

    output_dir = Path(result["output_directory"])
    manifest = json.loads((output_dir / "run_manifest.json").read_text("utf-8"))
    candidates = json.loads((output_dir / "change_candidates.geojson").read_text("utf-8"))
    assert manifest["algorithm_version"] == "glrchain-s2-change-v1"
    assert manifest["counts"]["candidate_features_after_area_filter"] == 1
    assert manifest["inputs"][0]["sha256"] == hashlib.sha256(before_path.read_bytes()).hexdigest()
    assert manifest["inputs"][1]["sha256"] == hashlib.sha256(after_path.read_bytes()).hexdigest()
    assert manifest["outputs"]["candidate_mask.tif"] == hashlib.sha256(
        (output_dir / "candidate_mask.tif").read_bytes()
    ).hexdigest()
    assert len(candidates["features"]) == 1

    feature = candidates["features"][0]
    assert feature["properties"]["candidate_type"] == "surface_change_screening"
    assert feature["properties"]["review_status"] == "pending_human_review"
    assert feature["properties"]["pixel_count"] == 25
    assert feature["properties"]["area_m2"] == pytest.approx(10_000.0)
    assert feature["properties"]["mean_ndvi_drop"] >= 0.25
    assert feature["properties"]["mean_bsi_rise"] >= 0.20
    assert feature["properties"]["mean_nbr_drop"] >= 0.25
    # The GeoJSON is transformed from projected metres to RFC 7946 WGS84 coordinates.
    longitude, latitude = feature["geometry"]["coordinates"][0][0]
    assert -180 <= longitude <= 180
    assert -90 <= latitude <= 90

    with rasterio.open(output_dir / "candidate_mask.tif") as output:
        assert output.count == 2
        assert output.nodata == 255
        assert output.descriptions[0].startswith("surface_change_candidate")
        raster_candidate_count = int(np.count_nonzero(output.read(1) == 1))
        assert raster_candidate_count == 25


def test_unchanged_surface_returns_empty_feature_collection(tmp_path: Path) -> None:
    before_path = _reflectance_stack(
        tmp_path / "before.tif",
        product_id="SYNTHETIC-BEFORE",
        acquisition_date="2026-01-01",
    )
    after_path = _reflectance_stack(
        tmp_path / "after.tif",
        product_id="SYNTHETIC-AFTER",
        acquisition_date="2026-03-01",
    )

    result = process_pair(
        before_path,
        after_path,
        tmp_path / "no-change-result",
        _thresholds(),
        max_pixels=100_000,
    )

    candidates = json.loads(
        (Path(result["output_directory"]) / "change_candidates.geojson").read_text("utf-8")
    )
    assert result["candidate_count"] == 0
    assert result["candidate_pixel_count"] == 0
    assert candidates["features"] == []


def test_candidate_id_changes_when_screening_configuration_changes(tmp_path: Path) -> None:
    mining = np.s_[10:15, 10:15]
    before_path = _reflectance_stack(
        tmp_path / "before.tif",
        product_id="SYNTHETIC-BEFORE",
        acquisition_date="2026-01-01",
    )
    after_path = _reflectance_stack(
        tmp_path / "after.tif",
        product_id="SYNTHETIC-AFTER",
        acquisition_date="2026-03-01",
        mining_pixels=(mining,),
    )

    two_signal_result = process_pair(
        before_path,
        after_path,
        tmp_path / "two-signal-result",
        _thresholds(),
        max_pixels=100_000,
    )
    three_signal_thresholds = ChangeThresholds(
        ndvi_drop=0.25,
        bsi_rise=0.20,
        nbr_drop=0.25,
        min_signals=3,
        min_area_m2=2_000,
    )
    three_signal_result = process_pair(
        before_path,
        after_path,
        tmp_path / "three-signal-result",
        three_signal_thresholds,
        max_pixels=100_000,
    )
    two_signal_features = json.loads(
        (Path(two_signal_result["output_directory"]) / "change_candidates.geojson").read_text("utf-8")
    )["features"]
    three_signal_features = json.loads(
        (Path(three_signal_result["output_directory"]) / "change_candidates.geojson").read_text("utf-8")
    )["features"]

    assert len(two_signal_features) == len(three_signal_features) == 1
    assert two_signal_features[0]["geometry"] == three_signal_features[0]["geometry"]
    assert two_signal_features[0]["id"] != three_signal_features[0]["id"]


def test_rejects_misaligned_scenes_and_existing_output_directory(tmp_path: Path) -> None:
    before_path = _reflectance_stack(
        tmp_path / "before.tif",
        product_id="SYNTHETIC-BEFORE",
        acquisition_date="2026-01-01",
    )
    shifted = from_origin(500_020, 700_000, 20, 20)
    after_path = _reflectance_stack(
        tmp_path / "after.tif",
        product_id="SYNTHETIC-AFTER",
        acquisition_date="2026-03-01",
        transform=shifted,
    )

    with pytest.raises(ValueError, match="affine transform differs"):
        process_pair(
            before_path,
            after_path,
            tmp_path / "misaligned-result",
            _thresholds(),
            max_pixels=100_000,
        )

    existing = tmp_path / "existing"
    existing.mkdir()
    with pytest.raises(FileExistsError, match="already exists"):
        process_pair(
            before_path,
            _reflectance_stack(
                tmp_path / "aligned-after.tif",
                product_id="SYNTHETIC-ALIGNED-AFTER",
                acquisition_date="2026-03-01",
            ),
            existing,
            _thresholds(),
            max_pixels=100_000,
        )


def test_rejects_out_of_order_acquisition_dates(tmp_path: Path) -> None:
    before_path = _reflectance_stack(
        tmp_path / "before.tif",
        product_id="SYNTHETIC-BEFORE",
        acquisition_date="2026-04-01",
    )
    after_path = _reflectance_stack(
        tmp_path / "after.tif",
        product_id="SYNTHETIC-AFTER",
        acquisition_date="2026-03-01",
    )

    with pytest.raises(ValueError, match="must be later"):
        process_pair(
            before_path,
            after_path,
            tmp_path / "out-of-order-result",
            _thresholds(),
            max_pixels=100_000,
        )


def test_thresholds_must_be_explicitly_valid(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="ndvi_drop"):
        ChangeThresholds(ndvi_drop=0, bsi_rise=0.2, nbr_drop=0.2).validate()
