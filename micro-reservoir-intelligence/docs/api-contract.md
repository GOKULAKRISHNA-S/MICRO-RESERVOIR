# API & Shared Contract Specification

This document details the functional contracts, method signatures, inputs, outputs, exceptions, measurement units, and status codes established for the **Micro-Reservoir Intelligence** core pipeline.

---

## Central Status Definitions

All multi-temporal change detection results classify observations into one of five mutually exclusive states:

| Status Code | Meaning | Standard Trigger Criteria |
| :--- | :--- | :--- |
| `stable` | Storage volume and surface area remain within normal seasonal bounds. | $-10.0\% < \Delta_{\text{percent}} < +10.0\%$ |
| `potential_decline` | Water surface area has contracted beyond the alert threshold. | $\Delta_{\text{percent}} \le -10.0\%$ |
| `potential_increase` | Water surface area has expanded beyond the growth threshold. | $\Delta_{\text{percent}} \ge +10.0\%$ |
| `insufficient_data` | Excessive cloud coverage or nodata mask prevented conclusive assessment. | Cloud cover $> 20.0\%$ or valid pixel coverage $< 70.0\%$ |
| `invalid_comparison` | Observations cannot be compared due to mismatched spatial dimensions or corrupted matrices. | Raster shape mismatch ($H_1 \ne H_2$ or $W_1 \ne W_2$) |

---

## Core Function Specifications

### 1. `validate_observation`

```python
def validate_observation(
    obs: Observation,
    cfg: Optional[AppConfig] = None
) -> ValidationResult
```

* **Purpose**: Inspects incoming multispectral observations for dimensional integrity, band presence, radiometric validities, and cloud obstruction.
* **Inputs**:
  * `obs` (`Observation`): Dataclass containing `metadata` (`ObservationMetadata`), `bands` (`Dict[str, np.ndarray]`), and optional `valid_mask` (`np.ndarray`).
  * `cfg` (`Optional[AppConfig]`): Optional application configuration overrides.
* **Outputs**:
  * `ValidationResult`:
    * `is_valid` (`bool`): `True` if no critical errors exist; `False` if fatal defects are detected.
    * `status` (`str`): `"valid"`, `"invalid"`, or `"warning"`.
    * `errors` (`List[str]`): List of blocking errors (e.g., missing core bands, shape mismatch).
    * `warnings` (`List[str]`): Quality warnings (e.g., cloud cover approaching limit).
    * `quality_report` (`Optional[QualityCheckReport]`): Granular metrics (valid pixel counts, valid ratio).
* **Exceptions**: Does not raise exceptions; captures all validation failures within `ValidationResult.errors`.
* **Units**: Cloud cover in percentage (`%`), pixel dimensions in counts.

---

### 2. `detect_water`

```python
def detect_water(
    obs: Observation,
    method: Optional[WaterIndexMethod] = None,
    threshold: Optional[float] = None,
    cfg: Optional[AppConfig] = None
) -> WaterDetectionResult
```

* **Purpose**: Calculates spectral water indices and generates a binary classification mask of surface water.
* **Inputs**:
  * `obs` (`Observation`): Valid observation with required spectral bands (`green`, `nir`, and optionally `swir1`).
  * `method` (`Optional[WaterIndexMethod]`): Algorithm identifier: `NDWI`, `MNDWI`, or `AWEI`. Default: `NDWI`.
  * `threshold` (`Optional[float]`): Cutoff value above which pixels are categorized as water. Default: `0.0`.
  * `cfg` (`Optional[AppConfig]`): Application configuration.
* **Outputs**:
  * `WaterDetectionResult`:
    * `water_mask` (`np.ndarray`): 2D boolean array (`True` for water, `False` for land).
    * `index_map` (`np.ndarray`): 2D float32 array with computed continuous index values `[-1.0, 1.0]`.
    * `index_method` (`WaterIndexMethod`): Method utilized.
    * `threshold` (`float`): Applied cutoff value.
    * `water_pixel_count` (`int`): Count of positive water pixels.
    * `total_valid_pixels` (`int`): Count of non-masked, non-cloudy pixels.
    * `water_fraction` (`float`): Ratio of water pixels to valid pixels `[0.0, 1.0]`.
* **Exceptions**:
  * `ValueError`: Raised if required bands for the selected index are missing.
* **Units**: Indices are unitless ratios bounded between `[-1.0, 1.0]`.

---

### 3. `estimate_area`

```python
def estimate_area(
    detection: WaterDetectionResult,
    pixel_resolution_m: float
) -> AreaEstimate
```

