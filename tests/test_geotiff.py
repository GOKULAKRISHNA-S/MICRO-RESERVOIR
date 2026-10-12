"""Tests for GeoTIFF reading, metadata validation, grid compatibility, and path security.

NOTE: All rasters generated in these tests are small synthetic fixtures created solely
for automated unit testing. They are not real satellite observations.
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Tuple
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin

from src.microreservoir.exceptions import (
    CorruptRasterError,
    IncompatibleGridError,
    InvalidDateError,
    MissingBandError,
    MissingCRSError,
    NoDataError,
    PathTraversalError,
    RasterReadError,
    TemporalOrderError,
    UnsupportedRasterError,
)
from src.microreservoir.geotiff import (
    load_geotiff_observation,
    read_geotiff_metadata,
    validate_grid_compatibility,
    validate_observation_date,
    validate_safe_path,
    validate_temporal_order,
)
from src.microreservoir.schemas import Observation, ObservationMetadata


# -----------------------------------------------------------------------------
# Synthetic Raster Fixture Helpers
# -----------------------------------------------------------------------------
def create_synthetic_geotiff(
    path: Path,
    shape: Tuple[int, int] = (20, 20),
    count: int = 1,
    crs: Optional[str] = "EPSG:32643",
    res: float = 10.0,
    origin: Tuple[float, float] = (500000.0, 2000000.0),
    dtype: str = "float32",
    nodata: Optional[float] = None,
    fill_value: float = 0.2,
) -> Path:
    """Create a small synthetic GeoTIFF fixture for testing."""
    height, width = shape
    transform = from_origin(origin[0], origin[1], res, res)
    profile = {
        "driver": "GTiff",
        "height": height,
        "width": width,
        "count": count,
        "dtype": dtype,
        "crs": crs,
        "transform": transform,
        "nodata": nodata,
    }

    data = np.full((count, height, width), fill_value, dtype=dtype)
    path.parent.mkdir(parents=True, exist_ok=True)
    with rasterio.open(path, "w", **profile) as dst:
        dst.write(data)

    return path


# -----------------------------------------------------------------------------
# Path Security Tests
# -----------------------------------------------------------------------------
def test_validate_safe_path_valid(tmp_path: Path):
    """Verify that a valid local path within base_dir resolves safely."""
    f = tmp_path / "test.tif"
    f.touch()
    resolved = validate_safe_path(f, base_dir=tmp_path, must_exist=True)
    assert resolved == f.resolve()


def test_validate_safe_path_null_byte():
    """Verify that paths containing null bytes are rejected."""
    with pytest.raises(PathTraversalError, match="null byte detected"):
        validate_safe_path("path/with\0/null.tif", must_exist=False)


def test_validate_safe_path_traversal(tmp_path: Path):
    """Verify that path traversal escaping base directory is blocked."""
    base = tmp_path / "safe_dir"
    base.mkdir()
    outside_file = tmp_path / "secret.txt"
    outside_file.touch()

    # Attempt to access outside_file using traversal relative to base
    traversal_path = base / ".." / "secret.txt"
    with pytest.raises(PathTraversalError, match="escapes base directory"):
        validate_safe_path(traversal_path, base_dir=base, must_exist=False)


def test_validate_safe_path_missing_file(tmp_path: Path):
    """Verify that non-existent files raise FileNotFoundError when must_exist=True."""
    missing = tmp_path / "does_not_exist.tif"
    with pytest.raises(FileNotFoundError, match="not found"):
        validate_safe_path(missing, must_exist=True)


def test_validate_safe_path_directory_target(tmp_path: Path):
    """Verify that pointing to a directory instead of a file raises RasterReadError."""
    dir_path = tmp_path / "some_dir"
    dir_path.mkdir()
    with pytest.raises(RasterReadError, match="not a file"):
        validate_safe_path(dir_path, must_exist=True)


# -----------------------------------------------------------------------------
# Metadata Extraction Tests
# -----------------------------------------------------------------------------
def test_read_geotiff_metadata_success(tmp_path: Path):
    """Verify extraction of dimensions, CRS, affine transform, and resolution."""
    tif_path = tmp_path / "synthetic_b03.tif"
    create_synthetic_geotiff(tif_path, shape=(30, 40), res=10.0, nodata=-9999.0)

    meta = read_geotiff_metadata(tif_path)

    assert meta["width"] == 40
    assert meta["height"] == 30
    assert meta["count"] == 1
    assert "32643" in meta["crs"]
    assert meta["resolution"] == (10.0, 10.0)
    assert meta["nodata"] == -9999.0
    assert meta["driver"] == "GTiff"


def test_read_geotiff_corrupt_empty_file(tmp_path: Path):
    """Verify that zero-byte files raise CorruptRasterError."""
    empty_file = tmp_path / "empty.tif"
    empty_file.touch()

    with pytest.raises(CorruptRasterError, match="empty"):
        read_geotiff_metadata(empty_file)


def test_read_geotiff_unsupported_format(tmp_path: Path):
    """Verify that non-raster text files raise UnsupportedRasterError or CorruptRasterError."""
    text_file = tmp_path / "not_a_raster.tif"
    text_file.write_text("This is plain text, not a valid TIFF header.", encoding="utf-8")

    with pytest.raises((UnsupportedRasterError, CorruptRasterError)):
        read_geotiff_metadata(text_file)


def test_read_geotiff_missing_crs(tmp_path: Path):
    """Verify that rasters without a CRS raise MissingCRSError."""
    no_crs_path = tmp_path / "no_crs.tif"
    create_synthetic_geotiff(no_crs_path, crs=None)

    with pytest.raises(MissingCRSError, match="lacks a Coordinate Reference System"):
        read_geotiff_metadata(no_crs_path)


# -----------------------------------------------------------------------------
# Input Layouts & Ingestion Tests
# -----------------------------------------------------------------------------
def test_load_geotiff_single_band_layout(tmp_path: Path):
    """Verify Layout 1: Separate single-band files for Sentinel-2 B03 (green) and B08 (nir)."""
    b03 = tmp_path / "S2_B03_green.tif"
    b08 = tmp_path / "S2_B08_nir.tif"
    create_synthetic_geotiff(b03, shape=(20, 20), fill_value=0.25)
    create_synthetic_geotiff(b08, shape=(20, 20), fill_value=0.05)

    obs = load_geotiff_observation(
        scene_id="S2A_TEST_01",
        date_str="2024-03-15",
        band_files={"green": b03, "nir": b08},
    )

    assert obs.metadata.scene_id == "S2A_TEST_01"
    assert obs.metadata.date == "2024-03-15"
    assert "green" in obs.bands
    assert "nir" in obs.bands
    assert obs.bands["green"].shape == (20, 20)
    assert obs.valid_mask is not None
    assert obs.valid_mask.all()  # All pixels valid
    # No cloud mask supplied -> cloud_assessed must be False and cloud_cover None
    assert obs.metadata.cloud_assessed is False
    assert obs.metadata.cloud_cover_percent is None


def test_load_geotiff_single_band_missing_required_band(tmp_path: Path):
    """Verify that omitting green or nir in single-band layout raises MissingBandError."""
    b03 = tmp_path / "S2_B03.tif"
    create_synthetic_geotiff(b03)

    with pytest.raises(MissingBandError, match="Missing required core spectral bands"):
        load_geotiff_observation(
            scene_id="S2A_TEST_02",
            date_str="2024-03-15",
            band_files={"green": b03},  # Missing 'nir'
        )


def test_load_geotiff_multiband_layout(tmp_path: Path):
    """Verify Layout 2: Multiband raster with explicit band mapping."""
    multi_path = tmp_path / "multiband_scene.tif"
    create_synthetic_geotiff(multi_path, shape=(25, 25), count=3, fill_value=0.3)

    obs = load_geotiff_observation(
        scene_id="S2A_MULTI_01",
        date_str="2024-03-15",
        multiband_file=multi_path,
        band_mapping={"green": 1, "nir": 2, "red": 3},
    )

    assert "green" in obs.bands
    assert "nir" in obs.bands
    assert "red" in obs.bands
    assert obs.bands["green"].shape == (25, 25)


def test_load_geotiff_multiband_missing_mapping(tmp_path: Path):
    """Verify that multiband rasters without band_mapping are rejected."""
    multi_path = tmp_path / "multi_no_map.tif"
    create_synthetic_geotiff(multi_path, count=2)

    with pytest.raises(MissingBandError, match="explicit 'band_mapping' dictionary"):
        load_geotiff_observation(
            scene_id="S2A_MULTI_02",
            date_str="2024-03-15",
            multiband_file=multi_path,
            band_mapping=None,  # Forbidden: never assume band index mapping
        )


def test_load_geotiff_multiband_invalid_index(tmp_path: Path):
    """Verify that specifying out-of-range band indices raises MissingBandError."""
    multi_path = tmp_path / "multi_2band.tif"
    create_synthetic_geotiff(multi_path, count=2)

    with pytest.raises(MissingBandError, match="Invalid band index 4"):
        load_geotiff_observation(
            scene_id="S2A_MULTI_03",
            date_str="2024-03-15",
            multiband_file=multi_path,
            band_mapping={"green": 1, "nir": 4},  # Index 4 out of range (only 2 bands)
        )


def test_load_geotiff_ambiguous_layout():
    """Verify that supplying both or neither layout options raises ValueError."""
    with pytest.raises(ValueError, match="Must provide either"):
        load_geotiff_observation(scene_id="S2", date_str="2024-01-01")

    with pytest.raises(ValueError, match="Cannot specify both"):
        load_geotiff_observation(
            scene_id="S2",
            date_str="2024-01-01",
            band_files={"green": "a.tif", "nir": "b.tif"},
            multiband_file="c.tif",
            band_mapping={"green": 1, "nir": 2},
        )


# -----------------------------------------------------------------------------
# NoData & Validity Mask Tests
# -----------------------------------------------------------------------------
def test_validity_mask_preserves_nodata(tmp_path: Path):
    """Verify that NoData pixels are correctly marked False in valid_mask."""
    b03 = tmp_path / "nodata_b03.tif"
    b08 = tmp_path / "nodata_b08.tif"
    create_synthetic_geotiff(b03, shape=(10, 10), nodata=-9999.0, fill_value=0.2)
    create_synthetic_geotiff(b08, shape=(10, 10), nodata=-9999.0, fill_value=0.05)

    # Set top-left pixel to NoData (-9999.0) in green band
    with rasterio.open(b03, "r+") as dst:
        arr = dst.read(1)
        arr[0, 0] = -9999.0
        dst.write(arr, 1)

    obs = load_geotiff_observation(
        scene_id="S2_NODATA",
        date_str="2024-02-01",
        band_files={"green": b03, "nir": b08},
    )

    assert obs.valid_mask is not None
    assert obs.valid_mask[0, 0] == False
    assert obs.valid_mask[1, 1] == True
    assert np.sum(obs.valid_mask) == 99


def test_all_invalid_observation_raises_nodata_error(tmp_path: Path):
    """Verify that a 100% NoData raster raises NoDataError."""
    b03 = tmp_path / "all_nodata_b03.tif"
    b08 = tmp_path / "all_nodata_b08.tif"
    create_synthetic_geotiff(b03, shape=(10, 10), nodata=0.0, fill_value=0.0)
    create_synthetic_geotiff(b08, shape=(10, 10), nodata=0.0, fill_value=0.0)

    with pytest.raises(NoDataError, match="contains no valid pixels"):
        load_geotiff_observation(
            scene_id="S2_EMPTY",
            date_str="2024-02-01",
            band_files={"green": b03, "nir": b08},
        )


# -----------------------------------------------------------------------------
# External Cloud Mask & Uncertainty Tests
# -----------------------------------------------------------------------------
def test_external_cloud_mask_application(tmp_path: Path):
    """Verify that external cloud masks exclude cloud pixels and compute cloud percentage."""
    b03 = tmp_path / "cloud_b03.tif"
    b08 = tmp_path / "cloud_b08.tif"
    cloud_f = tmp_path / "cloud_mask.tif"
    create_synthetic_geotiff(b03, shape=(20, 20), fill_value=0.2)
    create_synthetic_geotiff(b08, shape=(20, 20), fill_value=0.05)

    # Create cloud mask with 40 pixels set to 1 (clouds), rest 0 (clear)
    create_synthetic_geotiff(cloud_f, shape=(20, 20), fill_value=0, dtype="uint8")
    with rasterio.open(cloud_f, "r+") as dst:
        c_arr = dst.read(1)
        c_arr[:2, :] = 1  # 2 rows x 20 cols = 40 pixels (10% of 400)
        dst.write(c_arr, 1)

    obs = load_geotiff_observation(
        scene_id="S2_CLOUD",
        date_str="2024-02-01",
        band_files={"green": b03, "nir": b08},
        cloud_mask_file=cloud_f,
    )

    assert obs.metadata.cloud_assessed is True
    assert pytest.approx(obs.metadata.cloud_cover_percent, 0.1) == 10.0
    assert obs.valid_mask is not None
    assert obs.valid_mask[:2, :].all() == False  # Clouds masked out
    assert obs.valid_mask[2:, :].all() == True   # Clear pixels valid
    assert np.sum(obs.valid_mask) == 360


def test_cloud_mask_dimension_mismatch(tmp_path: Path):
    """Verify that cloud mask with mismatched dimensions raises IncompatibleGridError."""
    b03 = tmp_path / "s_b03.tif"
    b08 = tmp_path / "s_b08.tif"
    cloud_f = tmp_path / "mismatch_cloud.tif"
    create_synthetic_geotiff(b03, shape=(20, 20))
    create_synthetic_geotiff(b08, shape=(20, 20))
    create_synthetic_geotiff(cloud_f, shape=(30, 30))  # Different shape!

    with pytest.raises(IncompatibleGridError, match="Cloud mask shape"):
        load_geotiff_observation(
            scene_id="S2_MISMATCH_CLOUD",
            date_str="2024-02-01",
            band_files={"green": b03, "nir": b08},
            cloud_mask_file=cloud_f,
        )


# -----------------------------------------------------------------------------
# Grid & Study Area Compatibility Tests
# -----------------------------------------------------------------------------
def test_grid_compatibility_crs_mismatch():
    """Verify that observations with differing CRS projections are rejected."""
    m1 = ObservationMetadata(scene_id="O1", date="2024-01-01", crs="EPSG:32643")
    m2 = ObservationMetadata(scene_id="O2", date="2024-02-01", crs="EPSG:32644")  # Zone 44 != Zone 43
    obs1 = Observation(metadata=m1, bands={"green": np.zeros((10, 10))})
    obs2 = Observation(metadata=m2, bands={"green": np.zeros((10, 10))})

    with pytest.raises(IncompatibleGridError, match="Coordinate Reference System mismatch"):
        validate_grid_compatibility(obs1, obs2)


def test_grid_compatibility_dimension_mismatch():
    """Verify that observations with differing array shapes are rejected."""
    m1 = ObservationMetadata(scene_id="O1", date="2024-01-01", crs="EPSG:32643")
    m2 = ObservationMetadata(scene_id="O2", date="2024-02-01", crs="EPSG:32643")
    obs1 = Observation(metadata=m1, bands={"green": np.zeros((20, 20))})
    obs2 = Observation(metadata=m2, bands={"green": np.zeros((30, 30))})

    with pytest.raises(IncompatibleGridError, match="Spatial raster dimension mismatch"):
        validate_grid_compatibility(obs1, obs2)


def test_grid_compatibility_transform_mismatch():
    """Verify that unaligned grid origins/transforms are rejected."""
    t1 = (10.0, 0.0, 500000.0, 0.0, -10.0, 2000000.0)
    t2 = (10.0, 0.0, 500005.0, 0.0, -10.0, 2000000.0)  # Shifted by 5 meters!
    m1 = ObservationMetadata(scene_id="O1", date="2024-01-01", transform=t1)
    m2 = ObservationMetadata(scene_id="O2", date="2024-02-01", transform=t2)
    obs1 = Observation(metadata=m1, bands={"green": np.zeros((10, 10))})
    obs2 = Observation(metadata=m2, bands={"green": np.zeros((10, 10))})

    with pytest.raises(IncompatibleGridError, match="Affine transform grid mismatch"):
        validate_grid_compatibility(obs1, obs2)


# -----------------------------------------------------------------------------
# Date & Temporal Order Tests
# -----------------------------------------------------------------------------
def test_validate_observation_date_valid():
    """Verify valid ISO-8601 calendar date parsing."""
    d = validate_observation_date("2024-03-15")
    assert d.year == 2024
    assert d.month == 3
    assert d.day == 15


@pytest.mark.parametrize(
    "invalid_date",
    ["", "2024/03/15", "15-03-2024", "2024-02-30", "2024-13-01", "not-a-date"],
)
def test_validate_observation_date_invalid(invalid_date: str):
    """Verify that malformed or non-existent dates raise InvalidDateError."""
    with pytest.raises(InvalidDateError):
        validate_observation_date(invalid_date)


def test_validate_temporal_order_valid():
    """Verify baseline date preceding follow-up date passes."""
    validate_temporal_order("2023-10-15", "2024-03-15")


def test_validate_temporal_order_reversed():
    """Verify that reversed dates raise TemporalOrderError."""
    with pytest.raises(TemporalOrderError, match="must strictly precede"):
        validate_temporal_order("2024-03-15", "2023-10-15")


def test_validate_temporal_order_equal():
    """Verify that identical dates raise TemporalOrderError."""
    with pytest.raises(TemporalOrderError, match="must strictly precede"):
        validate_temporal_order("2024-01-01", "2024-01-01")


# -----------------------------------------------------------------------------
# Pixel Processing Limit Tests
# -----------------------------------------------------------------------------
def test_read_geotiff_metadata_exceeds_max_pixels(tmp_path):
    """Verify that rasters exceeding max_pixels raise RasterReadError."""
    tif_path = tmp_path / "test_limit.tif"
    create_synthetic_geotiff(tif_path, shape=(20, 20))  # 400 pixels

    # Set limit to 200 pixels -> should raise RasterReadError
    with pytest.raises(RasterReadError, match="exceeds the safety processing limit"):
        read_geotiff_metadata(tif_path, max_pixels=200)

    # Set limit to 500 pixels -> should succeed
    meta = read_geotiff_metadata(tif_path, max_pixels=500)
    assert meta["width"] == 20
    assert meta["height"] == 20


def test_load_geotiff_observation_exceeds_max_pixels(tmp_path):
    """Verify that load_geotiff_observation enforces the pixel safety limit."""
    g_path = tmp_path / "green.tif"
    n_path = tmp_path / "nir.tif"
    create_synthetic_geotiff(g_path, shape=(20, 20), fill_value=0.3)
    create_synthetic_geotiff(n_path, shape=(20, 20), fill_value=0.1)

    with pytest.raises(RasterReadError, match="exceeds the safety processing limit"):
        load_geotiff_observation(
            scene_id="TEST_LIMIT",
            date_str="2024-03-15",
            band_files={"green": g_path, "nir": n_path},
            max_pixels=300,
        )

