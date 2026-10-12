"""Unit tests for multi-temporal change detection, status classification, and numerical accuracy.

Synthetic values are used for unit verification and strictly labelled as synthetic test data.
"""

from __future__ import annotations

import numpy as np
import pytest

from config import (
    DEFAULT_CONFIG,
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_COMPARISON,
    STATUS_POTENTIAL_DECLINE,
    STATUS_POTENTIAL_INCREASE,
    STATUS_STABLE,
    AppConfig,
)
from src.microreservoir.change_detection import (
    HYDROLOGICAL_DISCLAIMER,
    compare_observations,
)
from src.microreservoir.schemas import (
    ChangePixelClass,
    Observation,
    ObservationMetadata,
    WaterDetectionResult,
    WaterIndexMethod,
)


def make_dummy_obs(
    shape=(30, 30),
    cloud_cover: float = 2.0,
    scene_id: str = "SCENE",
    date: str = "2024-01-01",
    crs: str = "EPSG:32643",
    pixel_resolution_m: float = 10.0,
) -> Observation:
    meta = ObservationMetadata(
        scene_id=scene_id,
        date=date,
        cloud_cover_percent=cloud_cover,
        crs=crs,
        pixel_resolution_m=pixel_resolution_m,
    )
    bands = {"green": np.ones(shape), "nir": np.ones(shape)}
    return Observation(metadata=meta, bands=bands)


