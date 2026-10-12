"""GeoTIFF loading, metadata extraction, and geospatial validation module.

Provides secure, local-only raster ingestion using Rasterio for Sentinel-2
and multispectral satellite imagery, with path-traversal prevention, explicit band
mapping, validity mask construction, and grid compatibility enforcement.
"""

from __future__ import annotations

import os
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional, Tuple, Union
import numpy as np
import rasterio
from rasterio.crs import CRS
from rasterio.errors import CRSError, RasterioIOError

from config import DEFAULT_CONFIG

from src.microreservoir.exceptions import (
    CorruptRasterError,
    IncompatibleGridError,
    InvalidDateError,
    MissingBandError,
    MissingCRSError,
    NoDataError,
    PathTraversalError,
    RasterReadError,
    TemporalOrderError,
    UnsupportedRasterError,
)
from src.microreservoir.schemas import Observation, ObservationMetadata


# -----------------------------------------------------------------------------
# Path Security
# -----------------------------------------------------------------------------
def validate_safe_path(
    path: Union[str, Path],
    base_dir: Optional[Union[str, Path]] = None,
    must_exist: bool = True,
) -> Path:
    """Validate a file path against null bytes, traversal attacks, and existence.

    Args:
        path: Path string or Path object to inspect.
        base_dir: Optional boundary directory that the path must reside within.
        must_exist: If True, asserts the file exists on the local filesystem.

    Returns:
        Resolved, safe Path instance.

    Raises:
        PathTraversalError: If path contains null bytes or escapes base_dir.
        FileNotFoundError: If must_exist=True and the file does not exist.
        RasterReadError: If the resolved path points to a directory rather than a file.
    """
    path_str = str(path)
    if "\0" in path_str:
        raise PathTraversalError("Unsafe path: null byte detected.")

    try:
        resolved = Path(path).resolve()
    except Exception as exc:
        raise PathTraversalError(f"Cannot resolve path '{path}': {exc}") from exc

    if base_dir is not None:
        try:
            resolved_base = Path(base_dir).resolve()
            # is_relative_to raises ValueError or returns False in Python 3.9+
            if not resolved.is_relative_to(resolved_base):
                raise PathTraversalError(
                    f"Path traversal detected: '{resolved}' escapes base directory '{resolved_base}'."
                )
        except AttributeError:
            # Fallback for Python versions before 3.9
            if not str(resolved).startswith(str(resolved_base)):
                raise PathTraversalError(
                    f"Path traversal detected: '{resolved}' escapes base directory '{resolved_base}'."
                )

    if must_exist:
        if not resolved.exists():
            raise FileNotFoundError(f"Raster file not found: '{resolved}'")
        if not resolved.is_file():
            raise RasterReadError(f"Specified path is not a file: '{resolved}'")

    return resolved


