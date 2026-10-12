"""Typed schemas and data contracts for Micro-Reservoir Intelligence.

Provides structured dataclasses and type definitions for multispectral observations,
validation reports, spectral water detection, surface area estimations, multi-temporal
change comparisons, alerts, and dashboard summaries.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from config import (
    STATUS_STABLE,
    STATUS_POTENTIAL_DECLINE,
    STATUS_POTENTIAL_INCREASE,
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_COMPARISON,
    VALID_STATUSES,
    ChangeStatusType,
)


# -----------------------------------------------------------------------------
# Enumerations
# -----------------------------------------------------------------------------
class ChangeStatus(str, Enum):
    """Central status values for multi-temporal reservoir comparison."""

    STABLE = STATUS_STABLE
    POTENTIAL_DECLINE = STATUS_POTENTIAL_DECLINE
    POTENTIAL_INCREASE = STATUS_POTENTIAL_INCREASE
    INSUFFICIENT_DATA = STATUS_INSUFFICIENT_DATA
    INVALID_COMPARISON = STATUS_INVALID_COMPARISON

    @classmethod
    def is_valid(cls, value: str) -> bool:
        """Check if a string matches any recognized status."""
        return value in VALID_STATUSES


class WaterIndexMethod(str, Enum):
    """Supported spectral water index algorithms."""

    NDWI = "NDWI"      # McFeeters (Green - NIR) / (Green + NIR)
    MNDWI = "MNDWI"    # Xu (Green - SWIR1) / (Green + SWIR1)
    AWEI = "AWEI"      # Feyisa Automated Water Extraction Index


class AlertSeverity(str, Enum):
    """Severity ratings for reservoir change alerts."""

    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class ChangePixelClass(int, Enum):
    """Categorical values for 2D change detection raster masks."""

    NON_WATER = 0        # Persistent dry land / non-water
    PERSISTENT_WATER = 1 # Water observed in both dates
    WATER_LOST = 2       # Water in baseline, dry in comparison (decline)
    WATER_GAINED = 3     # Dry in baseline, water in comparison (increase)
    INVALID = 255        # Cloud / nodata in at least one date


# -----------------------------------------------------------------------------
# Observation & Input Contracts
# -----------------------------------------------------------------------------
@dataclass
class ObservationMetadata:
    """Metadata identifying a single satellite observation scene."""

    scene_id: str
    date: str  # ISO-8601 format: YYYY-MM-DD
    sensor: str = "Sentinel-2"
    pixel_resolution_m: float = 10.0
    crs: str = "EPSG:32643"
    bounds: Tuple[float, float, float, float] = (0.0, 0.0, 1000.0, 1000.0)  # (min_x, min_y, max_x, max_y)
    cloud_cover_percent: Optional[float] = None
    cloud_assessed: bool = False
    transform: Optional[Tuple[float, float, float, float, float, float]] = None
    dimensions: Optional[Tuple[int, int]] = None
    nodata_value: Optional[float] = None
    dtype: Optional[str] = None
    notes: Optional[str] = None


@dataclass
class Observation:
    """Multispectral observation containing metadata and 2D band arrays."""

    metadata: ObservationMetadata
    bands: Dict[str, np.ndarray]  # Map of band names (e.g., 'green', 'nir', 'swir1') to 2D arrays
    valid_mask: Optional[np.ndarray] = None  # Optional 2D boolean array (True = valid pixel)

    def shape(self) -> Tuple[int, int]:
        """Return the spatial shape (rows, cols) of the observation bands."""
        if not self.bands:
            return (0, 0)
        first_band = next(iter(self.bands.values()))
        return first_band.shape


# -----------------------------------------------------------------------------
# Validation & Quality Assurance Contracts
# -----------------------------------------------------------------------------
@dataclass
class QualityCheckReport:
    """Granular quality inspection metrics for satellite raster data."""

    cloud_cover_percent: Optional[float]
    nodata_pixel_count: int
    valid_pixel_count: int
    total_pixel_count: int
    valid_pixel_ratio: float
    passed_quality_checks: bool
    cloud_assessed: bool = True
    quality_warnings: List[str] = field(default_factory=list)


@dataclass
class ValidationResult:
    """Validation outcome assessing structural and radiometric integrity."""

    is_valid: bool
    status: str  # "valid", "invalid", "warning"
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    quality_report: Optional[QualityCheckReport] = None


# -----------------------------------------------------------------------------
# Water Detection & Area Estimation Contracts
# -----------------------------------------------------------------------------
@dataclass
class WaterDetectionResult:
    """Output generated from spectral water indexing and threshold segmentation."""

    water_mask: np.ndarray  # 2D boolean ndarray (True = detected water)
    index_map: np.ndarray   # 2D float32 ndarray (computed spectral index values)
    index_method: WaterIndexMethod
    threshold: float
    water_pixel_count: int
    total_valid_pixels: int
    water_fraction: float
    valid_mask: Optional[np.ndarray] = None  # 2D boolean ndarray (True = valid pixel)
    summary_statistics: Dict[str, float] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)

    @property
    def ndwi_map(self) -> np.ndarray:
        """Alias returning the continuous spectral index array."""
        return self.index_map

    @property
    def valid_pixel_mask(self) -> Optional[np.ndarray]:
        """Alias returning the boolean valid pixel mask."""
        return self.valid_mask


@dataclass
class AreaEstimate:
    """Quantified water surface area and associated measurement uncertainty."""

    pixel_count: int
    pixel_resolution_m: float
    pixel_area_m2: float
    water_area_m2: float
    water_area_hectares: float
    water_area_acres: float
    uncertainty_range_hectares: Tuple[float, float]  # Lower and upper confidence bounds
    is_available: bool = True
    crs: Optional[str] = None
    warnings: List[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Change Detection & Comparison Contracts
# -----------------------------------------------------------------------------
@dataclass
class ChangeComparisonResult:
    """Bi-temporal comparison analyzing surface water shifts between two observations."""

    baseline_id: str
    baseline_date: str
    comparison_id: str
    comparison_date: str
    baseline_area_ha: float
    comparison_area_ha: float
    area_delta_ha: float
    area_delta_percent: Optional[float]
    status: ChangeStatusType
    confidence_score: float  # 0.0 to 1.0 confidence index
    change_mask: Optional[np.ndarray] = None  # 2D uint8 ndarray matching ChangePixelClass
    details: str = ""
    baseline_area_m2: Optional[float] = None
    comparison_area_m2: Optional[float] = None
    area_delta_m2: Optional[float] = None
    quality_passed: bool = True
    warnings: List[str] = field(default_factory=list)


# -----------------------------------------------------------------------------
# Alerting & Reporting Contracts
# -----------------------------------------------------------------------------
@dataclass
class AlertItem:
    """Actionable warning or notification regarding reservoir state changes."""

    severity: AlertSeverity
    title: str
    message: str
    action_recommended: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


@dataclass
class AnalysisResult:
    """End-to-end analytical package consolidating all pipeline outputs."""

    baseline_observation: ObservationMetadata
    comparison_observation: ObservationMetadata
    baseline_detection: WaterDetectionResult
    comparison_detection: WaterDetectionResult
    baseline_area: AreaEstimate
    comparison_area: AreaEstimate
    comparison: ChangeComparisonResult
    alerts: List[AlertItem] = field(default_factory=list)
    summary_metrics: Dict[str, Any] = field(default_factory=dict)
    generated_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
