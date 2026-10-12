"""Pipeline orchestration and dashboard data serialization module.

Provides end-to-end execution through `run_analysis` and serializes
results into structured dictionaries for Streamlit visualization and reporting.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from config import DEFAULT_CONFIG, AppConfig
from src.microreservoir.alerts import generate_alerts
from src.microreservoir.area_estimation import estimate_area
from src.microreservoir.change_detection import compare_observations
from src.microreservoir.schemas import (
    AnalysisResult,
    Observation,
)
from src.microreservoir.validation import validate_observation
from src.microreservoir.water_detection import detect_water


def run_analysis(
    baseline_obs: Observation,
    comparison_obs: Observation,
    cfg: Optional[AppConfig] = None,
) -> AnalysisResult:
    """Execute the end-to-end multi-temporal micro-reservoir analysis pipeline.

    Steps:
      1. Validate baseline and comparison observations.
      2. Detect water masks via spectral indexing (e.g. NDWI).
      3. Compute surface area and uncertainty bounds.
      4. Execute bi-temporal change detection and transition classification.
      5. Generate operational alerts and summary metrics.

    Args:
        baseline_obs: Baseline Observation instance.
        comparison_obs: Comparison Observation instance.
        cfg: Optional application configuration.

    Returns:
        Consolidated AnalysisResult object.
    """
    config = cfg or DEFAULT_CONFIG

    # 1. Validation
    base_val = validate_observation(baseline_obs, config)
    comp_val = validate_observation(comparison_obs, config)

    # 2. Water Detection
    base_det = detect_water(baseline_obs, cfg=config)
    comp_det = detect_water(comparison_obs, cfg=config)

    # 3. Area Estimation
    base_area = estimate_area(
        base_det,
        observation=baseline_obs,
    )
    comp_area = estimate_area(
        comp_det,
        observation=comparison_obs,
    )

    # 4. Change Detection
    change_res = compare_observations(
        baseline_obs=baseline_obs,
        comparison_obs=comparison_obs,
        baseline_det=base_det,
        comparison_det=comp_det,
        baseline_area=base_area,
        comparison_area=comp_area,
        cfg=config,
    )

    # 5. Alert Generation
    alerts = generate_alerts(change_res, config)

    # 6. Consolidated Metrics
    summary_metrics: Dict[str, Any] = {
        "baseline_scene_id": baseline_obs.metadata.scene_id,
        "baseline_date": baseline_obs.metadata.date,
        "baseline_area_m2": base_area.water_area_m2,
        "baseline_area_ha": base_area.water_area_hectares,
        "baseline_water_pixels": base_area.pixel_count,
        "comparison_scene_id": comparison_obs.metadata.scene_id,
        "comparison_date": comparison_obs.metadata.date,
        "comparison_area_m2": comp_area.water_area_m2,
        "comparison_area_ha": comp_area.water_area_hectares,
        "comparison_water_pixels": comp_area.pixel_count,
        "area_delta_m2": change_res.area_delta_m2,
        "area_delta_ha": change_res.area_delta_ha,
        "area_delta_percent": change_res.area_delta_percent,
        "status": change_res.status,
        "confidence_score": change_res.confidence_score,
        "alert_count": len(alerts),
        "validation_passed": base_val.is_valid and comp_val.is_valid,
        "quality_passed": change_res.quality_passed,
    }

    return AnalysisResult(
        baseline_observation=baseline_obs.metadata,
        comparison_observation=comparison_obs.metadata,
        baseline_detection=base_det,
        comparison_detection=comp_det,
        baseline_area=base_area,
        comparison_area=comp_area,
        comparison=change_res,
        alerts=alerts,
        summary_metrics=summary_metrics,
    )


def build_dashboard_data(analysis: AnalysisResult) -> Dict[str, Any]:
    """Serialize an AnalysisResult into standard JSON/Streamlit-friendly primitives.

    Args:
        analysis: AnalysisResult instance.

    Returns:
        Dictionary containing metric cards, time-series data, and status badges.
    """
    comp = analysis.comparison
    base_area = analysis.baseline_area
    comp_area = analysis.comparison_area

    delta_pct_str = (
        f"{comp.area_delta_percent:+.1f}%"
        if comp.area_delta_percent is not None
        else "N/A"
    )

    metrics = [
        {
            "label": f"Baseline Area ({analysis.baseline_observation.date})",
            "value": f"{base_area.water_area_hectares:.3f} ha",
            "subtext": f"{base_area.water_area_acres:.2f} acres ({base_area.pixel_count:,} px)",
        },
        {
            "label": f"Comparison Area ({analysis.comparison_observation.date})",
            "value": f"{comp_area.water_area_hectares:.3f} ha",
            "subtext": f"{comp_area.water_area_acres:.2f} acres ({comp_area.pixel_count:,} px)",
        },
        {
            "label": "Net Change",
            "value": f"{comp.area_delta_ha:+.3f} ha",
            "delta": delta_pct_str,
        },
        {
            "label": "Operational Status",
            "value": comp.status.replace("_", " ").title(),
            "confidence": f"{comp.confidence_score * 100:.0f}% confidence",
        },
    ]

    alert_dicts = [
        {
            "severity": a.severity.value,
            "title": a.title,
            "message": a.message,
            "action": a.action_recommended,
            "timestamp": a.timestamp,
        }
        for a in analysis.alerts
    ]

    return {
        "status": comp.status,
        "metrics": metrics,
        "details": comp.details,
        "alerts": alert_dicts,
        "summary": analysis.summary_metrics,
        "generated_at": analysis.generated_at,
    }


def export_report_csv(analysis: AnalysisResult, reservoir_id: str = "RESERVOIR") -> str:
    """Generate a clean, structured CSV report of multi-temporal analysis results.

    Args:
        analysis: AnalysisResult instance from run_analysis.
        reservoir_id: Human-readable identifier for the monitored reservoir.

    Returns:
        CSV-formatted string containing metrics, metadata, status, and disclaimers.
    """
    import csv
    import io

    comp = analysis.comparison
    base_area = analysis.baseline_area
    comp_area = analysis.comparison_area

    rows = [
        ("Metric", "Value", "Notes"),
        ("Reservoir Identifier", reservoir_id, "Target water body ID"),
        ("Report Generated At (UTC)", analysis.generated_at, "Analysis completion timestamp"),
        ("Operational Status", comp.status, "Central multi-temporal classification"),
        ("Quality Checks Passed", str(comp.quality_passed), "Pre-flight spatial/data validation flag"),
        ("Confidence Score", f"{comp.confidence_score * 100:.1f}%", "Assessment confidence"),
        ("Baseline Scene ID", analysis.baseline_observation.scene_id, "Reference observation"),
        ("Baseline Date", analysis.baseline_observation.date, "Acquisition date"),
        ("Baseline CRS", analysis.baseline_observation.crs or "N/A", "Coordinate Reference System"),
        ("Baseline Pixel Resolution (m)", f"{analysis.baseline_observation.pixel_resolution_m:.2f}", "Ground sampling distance"),
        (
            "Baseline Cloud Cover (%)",
            f"{analysis.baseline_observation.cloud_cover_percent:.1f}"
            if analysis.baseline_observation.cloud_cover_percent is not None
            else "Unassessed",
            "Screened cloud percentage",
        ),
        ("Baseline Water Pixels", str(base_area.pixel_count), "Valid pixels classified as water"),
        ("Baseline Water Area (m²)", f"{base_area.water_area_m2:.2f}", "Ground surface area"),
        ("Baseline Water Area (ha)", f"{base_area.water_area_hectares:.4f}", "Hectares (1 ha = 10,000 m²)"),
        ("Comparison Scene ID", analysis.comparison_observation.scene_id, "Follow-up observation"),
        ("Comparison Date", analysis.comparison_observation.date, "Acquisition date"),
        ("Comparison CRS", analysis.comparison_observation.crs or "N/A", "Coordinate Reference System"),
        ("Comparison Pixel Resolution (m)", f"{analysis.comparison_observation.pixel_resolution_m:.2f}", "Ground sampling distance"),
        (
            "Comparison Cloud Cover (%)",
            f"{analysis.comparison_observation.cloud_cover_percent:.1f}"
            if analysis.comparison_observation.cloud_cover_percent is not None
            else "Unassessed",
            "Screened cloud percentage",
        ),
        ("Comparison Water Pixels", str(comp_area.pixel_count), "Valid pixels classified as water"),
        ("Comparison Water Area (m²)", f"{comp_area.water_area_m2:.2f}", "Ground surface area"),
        ("Comparison Water Area (ha)", f"{comp_area.water_area_hectares:.4f}", "Hectares (1 ha = 10,000 m²)"),
        (
            "Absolute Net Change (m²)",
            f"{comp.area_delta_m2:+.2f}" if comp.area_delta_m2 is not None else "N/A",
            "Comparison minus Baseline",
        ),
        ("Absolute Net Change (ha)", f"{comp.area_delta_ha:+.4f}", "Comparison minus Baseline"),
        (
            "Percentage Change (%)",
            f"{comp.area_delta_percent:+.2f}%"
            if comp.area_delta_percent is not None
            else "Unavailable (Baseline Area is Zero)",
            "Relative shift",
        ),
        ("Spectral Index Method", analysis.baseline_detection.index_method.value, "Water detection algorithm"),
        ("Index Classification Threshold", str(analysis.baseline_detection.threshold), "Decision boundary"),
        (
            "Cloud Screening Status",
            "Screened via External Cloud Mask"
            if (analysis.baseline_observation.cloud_assessed and analysis.comparison_observation.cloud_assessed)
            else "Unassessed (No external cloud mask supplied; automatic internal cloud detection is not performed)",
            "Quality assurance limitation",
        ),
        (
            "Hydrological Disclaimer",
            "Surface-water extent reflects open surface water only; does not infer groundwater depletion or drought.",
            "Assumptions and limitations",
        ),
        ("Comparison Details", comp.details.replace("\n", " "), "Explanatory remarks"),
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerows(rows)
    return output.getvalue()


def export_report_json(analysis: AnalysisResult, reservoir_id: str = "RESERVOIR") -> str:
    """Generate a structured, serializable JSON report of multi-temporal analysis results.

    Args:
        analysis: AnalysisResult instance from run_analysis.
        reservoir_id: Human-readable identifier for the monitored reservoir.

    Returns:
        JSON-formatted string with metrics, metadata, status, alerts, and disclaimers.
    """
    import json

    comp = analysis.comparison
    base_area = analysis.baseline_area
    comp_area = analysis.comparison_area

    report_dict = {
        "reservoir_id": reservoir_id,
        "generated_at": analysis.generated_at,
        "status": comp.status,
        "confidence_score": comp.confidence_score,
        "quality_passed": comp.quality_passed,
        "observations": {
            "baseline": {
                "scene_id": analysis.baseline_observation.scene_id,
                "date": analysis.baseline_observation.date,
                "sensor": analysis.baseline_observation.sensor,
                "crs": analysis.baseline_observation.crs,
                "pixel_resolution_m": analysis.baseline_observation.pixel_resolution_m,
                "cloud_cover_percent": analysis.baseline_observation.cloud_cover_percent,
                "cloud_assessed": analysis.baseline_observation.cloud_assessed,
                "water_pixels": base_area.pixel_count,
                "water_area_m2": base_area.water_area_m2,
                "water_area_ha": base_area.water_area_hectares,
                "water_area_acres": base_area.water_area_acres,
                "uncertainty_range_ha": list(base_area.uncertainty_range_hectares),
            },
            "comparison": {
                "scene_id": analysis.comparison_observation.scene_id,
                "date": analysis.comparison_observation.date,
                "sensor": analysis.comparison_observation.sensor,
                "crs": analysis.comparison_observation.crs,
                "pixel_resolution_m": analysis.comparison_observation.pixel_resolution_m,
                "cloud_cover_percent": analysis.comparison_observation.cloud_cover_percent,
                "cloud_assessed": analysis.comparison_observation.cloud_assessed,
                "water_pixels": comp_area.pixel_count,
                "water_area_m2": comp_area.water_area_m2,
                "water_area_ha": comp_area.water_area_hectares,
                "water_area_acres": comp_area.water_area_acres,
                "uncertainty_range_ha": list(comp_area.uncertainty_range_hectares),
            },
        },
        "change_metrics": {
            "area_delta_m2": comp.area_delta_m2,
            "area_delta_ha": comp.area_delta_ha,
            "area_delta_percent": comp.area_delta_percent,
            "status": comp.status,
            "details": comp.details,
        },
        "alerts": [
            {
                "severity": a.severity.value,
                "title": a.title,
                "message": a.message,
                "action_recommended": a.action_recommended,
                "timestamp": a.timestamp,
            }
            for a in analysis.alerts
        ],
        "assumptions_and_caveats": {
            "hydrological_disclaimer": (
                "Surface-water extent reflects open surface water only and must NOT be used to "
                "infer groundwater depletion, aquifer trends, or confirmed regional drought."
            ),
            "cloud_detection_limitation": (
                "Automatic internal cloud masking is not performed. Without an externally supplied "
                "cloud mask, cloud screening is unassessed and clear-sky conditions cannot be guaranteed."
            ),
            "spectral_method": analysis.baseline_detection.index_method.value,
            "threshold": analysis.baseline_detection.threshold,
            "warnings": comp.warnings,
        },
    }
    return json.dumps(report_dict, indent=2)
