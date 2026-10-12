"""End-to-end integration tests for the Micro-Reservoir Intelligence pipeline."""

from __future__ import annotations

import numpy as np
import pytest

from config import DEFAULT_CONFIG, STATUS_POTENTIAL_DECLINE
from scripts.prepare_sample import generate_scene
from src.microreservoir.reporting import build_dashboard_data, run_analysis
from src.microreservoir.schemas import Observation, ObservationMetadata


def test_full_pipeline_end_to_end():
    """Verify end-to-end flow: Ingestion -> Validation -> Detection -> Estimation -> Comparison -> Dashboard."""
    # 1. Generate realistic synthetic scenes
    base_data = generate_scene(
        height=60,
        width=60,
        water_radii=(20, 16),
        cloud_fraction=0.01,
        seed=10,
    )
    comp_data = generate_scene(
        height=60,
        width=60,
        water_radii=(12, 10),  # Substantial water reduction
        cloud_fraction=0.02,
        seed=20,
    )

    base_obs = Observation(
        metadata=ObservationMetadata(
            scene_id="TEST_E2E_BASE",
            date="2023-10-15",
            cloud_cover_percent=1.0,
        ),
        bands={
            "green": base_data["green"],
            "nir": base_data["nir"],
            "red": base_data["red"],
            "blue": base_data["blue"],
            "swir1": base_data["swir1"],
        },
        valid_mask=base_data["valid_mask"],
    )

    comp_obs = Observation(
        metadata=ObservationMetadata(
            scene_id="TEST_E2E_COMP",
            date="2024-03-15",
            cloud_cover_percent=2.0,
        ),
        bands={
            "green": comp_data["green"],
            "nir": comp_data["nir"],
            "red": comp_data["red"],
            "blue": comp_data["blue"],
            "swir1": comp_data["swir1"],
        },
        valid_mask=comp_data["valid_mask"],
    )

    # 2. Run analysis pipeline
    analysis = run_analysis(base_obs, comp_obs, cfg=DEFAULT_CONFIG)

    # 3. Assert pipeline outputs
    assert analysis.baseline_area.water_area_hectares > analysis.comparison_area.water_area_hectares
    assert analysis.baseline_area.water_area_m2 > 0
    assert analysis.comparison_area.water_area_m2 > 0
    assert analysis.comparison.area_delta_m2 < 0
    assert pytest.approx(analysis.baseline_area.water_area_hectares * 10000.0, 1.0) == analysis.baseline_area.water_area_m2
    assert pytest.approx(analysis.comparison_area.water_area_hectares * 10000.0, 1.0) == analysis.comparison_area.water_area_m2

    assert analysis.comparison.status == STATUS_POTENTIAL_DECLINE
    assert analysis.comparison.quality_passed is True
    assert analysis.comparison.area_delta_percent < -20.0
    assert analysis.comparison.change_mask is not None
    assert len(analysis.alerts) >= 1
    assert any("groundwater" in w.lower() for w in analysis.comparison.warnings)

    # 4. Assert dashboard data serialization
    dashboard = build_dashboard_data(analysis)
    assert dashboard["status"] == STATUS_POTENTIAL_DECLINE
    assert len(dashboard["metrics"]) == 4
    assert len(dashboard["alerts"]) >= 1
    assert "generated_at" in dashboard
    assert dashboard["summary"]["quality_passed"] is True
