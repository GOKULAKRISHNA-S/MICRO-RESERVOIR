"""Unit tests for observation validation and quality control."""

from __future__ import annotations

import numpy as np
import pytest

from config import DEFAULT_CONFIG, AppConfig
from src.microreservoir.schemas import Observation, ObservationMetadata
from src.microreservoir.validation import validate_observation


def create_synthetic_obs(
    shape=(50, 50),
    cloud_cover: float = 2.0,
    bands_to_include=None,
    valid_mask=None,
) -> Observation:
    """Helper to create a synthetic Observation instance."""
    if bands_to_include is None:
        bands_to_include = ["green", "nir", "red", "blue", "swir1"]

    meta = ObservationMetadata(
        scene_id="TEST_SCENE_01",
        date="2024-01-01",
        cloud_cover_percent=cloud_cover,
    )

    bands = {}
    for b in bands_to_include:
        bands[b] = np.full(shape, 0.2, dtype=np.float32)

    return Observation(metadata=meta, bands=bands, valid_mask=valid_mask)


def test_validation_valid_observation():
    """Verify that a compliant observation passes validation with status 'valid'."""
    obs = create_synthetic_obs()
    result = validate_observation(obs)

    assert result.is_valid is True
    assert result.status == "valid"
    assert len(result.errors) == 0
    assert len(result.warnings) == 0
    assert result.quality_report is not None
    assert result.quality_report.passed_quality_checks is True


def test_validation_missing_core_bands():
    """Verify that missing green or nir bands causes an invalid status."""
    obs = create_synthetic_obs(bands_to_include=["red", "blue"])
    result = validate_observation(obs)

    assert result.is_valid is False
    assert result.status == "invalid"
    assert any("Missing required core spectral bands" in e for e in result.errors)


def test_validation_shape_mismatch():
    """Verify that inconsistent band dimensions trigger a validation error."""
    obs = create_synthetic_obs(bands_to_include=["green", "nir"])
    obs.bands["nir"] = np.full((30, 30), 0.2, dtype=np.float32)
    result = validate_observation(obs)

    assert result.is_valid is False
    assert any("Shape mismatch" in e for e in result.errors)


def test_validation_empty_bands():
    """Verify that empty band dictionaries are caught."""
    meta = ObservationMetadata(scene_id="EMPTY", date="2024-01-01")
    obs = Observation(metadata=meta, bands={})
    result = validate_observation(obs)

    assert result.is_valid is False
    assert result.status == "invalid"


def test_validation_cloud_cover_warning():
    """Verify that high cloud cover produces a quality warning while remaining valid."""
    obs = create_synthetic_obs(cloud_cover=25.0)
    result = validate_observation(obs)

    assert result.is_valid is True
    assert result.status == "warning"
    assert any("Cloud cover" in w for w in result.warnings)
    assert result.quality_report.passed_quality_checks is False


def test_validation_low_valid_ratio_warning():
    """Verify that low valid pixel ratio produces a quality warning."""
    h, w = 50, 50
    mask = np.zeros((h, w), dtype=bool)
    mask[:10, :10] = True  # only 100 out of 2500 pixels valid (~4%)

    obs = create_synthetic_obs(shape=(h, w), valid_mask=mask)
    result = validate_observation(obs)

    assert result.is_valid is True
    assert result.status == "warning"
    assert any("Valid pixel ratio" in w for w in result.warnings)


def test_validation_invalid_date_error():
    """Verify that malformed date string in metadata fails validation."""
    obs = create_synthetic_obs()
    obs.metadata.date = "2024-99-99"
    result = validate_observation(obs)

    assert result.is_valid is False
    assert result.status == "invalid"
    assert any("Invalid observation date" in e for e in result.errors)


def test_validation_unassessed_cloud_warning():
    """Verify that missing cloud assessment produces warning and passed_quality_checks=False."""
    obs = create_synthetic_obs(cloud_cover=None)
    obs.metadata.cloud_assessed = False
    result = validate_observation(obs)

    assert result.is_valid is True
    assert result.status == "warning"
    assert any("Cloud assessment unavailable" in w for w in result.warnings)
    assert result.quality_report.passed_quality_checks is False
    assert result.quality_report.cloud_assessed is False
