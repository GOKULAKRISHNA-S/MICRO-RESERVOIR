"""Unit tests for surface area calculation, geospatial projections, and uncertainty bounds.

Synthetic benchmarks are strictly labelled as synthetic test data.
"""

from __future__ import annotations

import numpy as np
import pytest
import rasterio

from src.microreservoir.area_estimation import estimate_area
from src.microreservoir.schemas import (
    Observation,
    ObservationMetadata,
    WaterDetectionResult,
    WaterIndexMethod,
)


def test_estimate_area_100_pixels_10m():
    """Verify exact requirement: 100 water pixels × 100 m² per pixel = 10,000 m² (1.0 ha)."""
    # Synthetic 10x10 grid with 100 water pixels
    det = WaterDetectionResult(
        water_mask=np.ones((10, 10), dtype=bool),
        index_map=np.ones((10, 10), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=100,
        total_valid_pixels=100,
        water_fraction=1.0,
    )

    area = estimate_area(det, pixel_resolution_m=10.0, crs="EPSG:32643")

    assert area.is_available is True
    assert area.pixel_count == 100
    assert area.pixel_resolution_m == 10.0
    assert area.pixel_area_m2 == 100.0
    assert pytest.approx(area.water_area_m2, 1e-2) == 10000.0
    assert pytest.approx(area.water_area_hectares, 1e-4) == 1.0
    assert pytest.approx(area.water_area_acres, 1e-3) == 2.471
    # Check uncertainty bounds
    assert area.uncertainty_range_hectares[0] < area.water_area_hectares
    assert area.uncertainty_range_hectares[1] > area.water_area_hectares


def test_estimate_area_does_not_assume_10m_resolution():
    """Verify that arbitrary pixel resolutions (e.g. 20m, 30m) calculate correct ground area."""
    # 50 pixels at 20m resolution -> 50 * (20*20 m²) = 50 * 400 m² = 20,000 m² = 2.0 ha
    det = WaterDetectionResult(
        water_mask=np.ones((10, 5), dtype=bool),
        index_map=np.ones((10, 5), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=50,
        total_valid_pixels=50,
        water_fraction=1.0,
    )

    area_20m = estimate_area(det, pixel_resolution_m=20.0, crs="EPSG:32643")
    assert area_20m.pixel_area_m2 == 400.0
    assert pytest.approx(area_20m.water_area_m2, 1e-2) == 20000.0
    assert pytest.approx(area_20m.water_area_hectares, 1e-4) == 2.0

    # 10 pixels at 30m resolution (Landsat-like) -> 10 * 900 m² = 9,000 m² = 0.9 ha
    det_30m = WaterDetectionResult(
        water_mask=np.ones((5, 2), dtype=bool),
        index_map=np.ones((5, 2), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=10,
        total_valid_pixels=10,
        water_fraction=1.0,
    )
    area_30m = estimate_area(det_30m, pixel_resolution_m=30.0, crs="EPSG:32643")
    assert area_30m.pixel_area_m2 == 900.0
    assert pytest.approx(area_30m.water_area_m2, 1e-2) == 9000.0
    assert pytest.approx(area_30m.water_area_hectares, 1e-4) == 0.9


def test_estimate_area_with_affine_transform():
    """Verify pixel ground area calculation directly from affine transform determinant."""
    # Affine transform with 15m x 15m ground scale and north-up orientation
    # (15.0, 0.0, 500000.0, 0.0, -15.0, 2000000.0)
    transform = (15.0, 0.0, 500000.0, 0.0, -15.0, 2000000.0)
    det = WaterDetectionResult(
        water_mask=np.ones((4, 5), dtype=bool),
        index_map=np.ones((4, 5), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=20,
        total_valid_pixels=20,
        water_fraction=1.0,
    )

    area = estimate_area(det, transform=transform, crs="EPSG:32643")
    # Determinant = abs(15.0 * (-15.0) - 0.0) = 225.0 m²
    assert pytest.approx(area.pixel_area_m2, 1e-2) == 225.0
    # 20 pixels * 225.0 m² = 4,500 m² = 0.45 ha
    assert pytest.approx(area.water_area_m2, 1e-2) == 4500.0
    assert pytest.approx(area.water_area_hectares, 1e-4) == 0.45


def test_estimate_area_geographic_crs_reported_unavailable():
    """Verify that geographic/unprojected CRS (EPSG:4326) reports area as unavailable."""
    det = WaterDetectionResult(
        water_mask=np.ones((10, 10), dtype=bool),
        index_map=np.ones((10, 10), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=100,
        total_valid_pixels=100,
        water_fraction=1.0,
    )

    area = estimate_area(det, pixel_resolution_m=0.0001, crs="EPSG:4326")

    assert area.is_available is False
    assert area.water_area_m2 == 0.0
    assert area.water_area_hectares == 0.0
    assert area.pixel_count == 100
    assert any("Geographic CRS" in w for w in area.warnings)


def test_estimate_area_geographic_crs_rejection():
    """Verify that reject_unsuitable_crs=True raises ValueError for geographic CRS."""
    det = WaterDetectionResult(
        water_mask=np.ones((5, 5), dtype=bool),
        index_map=np.ones((5, 5), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=25,
        total_valid_pixels=25,
        water_fraction=1.0,
    )

    with pytest.raises(ValueError, match="Geographic CRS.*detected"):
        estimate_area(det, pixel_resolution_m=0.0001, crs="EPSG:4326", reject_unsuitable_crs=True)


def test_estimate_area_nodata_exclusion():
    """Verify that NoData/invalid pixels marked as water are excluded from valid pixel count and area."""
    # 4 pixels in water_mask, but only 3 are valid in valid_mask
    water_mask = np.array([[True, True], [True, True]])
    valid_mask = np.array([[True, True], [True, False]])  # pixel (1,1) is NoData/cloud

    det = WaterDetectionResult(
        water_mask=water_mask,
        index_map=np.ones((2, 2), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=4,  # raw count before mask intersection
        total_valid_pixels=3,
        water_fraction=1.0,
        valid_mask=valid_mask,
    )

    area = estimate_area(det, pixel_resolution_m=10.0, crs="EPSG:32643")

    # Only 3 valid water pixels should be counted!
    assert area.pixel_count == 3
    assert pytest.approx(area.water_area_m2, 1e-2) == 300.0
    assert pytest.approx(area.water_area_hectares, 1e-4) == 0.03


def test_estimate_area_zero_pixels():
    """Verify that zero detected water pixels yields 0.0 area and bounds."""
    det = WaterDetectionResult(
        water_mask=np.zeros((10, 10), dtype=bool),
        index_map=np.zeros((10, 10), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=0,
        total_valid_pixels=100,
        water_fraction=0.0,
    )

    area = estimate_area(det, pixel_resolution_m=10.0, crs="EPSG:32643")

    assert area.water_area_m2 == 0.0
    assert area.water_area_hectares == 0.0
    assert area.uncertainty_range_hectares == (0.0, 0.0)


def test_estimate_area_invalid_resolution():
    """Verify that non-positive resolution values raise ValueError."""
    det = WaterDetectionResult(
        water_mask=np.zeros((5, 5), dtype=bool),
        index_map=np.zeros((5, 5), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=10,
        total_valid_pixels=25,
        water_fraction=0.4,
    )

    with pytest.raises(ValueError, match="strictly positive"):
        estimate_area(det, pixel_resolution_m=-5.0)


def test_estimate_area_from_observation():
    """Verify estimate_area extracting resolution, crs, and transform from Observation object."""
    meta = ObservationMetadata(
        scene_id="SYNTH_OBS",
        date="2024-01-01",
        pixel_resolution_m=10.0,
        crs="EPSG:32643",
        transform=(10.0, 0.0, 100.0, 0.0, -10.0, 200.0),
    )
    obs = Observation(metadata=meta, bands={"green": np.ones((5, 5)), "nir": np.ones((5, 5))})

    det = WaterDetectionResult(
        water_mask=np.ones((5, 5), dtype=bool),
        index_map=np.ones((5, 5), dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=25,
        total_valid_pixels=25,
        water_fraction=1.0,
    )

    area = estimate_area(det, observation=obs)
    assert area.is_available is True
    assert area.pixel_count == 25
    assert pytest.approx(area.water_area_m2, 1e-2) == 2500.0
    assert pytest.approx(area.water_area_hectares, 1e-4) == 0.25
    assert area.crs == "EPSG:32643"
