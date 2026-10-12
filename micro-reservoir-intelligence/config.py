"""Configuration module for Micro-Reservoir Intelligence.

Defines all system thresholds, status constants, default parameters, and
environment-variable overrides for CPU-bound water detection and multi-temporal
change analysis.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Final, Literal

# -----------------------------------------------------------------------------
# Central Status Constants
# -----------------------------------------------------------------------------
STATUS_STABLE: Final[str] = "stable"
STATUS_POTENTIAL_DECLINE: Final[str] = "potential_decline"
STATUS_POTENTIAL_INCREASE: Final[str] = "potential_increase"
STATUS_INSUFFICIENT_DATA: Final[str] = "insufficient_data"
STATUS_INVALID_COMPARISON: Final[str] = "invalid_comparison"

VALID_STATUSES: Final[tuple[str, ...]] = (
    STATUS_STABLE,
    STATUS_POTENTIAL_DECLINE,
    STATUS_POTENTIAL_INCREASE,
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_COMPARISON,
)

ChangeStatusType = Literal[
    "stable",
    "potential_decline",
    "potential_increase",
    "insufficient_data",
    "invalid_comparison",
]

# -----------------------------------------------------------------------------
# Default Paths
# -----------------------------------------------------------------------------
PACKAGE_ROOT: Final[Path] = Path(__file__).resolve().parent
DEFAULT_DATA_DIR: Final[Path] = PACKAGE_ROOT / "data"
DEFAULT_SAMPLES_DIR: Final[Path] = DEFAULT_DATA_DIR / "samples"
DEFAULT_PROCESSED_DIR: Final[Path] = DEFAULT_DATA_DIR / "processed"
DEFAULT_SAMPLE_MANIFEST: Final[Path] = DEFAULT_SAMPLES_DIR / "sample_manifest.json"


# -----------------------------------------------------------------------------
# Configuration Dataclass
# -----------------------------------------------------------------------------
@dataclass(frozen=True)
class AppConfig:
    """Immutable application settings and algorithm parameters."""

    # Run Mode & Logging
    environment: str = field(
        default_factory=lambda: os.getenv("ENVIRONMENT", "development")
    )
    log_level: str = field(
        default_factory=lambda: os.getenv("LOG_LEVEL", "INFO")
    )

    # Spectral Water Indices
    default_water_index: str = field(
        default_factory=lambda: os.getenv("DEFAULT_WATER_INDEX", "NDWI")
    )
    ndwi_threshold: float = field(
        default_factory=lambda: float(os.getenv("NDWI_WATER_THRESHOLD", "0.0"))
    )
    mndwi_threshold: float = field(
        default_factory=lambda: float(os.getenv("MNDWI_WATER_THRESHOLD", "0.0"))
    )
    awei_threshold: float = field(
        default_factory=lambda: float(os.getenv("AWEI_WATER_THRESHOLD", "0.0"))
    )

    # Change Detection & Alert Thresholds (Percentages)
    decline_threshold_percent: float = field(
        default_factory=lambda: float(os.getenv("ALERT_DECLINE_THRESHOLD_PERCENT", "-10.0"))
    )
    critical_decline_threshold_percent: float = field(
        default_factory=lambda: float(os.getenv("ALERT_CRITICAL_DECLINE_THRESHOLD_PERCENT", "-25.0"))
    )
    increase_threshold_percent: float = field(
        default_factory=lambda: float(os.getenv("ALERT_INCREASE_THRESHOLD_PERCENT", "10.0"))
    )

    # Quality Control Constraints
    max_cloud_cover_percent: float = field(
        default_factory=lambda: float(os.getenv("MAX_CLOUD_COVER_PERCENT", "20.0"))
    )
    min_valid_pixel_ratio: float = field(
        default_factory=lambda: float(os.getenv("MIN_VALID_PIXEL_RATIO", "0.70"))
    )
    min_reservoir_pixels: int = field(
        default_factory=lambda: int(os.getenv("MIN_RESERVOIR_PIXELS", "5"))
    )
    max_pixel_limit: int = field(
        default_factory=lambda: int(os.getenv("MAX_PIXEL_LIMIT", "25000000"))
    )

    # Geospatial Defaults
    default_pixel_resolution_m: float = field(
        default_factory=lambda: float(os.getenv("DEFAULT_PIXEL_RESOLUTION_M", "10.0"))
    )
    default_crs: str = field(
        default_factory=lambda: os.getenv("DEFAULT_CRS", "EPSG:32643")
    )

    # Storage and File Paths
    data_dir: Path = field(
        default_factory=lambda: Path(os.getenv("DATA_DIR", str(DEFAULT_DATA_DIR)))
    )
    samples_dir: Path = field(
        default_factory=lambda: Path(os.getenv("SAMPLES_DIR", str(DEFAULT_SAMPLES_DIR)))
    )
    processed_dir: Path = field(
        default_factory=lambda: Path(os.getenv("PROCESSED_OUTPUT_DIR", str(DEFAULT_PROCESSED_DIR)))
    )
    sample_manifest_path: Path = field(
        default_factory=lambda: Path(os.getenv("SAMPLE_MANIFEST_PATH", str(DEFAULT_SAMPLE_MANIFEST)))
    )

    # Unit Conversion Factors
    m2_to_hectare: float = 0.0001
    m2_to_acre: float = 0.000247105

    def get_index_threshold(self, method: str) -> float:
        """Return the detection threshold associated with a specific index method."""
        normalized = method.strip().upper()
        if normalized == "NDWI":
            return self.ndwi_threshold
        elif normalized == "MNDWI":
            return self.mndwi_threshold
        elif normalized == "AWEI":
            return self.awei_threshold
        raise ValueError(
            f"Unsupported spectral water index '{method}'. Supported methods: NDWI, MNDWI, AWEI."
        )


# Global default configuration instance
DEFAULT_CONFIG: Final[AppConfig] = AppConfig()
