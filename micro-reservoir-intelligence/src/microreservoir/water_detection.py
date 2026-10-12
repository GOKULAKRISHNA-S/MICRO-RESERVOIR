"""Spectral water extraction module implementing NDWI, MNDWI, and AWEI algorithms.

This module provides pure NumPy vectorized spectral water index calculation and
threshold segmentation. It strictly validates input observations, handles zero and
near-zero denominators, preserves validity masks, excludes NoData/NaN/Inf pixels,
and outputs comprehensive summary statistics and heuristic warnings.

Heuristic Limitations of NDWI:
  NDWI = (Green - NIR) / (Green + NIR) is an empirical spectral ratio heuristic.
  It is subject to known classification challenges:
    1. Terrain and cloud shadows exhibit low reflectance in both bands and can
       produce false-positive water classifications.
    2. High turbidity or sediment scattering increases NIR reflectance, which can
       depress NDWI below zero and lead to false-negative omissions.
    3. Algal blooms and eutrophication increase chlorophyll NIR reflectance,
       potentially masking shallow water bodies.
    4. Built-up urban surfaces (asphalt, concrete) can occasionally mirror water signals.
"""

from __future__ import annotations

from typing import Dict, List, Optional, Tuple
import numpy as np

from config import DEFAULT_CONFIG, AppConfig
from src.microreservoir.schemas import (
    Observation,
    WaterDetectionResult,
    WaterIndexMethod,
)
from src.microreservoir.validation import validate_observation

HEURISTIC_CAVEAT_WARNING: str = (
    "NDWI is an empirical spectral ratio heuristic. Mountain/cloud shadows, urban surfaces, "
    "dark basaltic soil, and turbid or algae-rich water bodies may cause false positives or false negatives."
)


def compute_ndwi(
    green: np.ndarray,
    nir: np.ndarray,
    eps: float = 1e-7,
    invalid_fill: float = -1.0,
) -> np.ndarray:
    """Compute McFeeters (1996) Normalized Difference Water Index: (Green - NIR) / (Green + NIR).

    Vectorized implementation with zero-division protection and NaN/Inf sanitation.

    Args:
        green: 2D numpy array of green surface reflectance (Band 3 in Sentinel-2).
        nir: 2D numpy array of near-infrared surface reflectance (Band 8 in Sentinel-2).
        eps: Small positive epsilon to detect zero or near-zero denominators.
        invalid_fill: Default fill value assigned to NaN or undefined pixels.

    Returns:
        Float32 array of NDWI values strictly bounded in [-1.0, 1.0].

    Raises:
        ValueError: If input arrays are not 2-dimensional or have mismatched shapes.
    """
    if not isinstance(green, np.ndarray) or not isinstance(nir, np.ndarray):
        raise ValueError("Inputs 'green' and 'nir' must be numpy ndarrays.")
    if green.ndim != 2 or nir.ndim != 2:
        raise ValueError(
            f"Input arrays must be 2-dimensional (got green.ndim={green.ndim}, nir.ndim={nir.ndim})."
        )
    if green.shape != nir.shape:
        raise ValueError(
            f"Incompatible array shapes: green {green.shape} does not match nir {nir.shape}."
        )

    g = green.astype(np.float32, copy=False)
    n = nir.astype(np.float32, copy=False)

    numerator = g - n
    denominator = g + n

    # Zero or near-zero denominator handling
    zero_denom_mask = np.abs(denominator) <= eps

    # Invalid input handling (NaN or infinite values in either band)
    invalid_mask = np.isnan(g) | np.isnan(n) | np.isinf(g) | np.isinf(n)

    with np.errstate(divide="ignore", invalid="ignore"):
        # Safe division: where denominator is zero, output 0.0
        safe_denom = np.where(zero_denom_mask, 1.0, denominator)
        raw_ndwi = np.where(zero_denom_mask, 0.0, numerator / safe_denom)

        # Overwrite invalid pixels with invalid_fill
        ndwi = np.where(invalid_mask, invalid_fill, raw_ndwi)
        ndwi = np.nan_to_num(ndwi, nan=invalid_fill, posinf=1.0, neginf=-1.0)

    return np.clip(ndwi, -1.0, 1.0).astype(np.float32)


