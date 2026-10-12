"""Exhaustive unit tests for Phase 3 spectral water extraction and NDWI calculation.

NOTE: All test rasters and arrays generated here are small synthetic fixtures created
solely for automated algorithm verification. They are not real satellite observations.
"""

from __future__ import annotations

import numpy as np
import pytest

from config import DEFAULT_CONFIG, AppConfig
from src.microreservoir.schemas import Observation, ObservationMetadata, WaterIndexMethod
from src.microreservoir.water_detection import (
    HEURISTIC_CAVEAT_WARNING,
    compute_awei,
    compute_mndwi,
    compute_ndwi,
    detect_water,
)


# -----------------------------------------------------------------------------
# 1. Arithmetic & Known Input Tests
# -----------------------------------------------------------------------------
def test_compute_ndwi_known_arithmetic():
    """Verify exact NDWI arithmetic against manually calculated values."""
    # (0.4 - 0.2) / (0.4 + 0.2) = 0.2 / 0.6 = 0.333333...
    green = np.array([[0.4, 0.1]], dtype=np.float32)
    nir = np.array([[0.2, 0.5]], dtype=np.float32)

    ndwi = compute_ndwi(green, nir)

    assert pytest.approx(ndwi[0, 0], 1e-4) == 0.333333
    # (0.1 - 0.5) / (0.1 + 0.5) = -0.4 / 0.6 = -0.666667...
    assert pytest.approx(ndwi[0, 1], 1e-4) == -0.666667


def test_compute_ndwi_positive_negative_signs():
    """Verify that Green > NIR yields positive NDWI and Green < NIR yields negative NDWI."""
    green = np.array([[0.5, 0.1, 0.3]], dtype=np.float32)
    nir = np.array([[0.1, 0.5, 0.3]], dtype=np.float32)

    ndwi = compute_ndwi(green, nir)

    assert ndwi[0, 0] > 0.0  # Clear water signal
    assert ndwi[0, 1] < 0.0  # Clear land/vegetation signal
    assert pytest.approx(ndwi[0, 2], 1e-4) == 0.0  # Neutral balance


# -----------------------------------------------------------------------------
# 2. Denominator Boundary & Zero Division Tests
# -----------------------------------------------------------------------------
def test_compute_ndwi_zero_and_near_zero_denominators():
    """Verify safe vectorized handling when denominator is zero or near-zero."""
    # (0.0, 0.0) has denominator 0.0
    # (1e-8, 1e-8) has denominator 2e-8 < eps (1e-7)
    green = np.array([[0.0, 1e-8], [0.2, 0.0]], dtype=np.float32)
    nir = np.array([[0.0, 1e-8], [0.1, 0.0]], dtype=np.float32)

    ndwi = compute_ndwi(green, nir, eps=1e-7)

    # Denominators <= eps evaluate safely to 0.0 without division errors or NaN
    assert not np.isnan(ndwi[0, 0])
    assert not np.isinf(ndwi[0, 0])
    assert ndwi[0, 0] == 0.0
    assert ndwi[0, 1] == 0.0
    # Normal pixel is computed correctly: (0.2 - 0.1) / (0.2 + 0.1) = 0.1 / 0.3 = 0.3333
    assert pytest.approx(ndwi[1, 0], 1e-4) == 0.333333


# -----------------------------------------------------------------------------
# 3. NaN & Infinite Input Handling Tests
# -----------------------------------------------------------------------------
def test_compute_ndwi_nan_and_infinite_sanitization():
    """Verify that NaN and Infinite inputs are sanitized without crashing."""
    green = np.array([[np.nan, 0.3], [np.inf, -np.inf]], dtype=np.float32)
    nir = np.array([[0.1, np.nan], [0.2, 0.2]], dtype=np.float32)

    ndwi = compute_ndwi(green, nir)

    # All outputs must be finite float32 bounded in [-1.0, 1.0]
    assert np.all(np.isfinite(ndwi))
    assert np.all(ndwi >= -1.0)
    assert np.all(ndwi <= 1.0)
    # Corrupt/NaN positions are set to invalid fill (-1.0)
    assert ndwi[0, 0] == -1.0
    assert ndwi[0, 1] == -1.0


# -----------------------------------------------------------------------------
# 4. Incompatible Shape Error Handling
# -----------------------------------------------------------------------------
def test_compute_ndwi_shape_mismatch():
    """Verify that mismatched array shapes raise ValueError."""
    g = np.zeros((10, 10), dtype=np.float32)
    n = np.zeros((10, 15), dtype=np.float32)

    with pytest.raises(ValueError, match="Incompatible array shapes"):
        compute_ndwi(g, n)


def test_compute_ndwi_non_2d_arrays():
    """Verify that non-2D arrays raise ValueError."""
    g = np.zeros((10,), dtype=np.float32)
    n = np.zeros((10,), dtype=np.float32)

    with pytest.raises(ValueError, match="must be 2-dimensional"):
        compute_ndwi(g, n)


