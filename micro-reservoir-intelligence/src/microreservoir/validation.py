"""Validation and quality-assurance module for multispectral observations.

Inspects observation metadata and 2D band arrays for dimensional consistency,
radiometric validity, cloud obstruction thresholds, and adequate pixel coverage.
"""

from __future__ import annotations

from typing import List, Optional
import numpy as np

from config import DEFAULT_CONFIG, AppConfig
from src.microreservoir.exceptions import (
    IncompatibleGridError,
    InvalidDateError,
    TemporalOrderError,
)
from src.microreservoir.geotiff import (
    validate_grid_compatibility,
    validate_observation_date,
    validate_temporal_order,
)
from src.microreservoir.schemas import (
    Observation,
    QualityCheckReport,
    ValidationResult,
)


def validate_observation(
    obs: Observation,
    cfg: Optional[AppConfig] = None,
) -> ValidationResult:
    """Validate a multispectral observation for processing suitability.

    Args:
        obs: The Observation instance containing metadata and band arrays.
        cfg: Optional application configuration. Uses DEFAULT_CONFIG if omitted.

    Returns:
        ValidationResult with status ('valid', 'invalid', 'warning'), errors, and quality report.
    """
    config = cfg or DEFAULT_CONFIG
    errors: List[str] = []
    warnings: List[str] = []

    # 1. Structural checks
    if not obs.bands:
        errors.append("Observation contains no spectral bands.")
        return ValidationResult(
            is_valid=False,
            status="invalid",
            errors=errors,
            warnings=warnings,
            quality_report=None,
        )

    required_minimal_bands = {"green", "nir"}
    available_bands = {k.lower() for k in obs.bands.keys()}
    missing_bands = required_minimal_bands - available_bands
    if missing_bands:
        errors.append(
            f"Missing required core spectral bands: {sorted(list(missing_bands))}. "
            f"Available: {sorted(list(available_bands))}."
        )

    # 2. Shape and dimensionality consistency
    first_shape = None
    first_name = None
    for band_name, band_array in obs.bands.items():
        if not isinstance(band_array, np.ndarray):
            errors.append(f"Band '{band_name}' is not a valid numpy ndarray.")
            continue
        if band_array.ndim != 2:
            errors.append(
                f"Band '{band_name}' must be a 2D array, but got ndim={band_array.ndim}."
            )
            continue
        if first_shape is None:
            first_shape = band_array.shape
            first_name = band_name
        elif band_array.shape != first_shape:
            errors.append(
                f"Shape mismatch: band '{band_name}' shape {band_array.shape} "
                f"does not match band '{first_name}' shape {first_shape}."
            )

    if first_shape is None or first_shape[0] == 0 or first_shape[1] == 0:
        errors.append("Band arrays cannot be empty.")

    if errors:
        return ValidationResult(
            is_valid=False,
            status="invalid",
            errors=errors,
            warnings=warnings,
            quality_report=None,
        )

    total_pixels = first_shape[0] * first_shape[1]

    # 3. Valid mask consistency
    if obs.valid_mask is not None:
        if not isinstance(obs.valid_mask, np.ndarray):
            errors.append("valid_mask must be a numpy ndarray.")
        elif obs.valid_mask.shape != first_shape:
            errors.append(
                f"valid_mask shape {obs.valid_mask.shape} does not match bands shape {first_shape}."
            )

    # 4. Radiometric and Value Range Validation
    for band_name, band_array in obs.bands.items():
        if np.isnan(band_array).all():
            errors.append(f"Band '{band_name}' contains all NaN values.")
        if np.isneginf(band_array).any() or np.isposinf(band_array).any():
            errors.append(f"Band '{band_name}' contains infinite (Inf) values.")

    # 5. Date validation
    try:
        validate_observation_date(obs.metadata.date)
    except InvalidDateError as exc:
        errors.append(str(exc))

    # 6. Quality metrics & Cloud threshold checking
    cloud_cover = obs.metadata.cloud_cover_percent
    cloud_assessed = obs.metadata.cloud_assessed or (cloud_cover is not None)

    if cloud_cover is not None:
        try:
            cloud_val = float(cloud_cover)
            if cloud_val < 0.0 or cloud_val > 100.0:
                warnings.append(
                    f"Reported cloud cover {cloud_val}% is out of the normal range [0, 100]."
                )
            elif cloud_val > config.max_cloud_cover_percent:
                warnings.append(
                    f"Cloud cover ({cloud_val:.1f}%) exceeds configured limit "
                    f"({config.max_cloud_cover_percent:.1f}%)."
                )
        except (ValueError, TypeError):
            warnings.append(f"Invalid cloud cover percentage value: {cloud_cover}")
    else:
        warnings.append(
            "No trustworthy cloud mask or cloud metadata was provided. Cloud assessment unavailable."
        )

    # Calculate valid pixel coverage
    if obs.valid_mask is not None:
        valid_pixel_count = int(np.sum(obs.valid_mask))
    else:
        # Infer validity from non-nan and non-zero across core bands
        valid_filter = np.ones(first_shape, dtype=bool)
        for b in obs.bands.values():
            valid_filter &= ~np.isnan(b)
        valid_pixel_count = int(np.sum(valid_filter))

    nodata_pixel_count = total_pixels - valid_pixel_count
    valid_ratio = valid_pixel_count / total_pixels if total_pixels > 0 else 0.0

    if valid_ratio < config.min_valid_pixel_ratio:
        warnings.append(
            f"Valid pixel ratio ({valid_ratio:.1%}) is below minimum threshold "
            f"({config.min_valid_pixel_ratio:.1%})."
        )

    passed_checks = len(errors) == 0 and len(warnings) == 0 and cloud_assessed
    quality_report = QualityCheckReport(
        cloud_cover_percent=float(cloud_cover) if cloud_cover is not None else None,
        nodata_pixel_count=nodata_pixel_count,
        valid_pixel_count=valid_pixel_count,
        total_pixel_count=total_pixels,
        valid_pixel_ratio=valid_ratio,
        passed_quality_checks=passed_checks,
        cloud_assessed=cloud_assessed,
        quality_warnings=list(warnings),
    )

    is_valid = len(errors) == 0
    if not is_valid:
        status = "invalid"
    elif len(warnings) > 0:
        status = "warning"
    else:
        status = "valid"

    return ValidationResult(
        is_valid=is_valid,
        status=status,
        errors=errors,
        warnings=warnings,
        quality_report=quality_report,
    )
