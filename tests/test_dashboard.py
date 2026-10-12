"""Unit and integration tests for Phase 5 Streamlit dashboard components and orchestration.

Tests dashboard imports, report exports, visualization generation, and orchestration workflows.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np
import pytest

from config import (
    DEFAULT_CONFIG,
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_COMPARISON,
    STATUS_POTENTIAL_DECLINE,
    STATUS_POTENTIAL_INCREASE,
    STATUS_STABLE,
)
from app import (
    load_npz_scene,
    load_sample_manifest,
    render_comparison_bar_chart,
    render_status_badge,
)
from scripts.prepare_sample import generate_scene
from src.microreservoir.reporting import (
    build_dashboard_data,
    export_report_csv,
    export_report_json,
    run_analysis,
)
from src.microreservoir.schemas import (
    Observation,
    ObservationMetadata,
)


def make_test_analysis():
    """Helper generating a realistic synthetic analysis result."""
    base_data = generate_scene(height=40, width=40, water_center=(20, 20), water_radii=(15, 12), seed=42)
    comp_data = generate_scene(height=40, width=40, water_center=(20, 20), water_radii=(8, 6), seed=43)

    base_obs = Observation(
        metadata=ObservationMetadata(
            scene_id="TEST_BASE",
            date="2023-10-15",
            cloud_cover_percent=2.0,
            crs="EPSG:32643",
            pixel_resolution_m=10.0,
        ),
        bands={"green": base_data["green"], "nir": base_data["nir"]},
        valid_mask=base_data["valid_mask"],
    )

    comp_obs = Observation(
        metadata=ObservationMetadata(
            scene_id="TEST_COMP",
            date="2024-03-15",
            cloud_cover_percent=3.0,
            crs="EPSG:32643",
            pixel_resolution_m=10.0,
        ),
        bands={"green": comp_data["green"], "nir": comp_data["nir"]},
        valid_mask=comp_data["valid_mask"],
    )

    return run_analysis(base_obs, comp_obs, cfg=DEFAULT_CONFIG)


def test_dashboard_imports_and_status_badges():
    """Verify that all status badges render valid HTML spans for every central status."""
    for st_val in [
        STATUS_STABLE,
        STATUS_POTENTIAL_DECLINE,
        STATUS_POTENTIAL_INCREASE,
        STATUS_INSUFFICIENT_DATA,
        STATUS_INVALID_COMPARISON,
    ]:
        badge = render_status_badge(st_val)
        assert "<span" in badge
        assert "border-radius" in badge
        assert st_val.replace("_", " ").upper() in badge


def test_dashboard_comparison_chart_generation():
    """Verify that render_comparison_bar_chart produces an interactive Plotly Figure with correct values."""
    analysis = make_test_analysis()
    fig = render_comparison_bar_chart(analysis)

    assert fig is not None
    assert len(fig.data) == 1
    trace = fig.data[0]
    # Check that baseline and follow-up values match analysis
    assert pytest.approx(trace.y[0], 1e-4) == analysis.baseline_area.water_area_hectares
    assert pytest.approx(trace.y[1], 1e-4) == analysis.comparison_area.water_area_hectares
    assert "Net Shift" in fig.layout.title.text


def test_dashboard_report_exports_csv_and_json():
    """Verify that export_report_csv and export_report_json produce complete, parseable reports."""
    analysis = make_test_analysis()
    res_id = "RES-TEST-99"

    # 1. Test CSV Export
    csv_str = export_report_csv(analysis, reservoir_id=res_id)
    assert isinstance(csv_str, str)
    assert "Reservoir Identifier,RES-TEST-99" in csv_str
    assert "Baseline Scene ID,TEST_BASE" in csv_str
    assert "Comparison Scene ID,TEST_COMP" in csv_str
    assert "Hydrological Disclaimer" in csv_str
    assert "Operational Status,potential_decline" in csv_str

    # 2. Test JSON Export
    json_str = export_report_json(analysis, reservoir_id=res_id)
    assert isinstance(json_str, str)
    parsed = json.loads(json_str)
    assert parsed["reservoir_id"] == res_id
    assert parsed["status"] == "potential_decline"
    assert parsed["observations"]["baseline"]["scene_id"] == "TEST_BASE"
    assert parsed["observations"]["comparison"]["scene_id"] == "TEST_COMP"
    assert "change_metrics" in parsed
    assert "assumptions_and_caveats" in parsed
    assert "hydrological_disclaimer" in parsed["assumptions_and_caveats"]
    assert len(parsed["alerts"]) >= 1


def test_dashboard_values_match_analysis_engine():
    """Verify that serialized dashboard metrics strictly match the underlying analysis engine."""
    analysis = make_test_analysis()
    dash_data = build_dashboard_data(analysis)

    assert dash_data["status"] == analysis.comparison.status
    assert dash_data["summary"]["baseline_area_ha"] == analysis.baseline_area.water_area_hectares
    assert dash_data["summary"]["comparison_area_ha"] == analysis.comparison_area.water_area_hectares
    assert dash_data["summary"]["area_delta_ha"] == analysis.comparison.area_delta_ha
    assert dash_data["summary"]["quality_passed"] == analysis.comparison.quality_passed
    assert len(dash_data["metrics"]) == 4


def test_dashboard_manifest_loading():
    """Verify load_sample_manifest loads valid scenarios."""
    manifest = load_sample_manifest()
    assert "sample_scenarios" in manifest
    assert len(manifest["sample_scenarios"]) >= 4


def test_streamlit_apptest_headless_startup_and_analysis_trigger():
    """Exercise headless startup and Analyse button click using Streamlit AppTest framework."""
    from streamlit.testing.v1 import AppTest

    app_path = str(Path(__file__).resolve().parent.parent / "app.py")
    at = AppTest.from_file(app_path, default_timeout=30)
    at.run()
    assert not at.exception

    # Verify that the Analyse button exists and click it to execute the synthetic scenario workflow
    primary_btns = [b for b in at.button if "Run Multi-Temporal Analysis" in b.label]
    assert len(primary_btns) == 1
    primary_btns[0].click().run()
    assert not at.exception


def test_dashboard_report_exports_cloud_limitation_documented():
    """Verify that export reports explicitly document the cloud screening limitation."""
    analysis = make_test_analysis()
    # Force cloud_assessed to False to test limitation notice
    analysis.baseline_observation.cloud_assessed = False
    analysis.comparison_observation.cloud_assessed = False

    csv_out = export_report_csv(analysis, reservoir_id="TEST_UNASSESSED")
    assert "Cloud Screening Status,Unassessed" in csv_out
    assert "automatic internal cloud detection is not performed" in csv_out

    json_out = export_report_json(analysis, reservoir_id="TEST_UNASSESSED")
    parsed = json.loads(json_out)
    assert "cloud_detection_limitation" in parsed["assumptions_and_caveats"]
    assert "Automatic internal cloud masking is not performed" in parsed["assumptions_and_caveats"]["cloud_detection_limitation"]


def test_dashboard_manifest_classifies_synthetic_vs_genuine():
    """Verify that the manifest clearly separates genuine vs synthetic data."""
    manifest = load_sample_manifest()
    assert "verified_genuine_observations" in manifest
    assert len(manifest["verified_genuine_observations"]) == 0
    assert manifest["verified_genuine_status"] == "BLOCKED_AWAITING_GENUINE_SATELLITE_DATA"

    for scen in manifest["synthetic_test_scenarios"]:
      assert scen["data_type"] == "synthetic_test_fixture"
      assert scen["is_real_observation"] is False

