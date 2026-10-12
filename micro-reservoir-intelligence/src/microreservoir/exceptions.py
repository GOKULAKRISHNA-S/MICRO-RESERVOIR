"""Custom exceptions for Micro-Reservoir Intelligence.

Provides a structured exception hierarchy for raster I/O, geospatial verification,
metadata integrity, temporal ordering, and path security.
"""

from __future__ import annotations


class MicroReservoirError(Exception):
    """Base exception for all Micro-Reservoir Intelligence errors."""


class RasterReadError(MicroReservoirError):
    """Raised when a raster file cannot be opened or parsed."""


class CorruptRasterError(RasterReadError):
    """Raised when a raster file is corrupted, truncated, or has unreadable headers."""


class UnsupportedRasterError(RasterReadError):
    """Raised when a file format or structure is unsupported."""


class MissingBandError(MicroReservoirError):
    """Raised when one or more required spectral bands are not found."""


class MissingCRSError(MicroReservoirError):
    """Raised when a geospatial raster lacks a Coordinate Reference System."""


class IncompatibleGridError(MicroReservoirError):
    """Raised when two observations have mismatched spatial grids, dimensions, or CRS."""


class InvalidDateError(MicroReservoirError):
    """Raised when an observation acquisition date is malformed or invalid."""


class TemporalOrderError(InvalidDateError):
    """Raised when the baseline observation date does not precede the follow-up date."""


class PathTraversalError(MicroReservoirError):
    """Raised when an unsafe file path or path traversal attempt is detected."""


class NoDataError(MicroReservoirError):
    """Raised when an observation has no valid data (100% NoData, NaN, or masked)."""
