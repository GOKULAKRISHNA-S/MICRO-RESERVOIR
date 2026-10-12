"""Micro-Reservoir Intelligence package.

Detect surface water in multispectral satellite imagery, estimate water-covered area,
compare multi-temporal dates, and flag potential reservoir declines.
"""

from __future__ import annotations

from config import (
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_COMPARISON,
    STATUS_POTENTIAL_DECLINE,
    STATUS_POTENTIAL_INCREASE,
    STATUS_STABLE,
    VALID_STATUSES,
    AppConfig,
    DEFAULT_CONFIG,
)
from src.microreservoir.alerts import generate_alerts
from src.microreservoir.area_estimation import estimate_area
from src.microreservoir.change_detection import compare_observations
from src.microreservoir.exceptions import (
    CorruptRasterError,
    IncompatibleGridError,
    InvalidDateError,
    MicroReservoirError,
    MissingBandError,
    MissingCRSError,
    NoDataError,
    PathTraversalError,
    RasterReadError,
    TemporalOrderError,
    UnsupportedRasterError,
)
from src.microreservoir.geotiff import (
    load_geotiff_observation,
    read_geotiff_metadata,
    validate_grid_compatibility,
    validate_observation_date,
    validate_safe_path,
    validate_temporal_order,
)
from src.microreservoir.preprocessing import (
    create_false_color_composite,
    create_rgb_composite,
    normalize_band,
)
from src.microreservoir.reporting import (
    build_dashboard_data,
    export_report_csv,
    export_report_json,
    run_analysis,
)
from src.microreservoir.schemas import (
    AlertItem,
    AlertSeverity,
    AnalysisResult,
    AreaEstimate,
    ChangeComparisonResult,
    ChangePixelClass,
    ChangeStatus,
    Observation,
    ObservationMetadata,
    QualityCheckReport,
    ValidationResult,
    WaterDetectionResult,
    WaterIndexMethod,
)
from src.microreservoir.validation import validate_observation
from src.microreservoir.water_detection import (
    compute_awei,
    compute_mndwi,
    compute_ndwi,
    detect_water,
)

__version__ = "0.2.0"

__all__ = [
    # Shared Core Pipeline Functions
    "validate_observation",
    "detect_water",
    "estimate_area",
    "compare_observations",
    "build_dashboard_data",
    "export_report_csv",
    "export_report_json",
    "run_analysis",
    # GeoTIFF & Ingestion Functions
    "load_geotiff_observation",
    "read_geotiff_metadata",
    "validate_safe_path",
    "validate_observation_date",
    "validate_temporal_order",
    "validate_grid_compatibility",
    # Supporting Utilities
    "generate_alerts",
    "normalize_band",
    "create_rgb_composite",
    "create_false_color_composite",
    "compute_ndwi",
    "compute_mndwi",
    "compute_awei",
    # Central Statuses
    "STATUS_STABLE",
    "STATUS_POTENTIAL_DECLINE",
    "STATUS_POTENTIAL_INCREASE",
    "STATUS_INSUFFICIENT_DATA",
    "STATUS_INVALID_COMPARISON",
    "VALID_STATUSES",
    # Exceptions
    "MicroReservoirError",
    "RasterReadError",
    "CorruptRasterError",
    "UnsupportedRasterError",
    "MissingBandError",
    "MissingCRSError",
    "IncompatibleGridError",
    "InvalidDateError",
    "TemporalOrderError",
    "PathTraversalError",
    "NoDataError",
    # Schemas and Enums
    "ChangeStatus",
    "WaterIndexMethod",
    "AlertSeverity",
    "ChangePixelClass",
    "ObservationMetadata",
    "Observation",
    "QualityCheckReport",
    "ValidationResult",
    "WaterDetectionResult",
    "AreaEstimate",
    "ChangeComparisonResult",
    "AlertItem",
    "AnalysisResult",
    # Config
    "AppConfig",
    "DEFAULT_CONFIG",
]