* **Purpose**: Quantifies ground surface water coverage based on pixel resolution and calculates boundary uncertainty.
* **Inputs**:
  * `detection` (`WaterDetectionResult`): Output from `detect_water`.
  * `pixel_resolution_m` (`float`): Ground sampling distance in linear meters per pixel (must be $> 0$).
* **Outputs**:
  * `AreaEstimate`:
    * `pixel_count` (`int`): Detected water pixels.
    * `pixel_resolution_m` (`float`): Input resolution (e.g., `10.0`).
    * `pixel_area_m2` (`float`): Area of single pixel in square meters ($100.0\text{ m}^2$ for 10m).
    * `water_area_m2` (`float`): Total surface area in square meters ($\text{m}^2$).
    * `water_area_hectares` (`float`): Total surface area in hectares ($\text{ha}$).
    * `water_area_acres` (`float`): Total surface area in international acres.
    * `uncertainty_range_hectares` (`Tuple[float, float]`): `(lower_bound_ha, upper_bound_ha)` representing boundary mixed-pixel uncertainty.
* **Exceptions**:
  * `ValueError`: Raised if `pixel_resolution_m <= 0` or `water_pixel_count < 0`.
* **Units**: Meters ($\text{m}$), square meters ($\text{m}^2$), hectares ($\text{ha}$), acres.

---

### 4. `compare_observations`

```python
def compare_observations(
    baseline_obs: Observation,
    comparison_obs: Observation,
    baseline_det: WaterDetectionResult,
    comparison_det: WaterDetectionResult,
    cfg: Optional[AppConfig] = None
) -> ChangeComparisonResult
```

* **Purpose**: Performs bi-temporal comparison between baseline ($t_0$) and comparison ($t_1$) observations.
* **Inputs**:
  * `baseline_obs` (`Observation`): Earlier reference observation.
  * `comparison_obs` (`Observation`): Subsequent monitoring observation.
  * `baseline_det` (`WaterDetectionResult`): Baseline detection output.
  * `comparison_det` (`WaterDetectionResult`): Comparison detection output.
  * `cfg` (`Optional[AppConfig]`): Application configuration.
* **Outputs**:
  * `ChangeComparisonResult`:
    * `baseline_id` (`str`), `baseline_date` (`str`): Baseline identifiers.
    * `comparison_id` (`str`), `comparison_date` (`str`): Comparison identifiers.
    * `baseline_area_ha` (`float`), `comparison_area_ha` (`float`): Areas in hectares.
    * `area_delta_ha` (`float`): Absolute shift in hectares ($\text{comp} - \text{base}$).
    * `area_delta_percent` (`float`): Percentage shift $(\Delta / \text{base}) \times 100$.
    * `status` (`ChangeStatusType`): Assigned status state.
    * `confidence_score` (`float`): Reliability score between `[0.0, 1.0]`.
    * `change_mask` (`Optional[np.ndarray]`): Categorical 2D transition raster (0=non-water, 1=persistent water, 2=water lost, 3=water gained, 255=invalid).
    * `details` (`str`): Human-readable explanatory summary.
* **Exceptions**: Handles shape mismatches and quality deficits internally by returning `invalid_comparison` or `insufficient_data`.
* **Units**: Hectares ($\text{ha}$), percentages ($\%$), confidence (`0.0` to `1.0`).

---

### 5. `build_dashboard_data`

```python
def build_dashboard_data(
    analysis: AnalysisResult
) -> Dict[str, Any]
```

* **Purpose**: Serializes complete pipeline output into JSON-compatible primitives for dashboard rendering.
* **Inputs**:
  * `analysis` (`AnalysisResult`): Output from `run_analysis`.
* **Outputs**:
  * `Dict[str, Any]` containing keys:
    * `"status"`: Central status string.
    * `"metrics"`: List of formatted KPI metric card dictionaries.
    * `"details"`: Summary paragraph text.
    * `"alerts"`: List of serialized alert objects.
    * `"summary"`: Machine-readable summary statistics.
    * `"generated_at"`: ISO-8601 UTC timestamp.

---

### 6. `run_analysis`

```python
def run_analysis(
    baseline_obs: Observation,
    comparison_obs: Observation,
    cfg: Optional[AppConfig] = None
) -> AnalysisResult
```

* **Purpose**: Orchestrates the complete end-to-end execution pipeline from raw observations to alerts.
* **Inputs**:
  * `baseline_obs` (`Observation`): Baseline scene.
  * `comparison_obs` (`Observation`): Comparison scene.
  * `cfg` (`Optional[AppConfig]`): Optional application configuration.
* **Outputs**:
  * `AnalysisResult`: Complete analytical container grouping metadata, detection masks, area estimates, comparison outcome, alerts, and summary metrics.

---

### 7. `load_geotiff_observation`

```python
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
) -> Observation
```

