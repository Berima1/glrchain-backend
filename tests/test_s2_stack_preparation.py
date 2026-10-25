from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from rasterio.warp import transform as transform_coords

from pipeline.prepare_s2_stack import prepare_s2_stack

QUANTIFICATION = 10_000
OFFSETS = {"B02": -1_000, "B04": -1_000, "B08": -1_000, "B11": -1_000, "B12": -1_000}
CRS = "EPSG:32631"


def _write_single_band(
    path: Path,
    *,
    array: np.ndarray,
    pixel_size: int,
) -> Path:
    height, width = array.shape
    profile = {
        "driver": "GTiff",
        "width": width,
        "height": height,
        "count": 1,
        "dtype": "uint16",
        "crs": CRS,
        "transform": from_origin(500_000, 700_000, pixel_size, pixel_size),
        "nodata": 0,
        "compress": "deflate",
    }
    with rasterio.open(path, "w", **profile) as dataset:
        dataset.write(array.astype(np.uint16), 1)
    return path


def _write_product_metadata(path: Path, *, include_offsets: bool = True, baseline: str = "05.13") -> Path:
    offsets = ""
    if include_offsets:
        offsets = "<BOA_ADD_OFFSET_VALUES_LIST>" + "".join(
            f'<BOA_ADD_OFFSET band_id="{band_id}">{OFFSETS[band]}</BOA_ADD_OFFSET>'
            for band, band_id in (("B02", 1), ("B04", 3), ("B08", 7), ("B11", 11), ("B12", 12))
        ) + "</BOA_ADD_OFFSET_VALUES_LIST>"
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Level2A>
  <PRODUCT_URI>S2A_MSIL2A_20260101T101000_N{baseline.replace('.', '')}_T31NAA.SAFE</PRODUCT_URI>
  <PROCESSING_BASELINE>{baseline}</PROCESSING_BASELINE>
  <PRODUCT_START_TIME>2026-01-01T10:10:00.000Z</PRODUCT_START_TIME>
  <BOA_QUANTIFICATION_VALUE>{QUANTIFICATION}</BOA_QUANTIFICATION_VALUE>
  {offsets}
