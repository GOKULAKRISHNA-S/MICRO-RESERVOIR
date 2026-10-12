"""Preprocessing utilities for multispectral satellite observations.

Handles reflectance normalization, band array clipping, nodata masking,
and visual false-color/true-color composite creation optimized for CPU memory.
"""

from __future__ import annotations

from typing import Dict, Optional, Tuple
import numpy as np


def normalize_band(
    band: np.ndarray,
    scale_factor: Optional[float] = None,
    clip_range: Tuple[float, float] = (0.0, 1.0),
) -> np.ndarray:
    """Normalize raw digital numbers or top-of-atmosphere reflectance to [0.0, 1.0].

    Args:
        band: 2D numpy array with raw spectral data.
        scale_factor: Optional divisor (e.g., 10000.0 for Sentinel-2 L2A).
        clip_range: (min_val, max_val) bounds to prevent sensor saturation artifacts.

    Returns:
        Float32 array scaled to the specified clip range.
    """
    arr = band.astype(np.float32, copy=True)

    if scale_factor is not None and scale_factor > 0:
        arr /= scale_factor
    elif arr.max() > 1.0:
        # Auto-detect 10,000 scale factor or 8-bit scale
        if arr.max() > 255.0:
            arr /= 10000.0
        else:
            arr /= 255.0

    return np.clip(arr, clip_range[0], clip_range[1])


def create_rgb_composite(
    bands: Dict[str, np.ndarray],
    red_band: str = "red",
    green_band: str = "green",
    blue_band: str = "blue",
) -> Optional[np.ndarray]:
    """Generate a normalized 3-channel RGB composite array for display.

    Args:
        bands: Dictionary containing normalized or raw spectral arrays.
        red_band: Name of the red channel.
        green_band: Name of the green channel.
        blue_band: Name of the blue channel.

    Returns:
        3D float32 array of shape (height, width, 3) in range [0.0, 1.0], or None if bands missing.
    """
    b_keys = {k.lower(): k for k in bands.keys()}
    if not (red_band.lower() in b_keys and green_band.lower() in b_keys and blue_band.lower() in b_keys):
        return None

    r = normalize_band(bands[b_keys[red_band.lower()]])
    g = normalize_band(bands[b_keys[green_band.lower()]])
    b = normalize_band(bands[b_keys[blue_band.lower()]])

    return np.dstack((r, g, b))


def create_false_color_composite(
    bands: Dict[str, np.ndarray],
    nir_band: str = "nir",
    red_band: str = "red",
    green_band: str = "green",
) -> Optional[np.ndarray]:
    """Generate a Standard False Color composite (NIR, Red, Green) highlighting water vs vegetation.

    Water bodies appear dark blue to black, while healthy vegetation appears bright red.

    Args:
        bands: Dictionary of band arrays.
        nir_band: Name of NIR channel.
        red_band: Name of Red channel.
        green_band: Name of Green channel.

    Returns:
        3D float32 array of shape (height, width, 3), or None if bands missing.
    """
    return create_rgb_composite(
        bands=bands,
        red_band=nir_band,
        green_band=red_band,
        blue_band=green_band,
    )
