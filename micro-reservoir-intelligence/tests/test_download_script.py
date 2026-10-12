import json
import numpy as np
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch
import rasterio
from rasterio.transform import from_origin

import download_mettur_sentinel2 as dms


def test_no_syntax_warning_in_docstring():
    """Ensure the docstring does not emit invalid escape sequence SyntaxWarning."""
    import warnings
    with warnings.catch_warnings(record=True) as recorded:
        warnings.simplefilter("always", SyntaxWarning)
        import importlib
        importlib.reload(dms)
    syntax_warnings = [w for w in recorded if issubclass(w.category, SyntaxWarning)]
    assert len(syntax_warnings) == 0


def test_bbox_overlap_ratio():
    study = (77.72, 11.74, 77.90, 11.88)
    # Identical box -> 1.0
    assert pytest.approx(dms.bbox_overlap_ratio(list(study), study)) == 1.0
    # No overlap -> 0.0
    assert dms.bbox_overlap_ratio([10.0, 10.0, 11.0, 11.0], study) == 0.0
    # None or invalid -> 0.0
    assert dms.bbox_overlap_ratio(None, study) == 0.0
    assert dms.bbox_overlap_ratio([], study) == 0.0


def test_get_asset():
    item = {
        "id": "test_scene",
        "assets": {
            "green": {"href": "https://example.com/B03.tif"},
            "nir": {"href": "https://example.com/B08.tif"},
            "b8a": {"href": "https://example.com/B8A.tif"},
        }
    }
    k3, h3 = dms.get_asset(item, "B03")
    assert k3 == "green"
    assert h3 == "https://example.com/B03.tif"

    k8, h8 = dms.get_asset(item, "B08")
    assert k8 == "nir"
    assert h8 == "https://example.com/B08.tif"

    # Missing band raises RuntimeError
    empty_item = {"id": "empty", "assets": {}}
    with pytest.raises(RuntimeError, match="Could not identify"):
        dms.get_asset(empty_item, "B03")


def test_choose_pair_prioritizes_study_area_overlap():
    items = [
        # Sliver tile (43PGN) - 2 scenes >= 30 days apart
        {
            "id": "scene_pgn_newer",
            "bbox": [76.82, 10.75, 77.84, 11.754],
            "properties": {
                "datetime": "2026-09-29T00:00:00Z",
                "eo:cloud_cover": 10.0,
                "s2:mgrs_tile": "43PGN",
                "proj:epsg": 32643,
            },
            "assets": {
                "B03": {"href": "https://example.com/pgn_newer_b03.tif"},
                "B08": {"href": "https://example.com/pgn_newer_b08.tif"},
            },
        },
        {
            "id": "scene_pgn_older",
            "bbox": [76.82, 10.75, 77.84, 11.754],
            "properties": {
                "datetime": "2026-08-15T00:00:00Z",
                "eo:cloud_cover": 12.0,
                "s2:mgrs_tile": "43PGN",
                "proj:epsg": 32643,
            },
            "assets": {
                "B03": {"href": "https://example.com/pgn_older_b03.tif"},
                "B08": {"href": "https://example.com/pgn_older_b08.tif"},
            },
        },
        # High-coverage tile (43PHP) - 2 scenes >= 30 days apart
        {
            "id": "scene_php_newer",
            "bbox": [77.75, 11.64, 78.77, 12.65],
            "properties": {
                "datetime": "2026-09-28T00:00:00Z",
                "eo:cloud_cover": 15.0,
                "s2:mgrs_tile": "43PHP",
                "proj:epsg": 32643,
            },
            "assets": {
                "B03": {"href": "https://example.com/php_newer_b03.tif"},
                "B08": {"href": "https://example.com/php_newer_b08.tif"},
            },
        },
        {
            "id": "scene_php_older",
            "bbox": [77.75, 11.64, 78.77, 12.65],
            "properties": {
                "datetime": "2026-08-20T00:00:00Z",
                "eo:cloud_cover": 14.0,
                "s2:mgrs_tile": "43PHP",
                "proj:epsg": 32643,
            },
            "assets": {
                "B03": {"href": "https://example.com/php_older_b03.tif"},
                "B08": {"href": "https://example.com/php_older_b08.tif"},
            },
        },
    ]

    older, newer = dms.choose_pair(items)
    # Must pick the high-coverage 43PHP tile instead of the 43PGN sliver!
    assert dms.item_tile(newer) == "43PHP"
    assert dms.item_tile(older) == "43PHP"
    assert older["id"] == "scene_php_older"
    assert newer["id"] == "scene_php_newer"


def test_validate_downloaded_rasters(tmp_path: Path):
    # Create 4 synthetic GeoTIFFs matching the required format
    crs = rasterio.crs.CRS.from_epsg(32643)
    transform = from_origin(800000.0, 1315000.0, 10.0, 10.0)
    records = []

    files_info = [
        ("date1", "2026-08-30", "B03"),
        ("date1", "2026-08-30", "B08"),
        ("date2", "2026-09-29", "B03"),
        ("date2", "2026-09-29", "B08"),
    ]

    for label, dt, band in files_info:
        file_path = tmp_path / f"{label}_{dt}_{band}.tif"
        data = np.ones((50, 50), dtype=np.uint16) * 1500
        mask = np.ones((50, 50), dtype=np.uint8) * 255
        with rasterio.open(
            file_path,
            "w",
            driver="GTiff",
            height=50,
            width=50,
            count=1,
            dtype="uint16",
            crs=crs,
            transform=transform,
            nodata=0,
        ) as dst:
            dst.write(data, 1)
            dst.write_mask(mask)

        records.append({
            "path": str(file_path),
            "band": band,
            "acquisition_datetime": f"{dt}T05:25:00Z",
            "crs": str(crs),
            "width": 50,
            "height": 50,
            "transform": list(transform)[:6],
        })

    # Validation should pass without error
    dms.validate_downloaded_rasters(records)