</Level2A>
"""
    path.write_text(xml, encoding="utf-8")
    return path


def _make_source_bands(tmp_path: Path) -> dict[str, Path]:
    # All reflectance data are source DN values. The offset is applied by the processor.
    reflectance_values = {"B02": 0.10, "B04": 0.10, "B08": 0.80, "B11": 0.20, "B12": 0.20}
    paths = {}
    for band, reflectance in reflectance_values.items():
        source_dn = int(round(reflectance * QUANTIFICATION - OFFSETS[band]))
        if band in {"B02", "B04", "B08"}:
            array = np.full((64, 64), source_dn, dtype=np.uint16)
            pixel_size = 10
        else:
            array = np.full((32, 32), source_dn, dtype=np.uint16)
            pixel_size = 20
        paths[band] = _write_single_band(
            tmp_path / f"{band}.tif", array=array, pixel_size=pixel_size
        )
    paths["SCL"] = _write_single_band(
        tmp_path / "SCL.tif",
        array=np.full((32, 32), 4, dtype=np.uint16),
        pixel_size=20,
    )
    return paths


def test_prepares_tagged_twenty_metre_stack_and_hash_manifest(tmp_path: Path) -> None:
    metadata = _write_product_metadata(tmp_path / "MTD_MSIL2A.xml")
    bands = _make_source_bands(tmp_path)
    output = tmp_path / "prepared_stack.tif"

    result = prepare_s2_stack(
        metadata_xml=metadata,
        b02_path=bands["B02"],
        b04_path=bands["B04"],
        b08_path=bands["B08"],
        b11_path=bands["B11"],
        b12_path=bands["B12"],
        scl_path=bands["SCL"],
        output_path=output,
    )

    assert result["status"] == "completed"
    assert result["stack_sha256"] == hashlib.sha256(output.read_bytes()).hexdigest()
    manifest = json.loads(Path(result["manifest_path"]).read_text("utf-8"))
    assert manifest["source_product_id"].startswith("S2A_MSIL2A_20260101")
    assert manifest["radiometry"]["quantification_value"] == QUANTIFICATION
    assert manifest["radiometry"]["boa_add_offsets"]["B08"] == -1_000
    assert manifest["source_band_files"]["B02"]["resampling"] == "average"
    assert manifest["source_band_files"]["SCL"]["resampling"] == "nearest"

    with rasterio.open(output) as stack:
        assert (stack.width, stack.height) == (32, 32)
        assert stack.count == 6
        assert stack.crs.to_string() == CRS
        assert tuple(stack.descriptions) == ("B02", "B04", "B08", "B11", "B12", "SCL")
        assert stack.tags()["GLRCHAIN_STACK_SCHEMA"] == "GLRCHAIN_S2_L2A_STACK_V1"
        assert stack.tags()["BOA_ADD_OFFSET_B08"] == "-1000.0"
        assert np.allclose(stack.read(1), 2_000.0)
        assert np.allclose(stack.read(3), 9_000.0)
        assert np.all(stack.read(6) == 4)


def test_refuses_modern_product_without_radiometric_offsets(tmp_path: Path) -> None:
    metadata = _write_product_metadata(
        tmp_path / "MTD_MSIL2A.xml",
        include_offsets=False,
        baseline="05.13",
    )
    bands = _make_source_bands(tmp_path)

    with pytest.raises(ValueError, match="requires BOA_ADD_OFFSET"):
        prepare_s2_stack(
            metadata_xml=metadata,
            b02_path=bands["B02"],
            b04_path=bands["B04"],
            b08_path=bands["B08"],
            b11_path=bands["B11"],
            b12_path=bands["B12"],
            scl_path=bands["SCL"],
            output_path=tmp_path / "should-not-exist.tif",
        )


def test_allows_legacy_baseline_without_offset_metadata(tmp_path: Path) -> None:
    metadata = _write_product_metadata(
        tmp_path / "MTD_MSIL2A.xml",
        include_offsets=False,
        baseline="03.01",
    )
    bands = _make_source_bands(tmp_path)
    output = tmp_path / "legacy-stack.tif"

    prepare_s2_stack(
        metadata_xml=metadata,
        b02_path=bands["B02"],
        b04_path=bands["B04"],
        b08_path=bands["B08"],
        b11_path=bands["B11"],
        b12_path=bands["B12"],
        scl_path=bands["SCL"],
        output_path=output,
    )

    with rasterio.open(output) as stack:
        assert stack.tags()["BOA_ADD_OFFSET_B08"] == "0.0"


def test_aoi_geojson_clips_stack_and_records_provenance(tmp_path: Path) -> None:
    metadata = _write_product_metadata(tmp_path / "MTD_MSIL2A.xml")
    bands = _make_source_bands(tmp_path)

    # Triangle inside the B11 scene: a 200 m x 200 m bounding box gives a 10x10
    # pixel output tile, while the AOI mask leaves pixels outside the polygon as NoData.
    eastings = [500_100, 500_300, 500_100, 500_100]
    northings = [699_800, 699_800, 699_600, 699_800]
    longitudes, latitudes = transform_coords(CRS, "EPSG:4326", eastings, northings)
    coordinates = [[lon, lat] for lon, lat in zip(longitudes, latitudes, strict=True)]
    aoi = tmp_path / "aoi.geojson"
    aoi.write_text(
        json.dumps({
            "type": "FeatureCollection",
            "features": [{
                "type": "Feature",
                "properties": {"name": "synthetic-test-aoi"},
                "geometry": {"type": "Polygon", "coordinates": [coordinates]},
            }],
        }),
        encoding="utf-8",
    )
    output = tmp_path / "aoi_stack.tif"

    result = prepare_s2_stack(
        metadata_xml=metadata,
        b02_path=bands["B02"],
        b04_path=bands["B04"],
        b08_path=bands["B08"],
        b11_path=bands["B11"],
        b12_path=bands["B12"],
        scl_path=bands["SCL"],
        output_path=output,
        aoi_geojson=aoi,
        max_pixels=100,
    )

    assert result["status"] == "completed"
    manifest = json.loads(Path(result["manifest_path"]).read_text("utf-8"))
    assert manifest["grid"]["width"] == 10
    assert manifest["grid"]["height"] == 10
    assert manifest["grid"]["max_pixels"] == 100
    assert manifest["grid"]["aoi_geojson_sha256"] == hashlib.sha256(aoi.read_bytes()).hexdigest()

    with rasterio.open(output) as stack:
        assert (stack.width, stack.height) == (10, 10)
        b02 = stack.read(1)
        scl = stack.read(6)
        assert np.count_nonzero(b02 == 0) > 0
        assert np.count_nonzero(b02 > 0) > 0
        assert np.count_nonzero(scl == 0) > 0
        assert np.count_nonzero(scl == 4) > 0
        assert stack.tags()["AOI_GEOJSON_SHA256"] == manifest["grid"]["aoi_geojson_sha256"]


def test_refuses_scene_exceeding_pixel_limit_without_aoi(tmp_path: Path) -> None:
    metadata = _write_product_metadata(tmp_path / "MTD_MSIL2A.xml")
    bands = _make_source_bands(tmp_path)
    with pytest.raises(ValueError, match="exceeding the configured limit"):
        prepare_s2_stack(
            metadata_xml=metadata,
            b02_path=bands["B02"],
            b04_path=bands["B04"],
            b08_path=bands["B08"],
            b11_path=bands["B11"],
            b12_path=bands["B12"],
            scl_path=bands["SCL"],
            output_path=tmp_path / "over-limit-stack.tif",
            max_pixels=100,
        )
