"""Surface water area estimation and uncertainty quantification module.

Calculates water coverage in square metres, hectares, and acres based on spatial
ground resolution and trustworthy CRS/affine transform parameters, incorporating
boundary mixed-pixel uncertainty bounds.
"""

from __future__ import annotations

import math
from typing import List, Optional, Tuple, Union
import numpy as np
import rasterio
from rasterio.crs import CRS

from config import DEFAULT_CONFIG
from src.microreservoir.schemas import (
    AreaEstimate,
    Observation,
    WaterDetectionResult,
)


def estimate_area(
    detection: WaterDetectionResult,
    pixel_resolution_m: Optional[float] = None,
    transform: Optional[Union[rasterio.Affine, Tuple[float, float, float, float, float, float]]] = None,
    crs: Optional[Union[str, CRS]] = None,
    observation: Optional[Observation] = None,
    reject_unsuitable_crs: bool = False,
) -> AreaEstimate:
    """Compute physical ground area from classified water detection results.

    Uses trustworthy CRS and affine-transform information to derive exact ground
    pixel area. Rejects or reports area as unavailable if the CRS is geographic
    (degree-based) or untrustworthy, adhering to the principle of never inventing
    measurements.

    Args:
        detection: WaterDetectionResult containing the classified water mask and valid mask.
        pixel_resolution_m: Optional nominal ground sampling distance in metres.
        transform: Optional affine transform (Affine instance or 6-element tuple).
        crs: Optional Coordinate Reference System (string e.g. 'EPSG:32643' or CRS object).
        observation: Optional Observation instance to extract CRS, transform, and resolution.
        reject_unsuitable_crs: If True, raises ValueError when CRS is geographic/unsuitable.
            If False (default), returns AreaEstimate with is_available=False and warnings.

    Returns:
        AreaEstimate with values in m², hectares, acres, uncertainty bounds, and availability.

    Raises:
        ValueError: If pixel resolution or transform determinant is non-positive,
            or if reject_unsuitable_crs=True and CRS is geographic/unprojected.
    """
    warnings: List[str] = []

    # 1. Harvest parameters from Observation if provided
    if observation is not None:
        if pixel_resolution_m is None:
            pixel_resolution_m = observation.metadata.pixel_resolution_m
        if transform is None:
            transform = observation.metadata.transform
        if crs is None:
            crs = observation.metadata.crs

    # 2. Count valid water pixels strictly excluding NoData/invalid pixels
    if detection.valid_mask is not None:
        valid_water_pixels = detection.water_mask & detection.valid_mask
        pixel_count = int(np.sum(valid_water_pixels))
    else:
        pixel_count = int(detection.water_pixel_count)

    if pixel_count < 0:
        raise ValueError(f"Water pixel count cannot be negative, got {pixel_count}")

    # 3. CRS Trustworthiness and Projection Check
    crs_str: Optional[str] = None
    is_projected = True  # Default to True when CRS is omitted but explicit resolution given

    if crs is not None:
        try:
            if isinstance(crs, CRS):
                crs_obj = crs
            else:
                crs_obj = CRS.from_user_input(crs)
            crs_str = crs_obj.to_string()
            is_projected = bool(crs_obj.is_projected)
        except Exception as exc:
            warnings.append(f"Unparseable or unverified CRS '{crs}': {exc}.")
            is_projected = False

    # Check for geographic (degree-based) or unprojected CRS
    if crs is not None and not is_projected:
        msg = (
            f"Geographic CRS ('{crs_str or crs}') detected: coordinates are in angular units (degrees). "
            f"Planar ground area in square metres is unreliable and unavailable without reprojecting "
            f"to an appropriate projected coordinate system (e.g., UTM)."
        )
        if reject_unsuitable_crs:
            raise ValueError(msg)

        warnings.append(msg)
        return AreaEstimate(
            pixel_count=pixel_count,
            pixel_resolution_m=float(pixel_resolution_m or 0.0),
            pixel_area_m2=0.0,
            water_area_m2=0.0,
            water_area_hectares=0.0,
            water_area_acres=0.0,
            uncertainty_range_hectares=(0.0, 0.0),
            is_available=False,
            crs=crs_str or (str(crs) if crs else None),
            warnings=warnings,
        )

    # 4. Calculate Ground Pixel Area using Transform or Linear Resolution
    # Do not assume 10m x 10m; derive directly from affine transform or resolution.
    if transform is not None:
        if isinstance(transform, (tuple, list)) and len(transform) == 6:
            t = rasterio.Affine(
                transform[0], transform[1], transform[2],
                transform[3], transform[4], transform[5]
            )
        elif isinstance(transform, rasterio.Affine):
            t = transform
        else:
            raise ValueError(f"Unsupported affine transform specification: {transform}")

        # Determinant gives ground area per pixel in CRS units (m² for projected CRS)
        det = abs(t.a * t.e - t.b * t.d)
        if det <= 0.0:
            raise ValueError(f"Affine transform has non-positive area determinant: {det}")
        pixel_area_m2 = float(det)
        if pixel_resolution_m is None:
            pixel_resolution_m = math.sqrt(pixel_area_m2)
    elif pixel_resolution_m is not None:
        if pixel_resolution_m <= 0:
            raise ValueError(
                f"pixel_resolution_m must be strictly positive, got {pixel_resolution_m}"
            )
        pixel_area_m2 = float(pixel_resolution_m ** 2)
    else:
        raise ValueError(
            "Neither pixel_resolution_m nor affine transform was provided to calculate pixel ground area."
        )

    # 5. Compute Ground Surface Water Area
    water_area_m2 = float(pixel_count * pixel_area_m2)
    water_area_hectares = water_area_m2 * DEFAULT_CONFIG.m2_to_hectare
    water_area_acres = water_area_m2 * DEFAULT_CONFIG.m2_to_acre

    # 6. Boundary mixed-pixel uncertainty estimation
    # Boundary uncertainty is proportional to perimeter / sqrt(pixel_count)
    if pixel_count == 0:
        uncertainty_range = (0.0, 0.0)
    else:
        edge_uncertainty_pixels = max(1.0, math.sqrt(pixel_count))
        uncertainty_m2 = edge_uncertainty_pixels * pixel_area_m2
        uncertainty_ha = uncertainty_m2 * DEFAULT_CONFIG.m2_to_hectare

        lower_bound = max(0.0, water_area_hectares - uncertainty_ha)
        upper_bound = water_area_hectares + uncertainty_ha
        uncertainty_range = (round(lower_bound, 4), round(upper_bound, 4))

    return AreaEstimate(
        pixel_count=pixel_count,
        pixel_resolution_m=round(float(pixel_resolution_m), 4),
        pixel_area_m2=round(pixel_area_m2, 4),
        water_area_m2=round(water_area_m2, 2),
        water_area_hectares=round(water_area_hectares, 4),
        water_area_acres=round(water_area_acres, 4),
        uncertainty_range_hectares=uncertainty_range,
        is_available=True,
        crs=crs_str or (str(crs) if crs else None),
        warnings=warnings,
    )