# -----------------------------------------------------------------------------
# Date & Temporal Order Validation
# -----------------------------------------------------------------------------
def validate_observation_date(date_str: str) -> date:
    """Validate that a date string follows the ISO-8601 calendar format 'YYYY-MM-DD'.

    Args:
        date_str: Acquisition date string.

    Returns:
        Parsed datetime.date object.

    Raises:
        InvalidDateError: If the date is malformed, has invalid calendar values, or wrong format.
    """
    if not isinstance(date_str, str) or not date_str.strip():
        raise InvalidDateError("Observation date cannot be empty.")

    try:
        parsed = datetime.strptime(date_str.strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        raise InvalidDateError(
            f"Invalid observation date '{date_str}'. Must follow strict ISO-8601 'YYYY-MM-DD' format."
        ) from exc

    return parsed


def validate_temporal_order(baseline_date_str: str, comparison_date_str: str) -> None:
    """Ensure baseline date strictly precedes the follow-up comparison date.

    Args:
        baseline_date_str: Baseline acquisition date (YYYY-MM-DD).
        comparison_date_str: Comparison acquisition date (YYYY-MM-DD).

    Raises:
        InvalidDateError: If either date is malformed.
        TemporalOrderError: If baseline date is on or after the comparison date.
    """
    base_d = validate_observation_date(baseline_date_str)
    comp_d = validate_observation_date(comparison_date_str)

    if base_d >= comp_d:
        raise TemporalOrderError(
            f"Baseline date ({base_d}) must strictly precede the comparison date ({comp_d}). "
            f"Reversed or identical temporal orders are not valid comparison sequences."
        )


# -----------------------------------------------------------------------------
# Metadata Extraction
# -----------------------------------------------------------------------------
def read_geotiff_metadata(
    path: Union[str, Path],
    base_dir: Optional[Union[str, Path]] = None,
    max_pixels: Optional[int] = None,
) -> Dict[str, Any]:
    """Read geospatial metadata and raster header properties from a GeoTIFF using Rasterio.

    Args:
        path: Path to the GeoTIFF file.
        base_dir: Optional base directory to enforce path safety.
        max_pixels: Optional maximum allowed pixel count (width * height).

    Returns:
        Dictionary containing dimensions, CRS, affine transform, pixel resolution,
        NoData values, data types, band count, bounds, and driver.

    Raises:
        FileNotFoundError: If the raster does not exist.
        CorruptRasterError: If the file is zero-byte, truncated, or unreadable.
        UnsupportedRasterError: If the file is not a supported raster format.
        MissingCRSError: If the raster lacks a Coordinate Reference System.
        RasterReadError: If transform/header structures are degenerate or exceeds pixel limit.
    """
    safe_path = validate_safe_path(path, base_dir=base_dir, must_exist=True)

    # Check for empty file before GDAL/Rasterio
    if safe_path.stat().st_size == 0:
        raise CorruptRasterError(f"Raster file '{safe_path}' is empty (0 bytes).")

    try:
        with rasterio.open(safe_path) as src:
            if src.crs is None:
                raise MissingCRSError(
                    f"Raster '{safe_path}' lacks a Coordinate Reference System (CRS). "
                    f"An explicit, valid CRS is required for micro-reservoir area measurement."
                )

            # Check for non-degenerate affine transform
            t = src.transform
            if t.a == 0.0 or t.e == 0.0:
                raise RasterReadError(
                    f"Raster '{safe_path}' has a degenerate affine transform (zero resolution): {t}."
                )

            # Resolution in linear units
            res_x, res_y = abs(float(src.res[0])), abs(float(src.res[1]))
            if res_x <= 0.0 or res_y <= 0.0:
                raise RasterReadError(
                    f"Raster '{safe_path}' has non-positive pixel resolution: ({res_x}, {res_y})."
                )

            # Pixel processing safety limit
            total_px = int(src.width * src.height)
            effective_limit = max_pixels if max_pixels is not None else DEFAULT_CONFIG.max_pixel_limit
            if total_px > effective_limit:
                raise RasterReadError(
                    f"Raster '{safe_path}' contains {total_px:,} pixels ({src.height}x{src.width}), "
                    f"which exceeds the safety processing limit of {effective_limit:,} pixels. "
                    f"Please clip the raster to the micro-reservoir AOI before processing."
                )

            meta: Dict[str, Any] = {
                "file_path": str(safe_path),
                "width": src.width,
                "height": src.height,
                "count": src.count,
                "crs": src.crs.to_string(),
                "crs_epsg": src.crs.to_epsg(),
                "transform": t,
                "transform_tuple": (t.a, t.b, t.c, t.d, t.e, t.f),
                "resolution": (res_x, res_y),
                "pixel_resolution_m": (res_x + res_y) / 2.0,
                "nodata": src.nodata,
                "dtypes": list(src.dtypes),
                "bounds": (src.bounds.left, src.bounds.bottom, src.bounds.right, src.bounds.top),
                "driver": src.driver,
                "tags": src.tags(),
            }
            return meta

    except (MissingCRSError, CorruptRasterError, RasterReadError):
        raise
    except RasterioIOError as exc:
        err_msg = str(exc).lower()
        if "not recognized as a supported file format" in err_msg:
            raise UnsupportedRasterError(
                f"File '{safe_path}' is not a recognized or supported raster format: {exc}"
            ) from exc
        raise CorruptRasterError(
            f"Failed to read raster '{safe_path}'. File may be corrupt or truncated: {exc}"
        ) from exc
    except CRSError as exc:
        raise MissingCRSError(f"Raster '{safe_path}' has an unparseable or corrupted CRS: {exc}") from exc
    except Exception as exc:
        raise RasterReadError(f"Unexpected error reading raster '{safe_path}': {exc}") from exc


# -----------------------------------------------------------------------------
# Grid & Study Area Compatibility
# -----------------------------------------------------------------------------
def validate_grid_compatibility(
    obs1: Observation,
    obs2: Observation,
    tolerance: float = 1e-3,
) -> None:
    """Validate that two observations share an identical study area, CRS, and raster grid.

    Rejects observations with mismatched CRS, dimensions, or origin transforms to
    prevent silent spatial misalignment errors.

    Args:
        obs1: First observation (e.g., baseline).
        obs2: Second observation (e.g., comparison).
        tolerance: Coordinate alignment tolerance in CRS units (default: 0.001 m).

    Raises:
        IncompatibleGridError: If CRS, dimensions, or grid origins do not match.
    """
    m1 = obs1.metadata
    m2 = obs2.metadata

    # 1. CRS match
    if not m1.crs or not m2.crs:
        raise IncompatibleGridError("Both observations must have a valid CRS defined.")

    if m1.crs.strip().upper() != m2.crs.strip().upper():
        raise IncompatibleGridError(
            f"Coordinate Reference System mismatch: '{m1.scene_id}' has CRS '{m1.crs}' "
            f"while '{m2.scene_id}' has CRS '{m2.crs}'. Comparing different projections is not permitted."
        )

    # 2. Dimensional shape match
    shape1 = obs1.shape()
    shape2 = obs2.shape()
    if shape1 != shape2:
        raise IncompatibleGridError(
            f"Spatial raster dimension mismatch: '{m1.scene_id}' shape {shape1} "
            f"does not match '{m2.scene_id}' shape {shape2}."
        )

    # 3. Ground resolution match
    if abs(m1.pixel_resolution_m - m2.pixel_resolution_m) > tolerance:
        raise IncompatibleGridError(
            f"Pixel resolution mismatch: '{m1.scene_id}' is {m1.pixel_resolution_m:.2f} m/px "
            f"while '{m2.scene_id}' is {m2.pixel_resolution_m:.2f} m/px."
        )

    # 4. Affine transform alignment (if available)
    if m1.transform is not None and m2.transform is not None:
        t1, t2 = m1.transform, m2.transform
        for i, (v1, v2) in enumerate(zip(t1, t2)):
            if abs(v1 - v2) > tolerance:
                raise IncompatibleGridError(
                    f"Affine transform grid mismatch at element {i} (baseline: {v1}, comparison: {v2}). "
                    f"Rasters do not share an aligned pixel grid."
                )

    # 5. Spatial bounding box match
    if m1.bounds and m2.bounds:
        for b1, b2 in zip(m1.bounds, m2.bounds):
            if abs(b1 - b2) > tolerance:
                raise IncompatibleGridError(
                    f"Geographic bounding box mismatch: '{m1.scene_id}' bounds {m1.bounds} "
                    f"do not match '{m2.scene_id}' bounds {m2.bounds}."
                )


# -----------------------------------------------------------------------------
# Observation Ingestion Entrypoints
# -----------------------------------------------------------------------------
def load_geotiff_observation(
    scene_id: str,
    date_str: str,
    band_files: Optional[Dict[str, Union[str, Path]]] = None,
    multiband_file: Optional[Union[str, Path]] = None,
    band_mapping: Optional[Dict[str, int]] = None,
    cloud_mask_file: Optional[Union[str, Path]] = None,
    sensor: str = "Sentinel-2",
    base_dir: Optional[Union[str, Path]] = None,
    max_pixels: Optional[int] = None,
) -> Observation:
    """Load a multispectral observation from local GeoTIFF file(s).

    Supported Layouts:
      Layout 1 (Separate Single-Band Files):
        Pass `band_files` mapping band names to file paths:
        `band_files={'green': 'path/B03.tif', 'nir': 'path/B08.tif'}`
      
      Layout 2 (Multiband Raster with Explicit Mapping):
        Pass `multiband_file` with a 1-indexed `band_mapping`:
        `multiband_file='scene.tif', band_mapping={'green': 1, 'nir': 2}`

    Args:
        scene_id: Identifier for the observation scene.
        date_str: Acquisition date (strict ISO-8601 'YYYY-MM-DD').
        band_files: Dictionary of single-band GeoTIFF paths.
        multiband_file: Path to multiband GeoTIFF file.
        band_mapping: Explicit dictionary mapping band names to 1-indexed band numbers.
        cloud_mask_file: Optional path to external cloud mask raster (non-zero = cloud/shadow).
        sensor: Sensor constellation name (default: "Sentinel-2").
        base_dir: Optional base directory to enforce path security.
        max_pixels: Optional maximum allowed pixel count (width * height).

    Returns:
        Fully validated Observation instance with band arrays and validity mask.

    Raises:
        ValueError: If layouts are ambiguous, contradictory, or empty.
        InvalidDateError: If date_str is invalid.
        MissingBandError: If required bands ('green', 'nir') are missing.
        IncompatibleGridError: If single-band rasters have mismatched dimensions or CRS.
        NoDataError: If observation contains 100% NoData or invalid pixels.
    """
    validate_observation_date(date_str)

    # 1. Layout Selection & Validation
    if band_files is None and multiband_file is None:
        raise ValueError(
            "Must provide either 'band_files' (single-band layout) or "
            "'multiband_file' with 'band_mapping' (multiband layout)."
        )
    if band_files is not None and multiband_file is not None:
        raise ValueError(
            "Cannot specify both 'band_files' and 'multiband_file'. Select one input layout."
        )

    bands: Dict[str, np.ndarray] = {}
    master_meta: Optional[Dict[str, Any]] = None
    common_shape: Optional[Tuple[int, int]] = None

    # -------------------------------------------------------------------------
    # Layout 1: Separate Single-Band Files
    # -------------------------------------------------------------------------
    if band_files is not None:
        if not band_files:
            raise ValueError("'band_files' dictionary cannot be empty.")

        norm_band_files = {k.strip().lower(): v for k, v in band_files.items()}
        required = {"green", "nir"}
        missing = required - set(norm_band_files.keys())
        if missing:
            raise MissingBandError(
                f"Missing required core spectral bands: {sorted(list(missing))}. "
                f"Available: {sorted(list(norm_band_files.keys()))}."
            )

        for b_name, b_path in norm_band_files.items():
            meta = read_geotiff_metadata(b_path, base_dir=base_dir, max_pixels=max_pixels)
            safe_b_path = validate_safe_path(b_path, base_dir=base_dir, must_exist=True)

            with rasterio.open(safe_b_path) as src:
                arr = src.read(1).astype(np.float32)

            if master_meta is None:
                master_meta = meta
                common_shape = (meta["height"], meta["width"])
            else:
                # Enforce exact dimensional and CRS alignment across single-band files
                if (meta["height"], meta["width"]) != common_shape:
                    raise IncompatibleGridError(
                        f"Band '{b_name}' dimensions ({meta['height']}, {meta['width']}) "
                        f"do not match reference dimensions {common_shape}."
                    )
                if meta["crs"] != master_meta["crs"]:
                    raise IncompatibleGridError(
                        f"Band '{b_name}' CRS '{meta['crs']}' does not match reference CRS '{master_meta['crs']}'."
                    )
                if meta["transform"] != master_meta["transform"]:
                    raise IncompatibleGridError(
                        f"Band '{b_name}' transform does not align with reference transform."
                    )

            bands[b_name] = arr

    # -------------------------------------------------------------------------
    # Layout 2: Multiband Raster with Explicit Band Mapping
    # -------------------------------------------------------------------------
    else:
        if band_mapping is None or not band_mapping:
            raise MissingBandError(
                "A multiband GeoTIFF layout requires an explicit 'band_mapping' dictionary "
                "specifying 1-indexed band numbers (e.g., {'green': 1, 'nir': 2}). "
                "Silently assuming band order is strictly forbidden."
            )

        norm_band_mapping = {k.strip().lower(): idx for k, idx in band_mapping.items()}
        required = {"green", "nir"}
        missing = required - set(norm_band_mapping.keys())
        if missing:
            raise MissingBandError(
                f"Multiband mapping is missing required core spectral bands: {sorted(list(missing))}."
            )

        master_meta = read_geotiff_metadata(multiband_file, base_dir=base_dir, max_pixels=max_pixels)
        common_shape = (master_meta["height"], master_meta["width"])
        safe_multi_path = validate_safe_path(multiband_file, base_dir=base_dir, must_exist=True)

        with rasterio.open(safe_multi_path) as src:
            total_bands = src.count
            for b_name, b_idx in norm_band_mapping.items():
                if not isinstance(b_idx, int) or b_idx < 1 or b_idx > total_bands:
                    raise MissingBandError(
                        f"Invalid band index {b_idx} for band '{b_name}'. "
                        f"Raster '{safe_multi_path}' only contains {total_bands} band(s) (1-indexed)."
                    )
                bands[b_name] = src.read(b_idx).astype(np.float32)

    assert master_meta is not None
    assert common_shape is not None

    # -------------------------------------------------------------------------
    # Validity Mask Construction (NoData + Cloud)
    # -------------------------------------------------------------------------
    h, w = common_shape
    valid_mask = np.ones((h, w), dtype=bool)

    # 1. Mask NoData values
    nodata_val = master_meta.get("nodata")
    for b_arr in bands.values():
        if nodata_val is not None:
            if np.isnan(nodata_val):
                valid_mask &= ~np.isnan(b_arr)
            else:
                valid_mask &= (b_arr != nodata_val)
        valid_mask &= ~np.isnan(b_arr)
        valid_mask &= ~np.isinf(b_arr)

    # 2. External Cloud / Shadow Mask Handling
    cloud_cover_percent: Optional[float] = None
    cloud_assessed = False

    if cloud_mask_file is not None:
        c_meta = read_geotiff_metadata(cloud_mask_file, base_dir=base_dir, max_pixels=max_pixels)
        if (c_meta["height"], c_meta["width"]) != common_shape:
            raise IncompatibleGridError(
                f"Cloud mask shape ({c_meta['height']}, {c_meta['width']}) "
                f"does not match raster dimensions {common_shape}."
            )
        safe_c_path = validate_safe_path(cloud_mask_file, base_dir=base_dir, must_exist=True)
        with rasterio.open(safe_c_path) as c_src:
            c_arr = c_src.read(1)

        # Any non-zero pixel in cloud mask indicates cloud/shadow obstruction
        cloud_pixels = c_arr != 0
        total_px = h * w
        cloud_count = int(np.sum(cloud_pixels))
        cloud_cover_percent = round((cloud_count / total_px) * 100.0, 2)
        cloud_assessed = True

        # Mask out cloud pixels from valid analysis mask
        valid_mask &= ~cloud_pixels

    # Enforce non-empty valid observations
    valid_count = int(np.sum(valid_mask))
    if valid_count == 0:
        raise NoDataError(
            f"Observation '{scene_id}' contains no valid pixels (100% NoData, invalid, or cloud)."
        )

    # Assemble metadata
    metadata = ObservationMetadata(
        scene_id=scene_id,
        date=date_str,
        sensor=sensor,
        pixel_resolution_m=master_meta["pixel_resolution_m"],
        crs=master_meta["crs"],
        bounds=master_meta["bounds"],
        cloud_cover_percent=cloud_cover_percent,
        cloud_assessed=cloud_assessed,
        transform=master_meta["transform_tuple"],
        dimensions=common_shape,
        nodata_value=nodata_val,
        dtype=master_meta["dtypes"][0] if master_meta["dtypes"] else None,
        notes=f"Loaded from GeoTIFF; valid pixels: {valid_count}/{h * w}",
    )

    return Observation(metadata=metadata, bands=bands, valid_mask=valid_mask)