def compute_mndwi(
    green: np.ndarray,
    swir1: np.ndarray,
    eps: float = 1e-7,
    invalid_fill: float = -1.0,
) -> np.ndarray:
    """Compute Xu (2006) Modified NDWI: (Green - SWIR1) / (Green + SWIR1)."""
    if green.shape != swir1.shape:
        raise ValueError(f"Shape mismatch: green {green.shape} vs swir1 {swir1.shape}.")
    g = green.astype(np.float32, copy=False)
    s = swir1.astype(np.float32, copy=False)

    numerator = g - s
    denominator = g + s
    zero_mask = np.abs(denominator) <= eps
    invalid_mask = np.isnan(g) | np.isnan(s) | np.isinf(g) | np.isinf(s)

    with np.errstate(divide="ignore", invalid="ignore"):
        safe_denom = np.where(zero_mask, 1.0, denominator)
        raw = np.where(zero_mask, 0.0, numerator / safe_denom)
        mndwi = np.where(invalid_mask, invalid_fill, raw)
        mndwi = np.nan_to_num(mndwi, nan=invalid_fill, posinf=1.0, neginf=-1.0)

    return np.clip(mndwi, -1.0, 1.0).astype(np.float32)


def compute_awei(
    green: np.ndarray,
    nir: np.ndarray,
    swir1: np.ndarray,
    swir2: Optional[np.ndarray] = None,
) -> np.ndarray:
    """Compute Feyisa et al. (2014) Automated Water Extraction Index (no shadow variant)."""
    swir2_arr = swir2 if swir2 is not None else swir1
    g = green.astype(np.float32, copy=False)
    n = nir.astype(np.float32, copy=False)
    s1 = swir1.astype(np.float32, copy=False)
    s2 = swir2_arr.astype(np.float32, copy=False)

    awei = 4.0 * (g - s1) - (0.25 * n + 2.75 * s2)
    return np.nan_to_num(awei, nan=-10.0).astype(np.float32)