def make_dummy_det(
    shape=(30, 30),
    water_count: int = 100,
    valid_count: int = 900,
) -> WaterDetectionResult:
    mask = np.zeros(shape, dtype=bool)
    flat = mask.ravel()
    flat[:water_count] = True
    mask = flat.reshape(shape)

    valid_mask = np.zeros(shape, dtype=bool)
    v_flat = valid_mask.ravel()
    v_flat[:valid_count] = True
    valid_mask = v_flat.reshape(shape)

    return WaterDetectionResult(
        water_mask=mask,
        index_map=np.zeros(shape, dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=water_count,
        total_valid_pixels=valid_count,
        water_fraction=water_count / valid_count if valid_count > 0 else 0.0,
        valid_mask=valid_mask,
    )


def test_compare_observations_10000_to_7500_m2():
    """Verify exact requirement: 10,000 m² to 7,500 m² = -2,500 m² and -25%."""
    # 100 pixels at 10m (10,000 m²) -> 75 pixels at 10m (7,500 m²)
    base_obs = make_dummy_obs(shape=(20, 20), scene_id="BASE", date="2024-01-01")
    comp_obs = make_dummy_obs(shape=(20, 20), scene_id="COMP", date="2024-02-01")

    base_det = make_dummy_det(shape=(20, 20), water_count=100, valid_count=400)
    comp_det = make_dummy_det(shape=(20, 20), water_count=75, valid_count=400)

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.status == STATUS_POTENTIAL_DECLINE
    assert res.quality_passed is True
    # Area in m²: 10,000 m² to 7,500 m²
    assert pytest.approx(res.baseline_area_m2, 1e-2) == 10000.0
    assert pytest.approx(res.comparison_area_m2, 1e-2) == 7500.0
    assert pytest.approx(res.area_delta_m2, 1e-2) == -2500.0
    # Area in ha: 1.0000 ha to 0.7500 ha
    assert pytest.approx(res.baseline_area_ha, 1e-4) == 1.0
    assert pytest.approx(res.comparison_area_ha, 1e-4) == 0.75
    assert pytest.approx(res.area_delta_ha, 1e-4) == -0.25
    # Percentage change: -25.0%
    assert res.area_delta_percent is not None
    assert pytest.approx(res.area_delta_percent, 0.01) == -25.0


def test_compare_observations_zero_baseline_no_division_by_zero():
    """Verify requirement: zero baseline area does not divide by zero; delta percent is None."""
    base_obs = make_dummy_obs(scene_id="BASE", date="2024-01-01")
    comp_obs = make_dummy_obs(scene_id="COMP", date="2024-02-01")

    # 0 water pixels in baseline, 50 water pixels in comparison
    base_det = make_dummy_det(water_count=0)
    comp_det = make_dummy_det(water_count=50)

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    # Percentage change must be None rather than infinite or fabricated!
    assert res.area_delta_percent is None
    assert res.status == STATUS_POTENTIAL_INCREASE
    assert res.baseline_area_m2 == 0.0
    assert res.comparison_area_m2 == 5000.0
    assert res.area_delta_m2 == 5000.0
    assert any("undefined" in w for w in res.warnings)


def test_compare_observations_zero_to_zero_baseline():
    """Verify zero water in both dates results in STATUS_STABLE and None percent delta."""
    base_obs = make_dummy_obs(scene_id="BASE", date="2024-01-01")
    comp_obs = make_dummy_obs(scene_id="COMP", date="2024-02-01")

    base_det = make_dummy_det(water_count=0)
    comp_det = make_dummy_det(water_count=0)

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.area_delta_percent is None
    assert res.status == STATUS_STABLE
    assert res.baseline_area_m2 == 0.0
    assert res.comparison_area_m2 == 0.0


def test_compare_observations_decline():
    """Verify that a drop exceeding decline_threshold_percent triggers STATUS_POTENTIAL_DECLINE."""
    # 200 pixels down to 140 pixels -> -30% change
    base_obs = make_dummy_obs(scene_id="BASE", date="2023-10-01")
    comp_obs = make_dummy_obs(scene_id="COMP", date="2024-03-01")

    base_det = make_dummy_det(water_count=200)
    comp_det = make_dummy_det(water_count=140)

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.status == STATUS_POTENTIAL_DECLINE
    assert pytest.approx(res.area_delta_percent, 0.1) == -30.0
    assert res.area_delta_ha < 0.0
    assert res.quality_passed is True


def test_compare_observations_increase():
    """Verify that an expansion exceeding increase_threshold_percent triggers STATUS_POTENTIAL_INCREASE."""
    base_obs = make_dummy_obs(scene_id="BASE", date="2024-05-01")
    comp_obs = make_dummy_obs(scene_id="COMP", date="2024-08-01")

    base_det = make_dummy_det(water_count=100)
    comp_det = make_dummy_det(water_count=150)  # +50% increase

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.status == STATUS_POTENTIAL_INCREASE
    assert pytest.approx(res.area_delta_percent, 0.1) == 50.0
    assert res.quality_passed is True


def test_compare_observations_stable():
    """Verify that shifts within +/- 10% are classified as STATUS_STABLE."""
    base_obs = make_dummy_obs(scene_id="BASE", date="2023-11-01")
    comp_obs = make_dummy_obs(scene_id="COMP", date="2023-11-20")

    base_det = make_dummy_det(water_count=200)
    comp_det = make_dummy_det(water_count=196)  # -2% shift

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.status == STATUS_STABLE
    assert pytest.approx(res.area_delta_percent, 0.1) == -2.0
    assert res.quality_passed is True


def test_compare_observations_dimension_mismatch():
    """Verify that unequal scene shapes produce STATUS_INVALID_COMPARISON."""
    base_obs = make_dummy_obs(shape=(30, 30))
    comp_obs = make_dummy_obs(shape=(40, 40))

    base_det = make_dummy_det(shape=(30, 30))
    comp_det = make_dummy_det(shape=(40, 40))

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.status == STATUS_INVALID_COMPARISON
    assert "dimensions do not match" in res.details
    assert res.quality_passed is False


def test_compare_observations_crs_mismatch():
    """Verify that comparing observations with different CRS produces STATUS_INVALID_COMPARISON."""
    base_obs = make_dummy_obs(scene_id="BASE", date="2024-01-01", crs="EPSG:32643")
    comp_obs = make_dummy_obs(scene_id="COMP", date="2024-02-01", crs="EPSG:32644")

    base_det = make_dummy_det(water_count=100)
    comp_det = make_dummy_det(water_count=80)

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.status == STATUS_INVALID_COMPARISON
    assert "CRS mismatch" in res.details
    assert res.quality_passed is False


def test_compare_observations_reversed_temporal_order():
    """Verify that baseline date after comparison date produces STATUS_INVALID_COMPARISON."""
    base_obs = make_dummy_obs(scene_id="BASE", date="2024-06-01")
    comp_obs = make_dummy_obs(scene_id="COMP", date="2024-01-01")  # earlier date!

    base_det = make_dummy_det(water_count=100)
    comp_det = make_dummy_det(water_count=80)

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.status == STATUS_INVALID_COMPARISON
    assert "Temporal order violation" in res.details
    assert res.quality_passed is False


def test_compare_observations_insufficient_valid_coverage():
    """Verify that valid pixel ratio below min_valid_pixel_ratio triggers STATUS_INSUFFICIENT_DATA."""
    base_obs = make_dummy_obs(shape=(10, 10), date="2024-01-01")
    comp_obs = make_dummy_obs(shape=(10, 10), date="2024-02-01")

    # 100 total pixels, but only 50 valid pixels (50% < 70% threshold)
    base_det = make_dummy_det(shape=(10, 10), water_count=20, valid_count=50)
    comp_det = make_dummy_det(shape=(10, 10), water_count=10, valid_count=100)

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.quality_passed is False


def test_compare_observations_excessive_cloud_insufficient():
    """Verify that cloud cover above limit triggers STATUS_INSUFFICIENT_DATA."""
    base_obs = make_dummy_obs(cloud_cover=5.0, date="2024-01-01")
    comp_obs = make_dummy_obs(cloud_cover=45.0, date="2024-02-01")  # exceeds 20% limit

    base_det = make_dummy_det(water_count=100)
    comp_det = make_dummy_det(water_count=80)

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)

    assert res.status == STATUS_INSUFFICIENT_DATA
    assert res.quality_passed is False