# -----------------------------------------------------------------------------
# 5. Threshold Boundary Behavior Tests
# -----------------------------------------------------------------------------
def test_detect_water_threshold_boundary():
    """Verify strict inequality (> threshold) boundary behavior."""
    # Create 3 pixels:
    # 1. NDWI = +0.2 (> 0.0 -> True)
    # 2. NDWI = 0.0 (== 0.0 -> False, boundary)
    # 3. NDWI = -0.2 (< 0.0 -> False)
    green = np.array([[0.3, 0.2, 0.2]], dtype=np.float32)
    nir = np.array([[0.2, 0.2, 0.3]], dtype=np.float32)

    meta = ObservationMetadata(scene_id="SYNTH_BOUNDARY", date="2024-01-01")
    obs = Observation(metadata=meta, bands={"green": green, "nir": nir})

    res = detect_water(obs, method=WaterIndexMethod.NDWI, threshold=0.0)

    # Pixel 0 is water, pixel 1 (equal to threshold) is NOT water, pixel 2 is NOT water
    assert res.water_mask[0, 0] == True
    assert res.water_mask[0, 1] == False
    assert res.water_mask[0, 2] == False
    assert res.water_pixel_count == 1


def test_detect_water_custom_threshold_from_config():
    """Verify that configurable threshold from config.py is respected."""
    green = np.array([[0.25, 0.22]], dtype=np.float32)
    nir = np.array([[0.20, 0.20]], dtype=np.float32)

    meta = ObservationMetadata(scene_id="SYNTH_THRESH", date="2024-01-01")
    obs = Observation(metadata=meta, bands={"green": green, "nir": nir})

    # At threshold=0.0, both pixels have Green > NIR (NDWI > 0) -> 2 water pixels
    res_default = detect_water(obs, threshold=0.0)
    assert res_default.water_pixel_count == 2

    # At threshold=0.10, pixel 0 has NDWI=(0.05/0.45)=0.111 (>0.10), pixel 1 has NDWI=(0.02/0.42)=0.047 (<0.10)
    res_high = detect_water(obs, threshold=0.10)
    assert res_high.water_pixel_count == 1
    assert res_high.water_mask[0, 0] == True
    assert res_high.water_mask[0, 1] == False


# -----------------------------------------------------------------------------
# 6. NoData & Validity Mask Preservation Tests
# -----------------------------------------------------------------------------
def test_detect_water_preserves_and_applies_valid_mask():
    """Verify that pixels flagged False in valid_mask are excluded from water mask."""
    h, w = 10, 10
    green = np.full((h, w), 0.3, dtype=np.float32)
    nir = np.full((h, w), 0.05, dtype=np.float32)  # High water signal across all 100 pixels

    valid_mask = np.ones((h, w), dtype=bool)
    valid_mask[0, 0] = False  # Explicitly mask top-left pixel as invalid

    meta = ObservationMetadata(scene_id="SYNTH_MASK", date="2024-01-01")
    obs = Observation(metadata=meta, bands={"green": green, "nir": nir}, valid_mask=valid_mask)

    res = detect_water(obs, threshold=0.0)

    assert res.water_mask[0, 0] == False
    assert res.valid_mask is not None
    assert res.valid_mask[0, 0] == False
    assert res.water_pixel_count == 99
    assert res.total_valid_pixels == 99


def test_detect_water_excludes_nan_pixels():
    """Verify that NaN pixels are excluded from valid_mask and water_mask."""
    green = np.array([[np.nan, 0.4], [0.1, 0.3]], dtype=np.float32)
    nir = np.array([[0.1, 0.1], [0.3, 0.1]], dtype=np.float32)

    meta = ObservationMetadata(scene_id="SYNTH_NAN", date="2024-01-01")
    obs = Observation(metadata=meta, bands={"green": green, "nir": nir})

    res = detect_water(obs, threshold=0.0)

    # Pixel (0,0) is NaN -> not valid, not water
    assert res.valid_mask is not None
    assert res.valid_mask[0, 0] == False
    assert res.water_mask[0, 0] == False
    assert res.total_valid_pixels == 3
    assert res.water_pixel_count == 2  # (0,1) and (1,1) have Green > NIR