def detect_water(
    obs: Observation,
    method: Optional[WaterIndexMethod] = None,
    threshold: Optional[float] = None,
    cfg: Optional[AppConfig] = None,
    validate: bool = True,
) -> WaterDetectionResult:
    """Perform surface water extraction on a validated multispectral observation.

    Args:
        obs: Observation instance containing spectral band arrays.
        method: Spectral index algorithm (default: configured DEFAULT_WATER_INDEX, e.g. NDWI).
        threshold: Classification boundary cutoff (default: configured threshold for method).
        cfg: Optional application configuration with thresholds.
        validate: If True, executes validate_observation and raises ValueError on defects.

    Returns:
        WaterDetectionResult containing boolean water mask, continuous index map,
        valid pixel mask, summary statistics, and diagnostic warnings.

    Raises:
        ValueError: If observation fails validation or required spectral bands are missing.
    """
    config = cfg or DEFAULT_CONFIG
    chosen_method = method or WaterIndexMethod(config.default_water_index.upper())
    applied_threshold = (
        float(threshold)
        if threshold is not None
        else config.get_index_threshold(chosen_method.value)
    )

    warnings: List[str] = [HEURISTIC_CAVEAT_WARNING]

    # 1. Validation Pre-Check
    if validate:
        val_res = validate_observation(obs, cfg=config)
        if not val_res.is_valid:
            raise ValueError(
                f"Cannot perform water detection on invalid observation: {'; '.join(val_res.errors)}"
            )
        warnings.extend(val_res.warnings)

    band_keys = {k.lower(): arr for k, arr in obs.bands.items()}

    # 2. Spectral Index Computation
    if chosen_method == WaterIndexMethod.NDWI:
        if "green" not in band_keys or "nir" not in band_keys:
            raise ValueError("NDWI water detection requires 'green' and 'nir' spectral bands.")
        index_map = compute_ndwi(band_keys["green"], band_keys["nir"])
        primary_bands = [band_keys["green"], band_keys["nir"]]

    elif chosen_method == WaterIndexMethod.MNDWI:
        if "green" not in band_keys or "swir1" not in band_keys:
            raise ValueError("MNDWI water detection requires 'green' and 'swir1' spectral bands.")
        index_map = compute_mndwi(band_keys["green"], band_keys["swir1"])
        primary_bands = [band_keys["green"], band_keys["swir1"]]

    elif chosen_method == WaterIndexMethod.AWEI:
        if "green" not in band_keys or "nir" not in band_keys or "swir1" not in band_keys:
            raise ValueError("AWEI water detection requires 'green', 'nir', and 'swir1' bands.")
        index_map = compute_awei(
            green=band_keys["green"],
            nir=band_keys["nir"],
            swir1=band_keys["swir1"],
            swir2=band_keys.get("swir2"),
        )
        primary_bands = [band_keys["green"], band_keys["nir"], band_keys["swir1"]]
    else:
        raise ValueError(f"Unknown water detection method: {chosen_method}")

    # 3. Valid Data Mask Construction
    shape = index_map.shape
    valid_filter = np.ones(shape, dtype=bool)

    # Exclude NaNs and infinities in primary spectral bands and index map
    valid_filter &= ~np.isnan(index_map)
    valid_filter &= ~np.isinf(index_map)
    for b in primary_bands:
        valid_filter &= ~np.isnan(b)
        valid_filter &= ~np.isinf(b)
        if obs.metadata.nodata_value is not None:
            if not np.isnan(obs.metadata.nodata_value):
                valid_filter &= (b != obs.metadata.nodata_value)

    # Apply observation's external valid_mask (e.g. cloud/shadow or raster NoData)
    if obs.valid_mask is not None:
        valid_pixel_mask = valid_filter & obs.valid_mask
    else:
        valid_pixel_mask = valid_filter

    # 4. Binary Water Mask Segmentation (Strictly > threshold on valid pixels)
    water_mask = (index_map > applied_threshold) & valid_pixel_mask

    # 5. Summary Statistics Calculation
    total_pixels = int(index_map.size)
    valid_count = int(np.sum(valid_pixel_mask))
    water_count = int(np.sum(water_mask))
    non_water_count = valid_count - water_count
    water_fraction = (water_count / valid_count) if valid_count > 0 else 0.0

    if valid_count > 0:
        valid_ndwi_values = index_map[valid_pixel_mask]
        summary_stats: Dict[str, float] = {
            "total_pixels": float(total_pixels),
            "valid_pixels": float(valid_count),
            "invalid_pixels": float(total_pixels - valid_count),
            "water_pixels": float(water_count),
            "non_water_pixels": float(non_water_count),
            "water_fraction": round(float(water_fraction), 6),
            "ndwi_min": round(float(np.min(valid_ndwi_values)), 4),
            "ndwi_max": round(float(np.max(valid_ndwi_values)), 4),
            "ndwi_mean": round(float(np.mean(valid_ndwi_values)), 4),
            "ndwi_std": round(float(np.std(valid_ndwi_values)), 4),
            "ndwi_median": round(float(np.median(valid_ndwi_values)), 4),
            "threshold_applied": float(applied_threshold),
        }
    else:
        warnings.append("Observation contains zero valid pixels after NoData and quality masking.")
        summary_stats = {
            "total_pixels": float(total_pixels),
            "valid_pixels": 0.0,
            "invalid_pixels": float(total_pixels),
            "water_pixels": 0.0,
            "non_water_pixels": 0.0,
            "water_fraction": 0.0,
            "ndwi_min": 0.0,
            "ndwi_max": 0.0,
            "ndwi_mean": 0.0,
            "ndwi_std": 0.0,
            "ndwi_median": 0.0,
            "threshold_applied": float(applied_threshold),
        }

    if water_count == 0 and valid_count > 0:
        warnings.append(f"Zero water pixels detected at threshold {applied_threshold}.")

    return WaterDetectionResult(
        water_mask=water_mask,
        index_map=index_map,
        index_method=chosen_method,
        threshold=float(applied_threshold),
        water_pixel_count=water_count,
        total_valid_pixels=valid_count,
        water_fraction=float(water_fraction),
        valid_mask=valid_pixel_mask,
        summary_statistics=summary_stats,
        warnings=warnings,
    )