def test_configurable_threshold_behavior():
    """Verify that configurable decline and increase thresholds modify classification cutoff."""
    # -8% change
    base_obs = make_dummy_obs(scene_id="BASE", date="2024-01-01")
    comp_obs = make_dummy_obs(scene_id="COMP", date="2024-02-01")

    base_det = make_dummy_det(water_count=100)
    comp_det = make_dummy_det(water_count=92)  # -8%

    # Default threshold (-10%): -8% is STABLE
    res_default = compare_observations(base_obs, comp_obs, base_det, comp_det, cfg=DEFAULT_CONFIG)
    assert res_default.status == STATUS_STABLE

    # Custom sensitive config (-5%): -8% triggers POTENTIAL_DECLINE
    sensitive_cfg = AppConfig(decline_threshold_percent=-5.0)
    res_sensitive = compare_observations(base_obs, comp_obs, base_det, comp_det, cfg=sensitive_cfg)
    assert res_sensitive.status == STATUS_POTENTIAL_DECLINE


def test_hydrological_disclaimer_included():
    """Verify that hydrological disclaimer against groundwater/drought inference is present."""
    base_obs = make_dummy_obs(date="2024-01-01")
    comp_obs = make_dummy_obs(date="2024-02-01")

    base_det = make_dummy_det(water_count=100)
    comp_det = make_dummy_det(water_count=70)

    res = compare_observations(base_obs, comp_obs, base_det, comp_det)
    assert any("groundwater depletion" in w.lower() for w in res.warnings)


def test_transition_mask_classes():
    """Verify that change_mask categorical codes identify persistent, lost, gained, and invalid water."""
    shape = (2, 2)
    base_obs = make_dummy_obs(shape=shape, date="2024-01-01")
    comp_obs = make_dummy_obs(shape=shape, date="2024-02-01")

    # Pixel (0,0): Persistent water (True, True)
    # Pixel (0,1): Water lost (True, False)
    # Pixel (1,0): Water gained (False, True)
    # Pixel (1,1): Non-water (False, False)
    b_mask = np.array([[True, True], [False, False]])
    c_mask = np.array([[True, False], [True, False]])

    b_det = WaterDetectionResult(
        water_mask=b_mask,
        index_map=np.zeros(shape, dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=2,
        total_valid_pixels=4,
        water_fraction=0.5,
    )
    c_det = WaterDetectionResult(
        water_mask=c_mask,
        index_map=np.zeros(shape, dtype=np.float32),
        index_method=WaterIndexMethod.NDWI,
        threshold=0.0,
        water_pixel_count=2,
        total_valid_pixels=4,
        water_fraction=0.5,
    )

    res = compare_observations(base_obs, comp_obs, b_det, c_det)

    assert res.change_mask is not None
    assert res.change_mask[0, 0] == ChangePixelClass.PERSISTENT_WATER.value
    assert res.change_mask[0, 1] == ChangePixelClass.WATER_LOST.value
    assert res.change_mask[1, 0] == ChangePixelClass.WATER_GAINED.value
    assert res.change_mask[1, 1] == ChangePixelClass.NON_WATER.value


def test_compare_observations_unprojected_geographic_crs():
    """Verify that unprojected geographic CRS (EPSG:4326) triggers warning/unavailability."""
    base_obs = make_dummy_obs(scene_id="GEO_BASE", date="2024-01-01", crs="EPSG:4326")
    comp_obs = make_dummy_obs(scene_id="GEO_COMP", date="2024-02-01", crs="EPSG:4326")

    b_det = make_dummy_det(water_count=50)
    c_det = make_dummy_det(water_count=25)

    # When geographic CRS is provided, area calculation returns is_available=False
    res = compare_observations(base_obs, comp_obs, b_det, c_det)

    assert any("Geographic CRS" in w or "angular" in w for w in res.warnings)
    # Area must be reported as 0.0 / unavailable
    assert res.baseline_area_ha == 0.0
    assert res.comparison_area_ha == 0.0