# -----------------------------------------------------------------------------
# 7. Summary Statistics, Properties & Caveat Warnings
# -----------------------------------------------------------------------------
def test_detect_water_summary_statistics_and_warnings():
    """Verify that WaterDetectionResult contains statistics, properties, and caveat warnings."""
    green = np.array([[0.3, 0.1], [0.2, 0.4]], dtype=np.float32)
    nir = np.array([[0.1, 0.3], [0.2, 0.1]], dtype=np.float32)

    meta = ObservationMetadata(scene_id="SYNTH_STATS", date="2024-01-01")
    obs = Observation(metadata=meta, bands={"green": green, "nir": nir})

    res = detect_water(obs, threshold=0.0)

    # Check properties
    assert isinstance(res.ndwi_map, np.ndarray)
    assert isinstance(res.valid_pixel_mask, np.ndarray)
    assert res.ndwi_map is res.index_map
    assert res.valid_pixel_mask is res.valid_mask

    # Check statistics dictionary
    stats = res.summary_statistics
    assert stats["total_pixels"] == 4.0
    assert stats["valid_pixels"] == 4.0
    assert stats["water_pixels"] == 2.0  # Pixels (0,0) and (1,1) have Green > NIR
    assert pytest.approx(stats["water_fraction"], 1e-4) == 0.50
    assert "ndwi_min" in stats
    assert "ndwi_max" in stats
    assert "ndwi_mean" in stats
    assert "ndwi_std" in stats

    # Check heuristic warning
    assert any("NDWI is an empirical spectral ratio heuristic" in w for w in res.warnings)


# -----------------------------------------------------------------------------
# 8. Deterministic Repeatability
# -----------------------------------------------------------------------------
def test_detect_water_repeatability():
    """Verify that detect_water produces bitwise-identical results for identical inputs."""
    green = np.random.default_rng(42).uniform(0.05, 0.5, (25, 25)).astype(np.float32)
    nir = np.random.default_rng(43).uniform(0.05, 0.5, (25, 25)).astype(np.float32)

    meta = ObservationMetadata(scene_id="SYNTH_REPEAT", date="2024-01-01")
    obs1 = Observation(metadata=meta, bands={"green": green.copy(), "nir": nir.copy()})
    obs2 = Observation(metadata=meta, bands={"green": green.copy(), "nir": nir.copy()})

    res1 = detect_water(obs1, threshold=0.0)
    res2 = detect_water(obs2, threshold=0.0)

    assert np.array_equal(res1.water_mask, res2.water_mask)
    assert np.array_equal(res1.index_map, res2.index_map)
    assert res1.water_pixel_count == res2.water_pixel_count
    assert res1.summary_statistics == res2.summary_statistics


# -----------------------------------------------------------------------------
# 9. Validation Enforcement Integration
# -----------------------------------------------------------------------------
def test_detect_water_rejects_invalid_observation():
    """Verify that an observation with mismatched shapes fails validation and raises ValueError."""
    meta = ObservationMetadata(scene_id="SYNTH_INVALID", date="2024-01-01")
    # Incompatible band shapes (10x10 vs 10x15)
    obs = Observation(
        metadata=meta,
        bands={"green": np.zeros((10, 10)), "nir": np.zeros((10, 15))},
    )

    with pytest.raises(ValueError, match="Cannot perform water detection on invalid observation"):
        detect_water(obs)


# -----------------------------------------------------------------------------
# 10. End-to-End GeoTIFF Ingestion to NDWI Integration Test
# -----------------------------------------------------------------------------
def test_integration_geotiff_to_ndwi_water_mask(tmp_path: pytest.TempPathFactory):
    """Integration test: Local GeoTIFF files -> load_geotiff_observation -> detect_water."""
    from pathlib import Path
    import rasterio
    from src.microreservoir.geotiff import load_geotiff_observation
    from tests.test_geotiff import create_synthetic_geotiff

    b03_path = Path(tmp_path) / "int_b03.tif"
    b08_path = Path(tmp_path) / "int_b08.tif"

    # Create synthetic single-band GeoTIFFs (20x20)
    # Background is land (Green=0.10, NIR=0.45 -> NDWI < -0.5)
    create_synthetic_geotiff(b03_path, shape=(20, 20), fill_value=0.10)
    create_synthetic_geotiff(b08_path, shape=(20, 20), fill_value=0.45)

    # Central 10x10 block is water (Green=0.35, NIR=0.05 -> NDWI > +0.7)
    with rasterio.open(b03_path, "r+") as dst:
        g_arr = dst.read(1)
        g_arr[5:15, 5:15] = 0.35
        dst.write(g_arr, 1)

    with rasterio.open(b08_path, "r+") as dst:
        n_arr = dst.read(1)
        n_arr[5:15, 5:15] = 0.05
        dst.write(n_arr, 1)

    # Ingest using Phase 2 loader
    obs = load_geotiff_observation(
        scene_id="INT_TEST_S2A",
        date_str="2024-03-15",
        band_files={"green": b03_path, "nir": b08_path},
    )

    # Execute Phase 3 water detection
    result = detect_water(obs, method=WaterIndexMethod.NDWI, threshold=0.0)

    # Assert outputs
    assert result.water_pixel_count == 100
    assert result.total_valid_pixels == 400
    assert pytest.approx(result.water_fraction, 1e-4) == 0.25
    assert result.water_mask[10, 10] == True
    assert result.water_mask[0, 0] == False
    assert result.index_map[10, 10] > 0.6
    assert result.index_map[0, 0] < -0.5
    assert result.valid_mask is not None
    assert result.valid_mask.all() == True
    assert result.summary_statistics["water_pixels"] == 100.0
    assert "ndwi_mean" in result.summary_statistics
