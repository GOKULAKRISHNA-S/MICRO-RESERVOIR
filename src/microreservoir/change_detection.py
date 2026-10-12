"""Multi-temporal change detection and comparison module.

Analyzes surface water area dynamics between baseline and comparison dates,
classifies pixel-level transitions, and assigns standardized quality-aware statuses.
"""

from __future__ import annotations

from typing import List, Optional
import numpy as np

from config import (
    DEFAULT_CONFIG,
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_COMPARISON,
    STATUS_POTENTIAL_DECLINE,
    STATUS_POTENTIAL_INCREASE,
    STATUS_STABLE,
    AppConfig,
)
from src.microreservoir.area_estimation import estimate_area
from src.microreservoir.geotiff import validate_temporal_order
from src.microreservoir.schemas import (
    AreaEstimate,
    ChangeComparisonResult,
    ChangePixelClass,
    Observation,
    WaterDetectionResult,
)

HYDROLOGICAL_DISCLAIMER: str = (
    "Surface-water area changes reflect open water extent only. "
    "Do not infer groundwater depletion, aquifer depletion, or regional drought "
    "without independent hydrological, meteorological, and in-situ ground-truth data."
)


def compare_observations(
    baseline_obs: Observation,
    comparison_obs: Observation,
    baseline_det: WaterDetectionResult,
    comparison_det: WaterDetectionResult,
    baseline_area: Optional[AreaEstimate] = None,
    comparison_area: Optional[AreaEstimate] = None,
    cfg: Optional[AppConfig] = None,
) -> ChangeComparisonResult:
    """Compare two observation dates to detect reservoir surface area changes.

    Requirements:
      1. Enforces strict grid and CRS compatibility and temporal ordering.
      2. Rejects comparisons with insufficient valid pixel coverage or excessive cloud.
      3. Computes absolute changes in both square metres and hectares.
      4. If baseline area is zero, percentage change is reported as None (unavailable)
         rather than infinite or fabricated.
      5. Retains quality metadata and appends hydrological caveat warnings.

    Args:
        baseline_obs: Reference/earlier Observation instance.
        comparison_obs: Later/subsequent Observation instance.
        baseline_det: WaterDetectionResult for baseline observation.
        comparison_det: WaterDetectionResult for comparison observation.
        baseline_area: Optional precomputed AreaEstimate for baseline.
        comparison_area: Optional precomputed AreaEstimate for comparison.
        cfg: Optional application configuration.

    Returns:
        ChangeComparisonResult with area deltas, percentage shifts, pixel change mask,
        quality verification status, and explanatory warnings.
    """
    config = cfg or DEFAULT_CONFIG
    warnings: List[str] = [HYDROLOGICAL_DISCLAIMER]

    base_id = baseline_obs.metadata.scene_id
    base_date = baseline_obs.metadata.date
    comp_id = comparison_obs.metadata.scene_id
    comp_date = comparison_obs.metadata.date

    # 1. Structural Compatibility Check (Dimensions & Non-Empty Shapes)
    base_shape = baseline_obs.shape()
    comp_shape = comparison_obs.shape()
    det_base_shape = baseline_det.water_mask.shape
    det_comp_shape = comparison_det.water_mask.shape

    if (
        base_shape != comp_shape
        or det_base_shape != det_comp_shape
        or base_shape != det_base_shape
        or base_shape == (0, 0)
    ):
        err_msg = f"Spatial dimensions do not match: baseline {base_shape} vs comparison {comp_shape}."
        warnings.append(err_msg)
        return ChangeComparisonResult(
            baseline_id=base_id,
            baseline_date=base_date,
            comparison_id=comp_id,
            comparison_date=comp_date,
            baseline_area_ha=0.0,
            comparison_area_ha=0.0,
            area_delta_ha=0.0,
            area_delta_percent=None,
            status=STATUS_INVALID_COMPARISON,
            confidence_score=0.0,
            change_mask=None,
            details=err_msg,
            baseline_area_m2=0.0,
            comparison_area_m2=0.0,
            area_delta_m2=0.0,
            quality_passed=False,
            warnings=warnings,
        )

    # 2. CRS & Spatial Alignment Compatibility Checks
    base_crs = (baseline_obs.metadata.crs or "").strip().upper()
    comp_crs = (comparison_obs.metadata.crs or "").strip().upper()
    if base_crs and comp_crs and base_crs != comp_crs:
        err_msg = (
            f"CRS mismatch: baseline '{base_crs}' vs comparison '{comp_crs}'. "
            f"Comparing rasters across different Coordinate Reference Systems is rejected."
        )
        warnings.append(err_msg)
        return ChangeComparisonResult(
            baseline_id=base_id,
            baseline_date=base_date,
            comparison_id=comp_id,
            comparison_date=comp_date,
            baseline_area_ha=0.0,
            comparison_area_ha=0.0,
            area_delta_ha=0.0,
            area_delta_percent=None,
            status=STATUS_INVALID_COMPARISON,
            confidence_score=0.0,
            change_mask=None,
            details=err_msg,
            baseline_area_m2=0.0,
            comparison_area_m2=0.0,
            area_delta_m2=0.0,
            quality_passed=False,
            warnings=warnings,
        )

    tol = 1e-3
    if abs(baseline_obs.metadata.pixel_resolution_m - comparison_obs.metadata.pixel_resolution_m) > tol:
        err_msg = (
            f"Resolution mismatch: baseline {baseline_obs.metadata.pixel_resolution_m:.2f} m/px vs "
            f"comparison {comparison_obs.metadata.pixel_resolution_m:.2f} m/px."
        )
        warnings.append(err_msg)
        return ChangeComparisonResult(
            baseline_id=base_id,
            baseline_date=base_date,
            comparison_id=comp_id,
            comparison_date=comp_date,
            baseline_area_ha=0.0,
            comparison_area_ha=0.0,
            area_delta_ha=0.0,
            area_delta_percent=None,
            status=STATUS_INVALID_COMPARISON,
            confidence_score=0.0,
            change_mask=None,
            details=err_msg,
            baseline_area_m2=0.0,
            comparison_area_m2=0.0,
            area_delta_m2=0.0,
            quality_passed=False,
            warnings=warnings,
        )

    if baseline_obs.metadata.transform and comparison_obs.metadata.transform:
        t1, t2 = baseline_obs.metadata.transform, comparison_obs.metadata.transform
        if any(abs(v1 - v2) > tol for v1, v2 in zip(t1, t2)):
            err_msg = "Affine transform grid mismatch: observations do not share an aligned origin/grid."
            warnings.append(err_msg)
            return ChangeComparisonResult(
                baseline_id=base_id,
                baseline_date=base_date,
                comparison_id=comp_id,
                comparison_date=comp_date,
                baseline_area_ha=0.0,
                comparison_area_ha=0.0,
                area_delta_ha=0.0,
                area_delta_percent=None,
                status=STATUS_INVALID_COMPARISON,
                confidence_score=0.0,
                change_mask=None,
                details=err_msg,
                baseline_area_m2=0.0,
                comparison_area_m2=0.0,
                area_delta_m2=0.0,
                quality_passed=False,
                warnings=warnings,
            )

    # 3. Temporal Ordering Check
    if base_date and comp_date:
        if base_date > comp_date:
            err_msg = (
                f"Temporal order violation: baseline date ({base_date}) must strictly precede "
                f"the comparison date ({comp_date})."
            )
            warnings.append(err_msg)
            return ChangeComparisonResult(
                baseline_id=base_id,
                baseline_date=base_date,
                comparison_id=comp_id,
                comparison_date=comp_date,
                baseline_area_ha=0.0,
                comparison_area_ha=0.0,
                area_delta_ha=0.0,
                area_delta_percent=None,
                status=STATUS_INVALID_COMPARISON,
                confidence_score=0.0,
                change_mask=None,
                details=err_msg,
                baseline_area_m2=0.0,
                comparison_area_m2=0.0,
                area_delta_m2=0.0,
                quality_passed=False,
                warnings=warnings,
            )
        elif base_date == comp_date:
            warnings.append("Baseline and comparison dates are identical.")

    # 4. Quality and Data Coverage Sufficiency Checks
    total_px = base_shape[0] * base_shape[1]
    base_valid_ratio = (
        baseline_det.total_valid_pixels / total_px if total_px > 0 else 0.0
    )
    comp_valid_ratio = (
        comparison_det.total_valid_pixels / total_px if total_px > 0 else 0.0
    )

    base_cloud = baseline_obs.metadata.cloud_cover_percent or 0.0
    comp_cloud = comparison_obs.metadata.cloud_cover_percent or 0.0

    if (
        base_valid_ratio < config.min_valid_pixel_ratio
        or comp_valid_ratio < config.min_valid_pixel_ratio
        or (baseline_obs.metadata.cloud_cover_percent is not None and base_cloud > config.max_cloud_cover_percent)
        or (comparison_obs.metadata.cloud_cover_percent is not None and comp_cloud > config.max_cloud_cover_percent)
    ):
        details = (
            f"Cloud cover (base: {base_cloud:.1f}%, comp: {comp_cloud:.1f}%) or valid ratio "
            f"(base: {base_valid_ratio:.1%}, comp: {comp_valid_ratio:.1%}) exceeded limits."
        )
        warnings.append(details)
        return ChangeComparisonResult(
            baseline_id=base_id,
            baseline_date=base_date,
            comparison_id=comp_id,
            comparison_date=comp_date,
            baseline_area_ha=0.0,
            comparison_area_ha=0.0,
            area_delta_ha=0.0,
            area_delta_percent=None,
            status=STATUS_INSUFFICIENT_DATA,
            confidence_score=0.2,
            change_mask=None,
            details=details,
            baseline_area_m2=0.0,
            comparison_area_m2=0.0,
            area_delta_m2=0.0,
            quality_passed=False,
            warnings=warnings,
        )

    # 4. Area Estimation Retrieval and Trustworthiness Check
    base_area = baseline_area or estimate_area(
        baseline_det,
        observation=baseline_obs,
    )
    comp_area = comparison_area or estimate_area(
        comparison_det,
        observation=comparison_obs,
    )

    if not base_area.is_available or not comp_area.is_available:
        details = (
            "Surface area estimation is unavailable due to unprojected geographic CRS "
            "or untrustworthy spatial metadata."
        )
        warnings.extend(base_area.warnings)
        warnings.extend(comp_area.warnings)
        return ChangeComparisonResult(
            baseline_id=base_id,
            baseline_date=base_date,
            comparison_id=comp_id,
            comparison_date=comp_date,
            baseline_area_ha=0.0,
            comparison_area_ha=0.0,
            area_delta_ha=0.0,
            area_delta_percent=None,
            status=STATUS_INVALID_COMPARISON,
            confidence_score=0.0,
            change_mask=None,
            details=details,
            baseline_area_m2=0.0,
            comparison_area_m2=0.0,
            area_delta_m2=0.0,
            quality_passed=False,
            warnings=warnings,
        )

    # 5. Area Change Metrics Computation
    base_m2 = base_area.water_area_m2
    comp_m2 = comp_area.water_area_m2
    delta_m2 = comp_m2 - base_m2

    base_ha = base_area.water_area_hectares
    comp_ha = comp_area.water_area_hectares
    delta_ha = comp_ha - base_ha

    # Zero baseline area handling:
    # If baseline area is 0, percentage change is mathematically undefined and
    # reported as None rather than infinite or fabricated.
    if base_m2 <= 0.0:
        area_delta_percent = None
        warnings.append(
            "Baseline surface water area is 0.0; percentage change is undefined and reported as unavailable."
        )
    else:
        area_delta_percent = round(((delta_m2) / base_m2) * 100.0, 2)

    # 6. Quality-Aware Status Classification
    if area_delta_percent is not None:
        if area_delta_percent <= config.decline_threshold_percent:
            status = STATUS_POTENTIAL_DECLINE
        elif area_delta_percent >= config.increase_threshold_percent:
            status = STATUS_POTENTIAL_INCREASE
        else:
            status = STATUS_STABLE
    else:
        # Baseline was 0
        if comp_m2 > 0.0:
            status = STATUS_POTENTIAL_INCREASE
        else:
            status = STATUS_STABLE

    # 7. Categorical Pixel Transition Mask Construction
    # 0 = Non-water, 1 = Persistent water, 2 = Water lost, 3 = Water gained, 255 = Invalid
    b_mask = baseline_det.water_mask
    c_mask = comparison_det.water_mask

    change_mask = np.zeros(base_shape, dtype=np.uint8)
    change_mask[b_mask & c_mask] = ChangePixelClass.PERSISTENT_WATER.value
    change_mask[b_mask & ~c_mask] = ChangePixelClass.WATER_LOST.value
    change_mask[~b_mask & c_mask] = ChangePixelClass.WATER_GAINED.value

    # Apply invalid mask joint intersection
    b_valid = baseline_det.valid_mask if baseline_det.valid_mask is not None else baseline_obs.valid_mask
    c_valid = comparison_det.valid_mask if comparison_det.valid_mask is not None else comparison_obs.valid_mask
    if b_valid is not None and c_valid is not None:
        invalid_joint = ~(b_valid & c_valid)
        change_mask[invalid_joint] = ChangePixelClass.INVALID.value

    # Confidence score calculation
    avg_cloud = (base_cloud + comp_cloud) / 2.0
    confidence = max(0.4, min(1.0, 1.0 - (avg_cloud / 100.0)))

    # Explanatory details string
    if area_delta_percent is not None:
        details = (
            f"Surface area shifted from {base_ha:.4f} ha ({base_m2:,.0f} m², {base_date}) "
            f"to {comp_ha:.4f} ha ({comp_m2:,.0f} m², {comp_date}), representing a "
            f"{area_delta_percent:+.2f}% change ({delta_ha:+.4f} ha / {delta_m2:+,.0f} m²)."
        )
    else:
        details = (
            f"Surface area shifted from {base_ha:.4f} ha ({base_m2:,.0f} m², {base_date}) "
            f"to {comp_ha:.4f} ha ({comp_m2:,.0f} m², {comp_date}). Percentage change is unavailable "
            f"because baseline area is zero."
        )

    return ChangeComparisonResult(
        baseline_id=base_id,
        baseline_date=base_date,
        comparison_id=comp_id,
        comparison_date=comp_date,
        baseline_area_ha=round(base_ha, 4),
        comparison_area_ha=round(comp_ha, 4),
        area_delta_ha=round(delta_ha, 4),
        area_delta_percent=area_delta_percent,
        status=status,
        confidence_score=round(confidence, 2),
        change_mask=change_mask,
        details=details,
        baseline_area_m2=round(base_m2, 2),
        comparison_area_m2=round(comp_m2, 2),
        area_delta_m2=round(delta_m2, 2),
        quality_passed=True,
        warnings=warnings,
    )