* **Purpose**: Safely loads local multispectral GeoTIFF files into an `Observation` dataclass with automatic NoData, cloud mask integration, and memory-safety pixel limit enforcement.
* **Supported Layouts**:
  * **Single-Band Layout**: Pass `band_files={'green': path, 'nir': path}`.
  * **Multiband Layout**: Pass `multiband_file=path` with explicit `band_mapping={'green': 1, 'nir': 2}` (1-indexed).
* **Inputs**:
  * `scene_id` (`str`): Observation identifier.
  * `date_str` (`str`): Sensing date in strict ISO-8601 (`YYYY-MM-DD`).
  * `band_files` (`Optional[Dict[str, Union[str, Path]]]`): Mapping of spectral bands to separate GeoTIFF files.
  * `multiband_file` (`Optional[Union[str, Path]]`): Path to composite GeoTIFF.
  * `band_mapping` (`Optional[Dict[str, int]]`): Mandatory 1-indexed band numbers when using `multiband_file`.
  * `cloud_mask_file` (`Optional[Union[str, Path]]`): Optional external cloud mask (non-zero values treated as cloud/shadow).
  * `sensor` (`str`): Sensor identifier (default: `"Sentinel-2"`).
  * `base_dir` (`Optional[Union[str, Path]]`): Optional boundary directory to prevent path traversal.
  * `max_pixels` (`Optional[int]`): Optional maximum allowed total pixels (default: `25,000,000` from `AppConfig`).
* **Outputs**:
  * `Observation`: Initialized with metadata, float32 band arrays, and boolean `valid_mask`.
* **Exceptions**:
  * `PathTraversalError`: If a file path attempts directory traversal or contains null bytes.
  * `FileNotFoundError`: If any raster file does not exist.
  * `CorruptRasterError`: If a raster file is empty or corrupted.
  * `MissingCRSError`: If a raster lacks an explicit Coordinate Reference System.
  * `MissingBandError`: If required bands (`green`, `nir`) or band mapping is omitted.
  * `IncompatibleGridError`: If single-band rasters have mismatched dimensions or CRS.
  * `NoDataError`: If an observation contains 100% NoData/invalid pixels.

---

### 8. `validate_grid_compatibility`

```python
def validate_grid_compatibility(
    obs1: Observation,
    obs2: Observation,
    tolerance: float = 1e-3,
) -> None
```

* **Purpose**: Validates that two observations share an identical projected CRS, spatial dimensions, pixel resolution, and grid alignment.
* **Exceptions**:
  * `IncompatibleGridError`: If CRS, shape, resolution, or affine transforms do not match within `tolerance`. Rejects observations rather than silently warping or resizing pixels.

---

### 9. `validate_temporal_order`

```python
def validate_temporal_order(
    baseline_date_str: str,
    comparison_date_str: str,
) -> None
```

* **Purpose**: Verifies that the baseline observation acquisition date strictly precedes the follow-up comparison date.
* **Exceptions**:
  * `InvalidDateError`: If either date string is malformed or not a valid ISO-8601 calendar date.
  * `TemporalOrderError`: If `baseline_date >= comparison_date`.

### 10. `export_report_csv`

```python
def export_report_csv(
    analysis: AnalysisResult,
    reservoir_id: str = "RESERVOIR",
) -> str
```

* **Purpose**: Serializes complete multi-temporal analysis results into a structured, RFC 4180-compliant CSV report.
* **Inputs**:
  * `analysis` (`AnalysisResult`): Output generated from `run_analysis`.
  * `reservoir_id` (`str`): Target reservoir identifier string.
* **Outputs**:
  * `str`: CSV-formatted text containing metrics, source observation metadata, operational status, quality flags, active alerts, and hydrological disclaimers.

---

### 11. `export_report_json`

```python
def export_report_json(
    analysis: AnalysisResult,
    reservoir_id: str = "RESERVOIR",
) -> str
```

* **Purpose**: Serializes complete multi-temporal analysis results into an indented, machine-readable JSON document.
* **Inputs**:
  * `analysis` (`AnalysisResult`): Output generated from `run_analysis`.
  * `reservoir_id` (`str`): Target reservoir identifier string.
* **Outputs**:
  * `str`: JSON-formatted text containing hierarchical metadata, observation details, uncertainty bounds, alerts, and assumptions.

---

## Exception Hierarchy

All custom exceptions inherit from `MicroReservoirError`:

```
MicroReservoirError
├── RasterReadError
│   ├── CorruptRasterError
│   └── UnsupportedRasterError
├── MissingBandError
├── MissingCRSError
├── IncompatibleGridError
├── InvalidDateError
│   └── TemporalOrderError
├── PathTraversalError
└── NoDataError
```
