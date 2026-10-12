# Micro-Reservoir Intelligence

> **Automated multispectral satellite water extraction, surface area estimation, and multi-temporal storage decline detection on CPU.**

[![Python Version](https://img.shields.io/badge/python-3.11%20%7C%203.12-blue.svg)](https://www.python.org/)
[![Hardware](https://img.shields.io/badge/hardware-CPU--only%20laptop-green.svg)](#hardware-requirements)
[![Testing](https://img.shields.io/badge/pytest-97%20passed-brightgreen.svg)](#testing)

---

## 1. The Problem

Small water bodies—such as micro-reservoirs, farm ponds, percolation tanks, and village check dams—are the lifeblood of rural communities, rain-fed agriculture, and drought resilience across semi-arid regions. Despite their aggregate importance:
* **Overlooked by Global Monitoring**: Large-scale water observation platforms (e.g., HydroLAKES, Global Surface Water Explorer) prioritize large reservoirs (> 10 hectares), ignoring micro-water bodies (< 5 hectares).
* **Sparse Ground Gauging**: Rural check dams lack automated telemetric water-level sensors due to cost and maintenance constraints.
* **Invisible Depletion**: Communities and water managers often realize storage has reached critical depletion only after ponds run dry.

---

## 2. The Solution

**Micro-Reservoir Intelligence** provides an automated, lightweight, CPU-friendly solution that transforms open multispectral satellite observations (such as Sentinel-2 MSI and Landsat-8/9) into actionable water monitoring intelligence:
1. **Automated Water Extraction**: Extracts surface water boundaries using physics-based multispectral indices (NDWI, MNDWI, AWEI).
2. **Ground Area Quantification**: Translates classified water pixels into physical units (square meters, hectares, acres) with boundary mixed-pixel uncertainty modeling.
3. **Multi-Temporal Change Detection**: Compares baseline (e.g., post-monsoon full capacity) and comparison dates to quantify volume/area shifts.
4. **Early Warning System**: Flags significant surface water shrinkage (`potential_decline`) and triggers tiered operational alerts (CRITICAL, WARNING, INFO).
5. **Zero External API / No GPU Requirement**: Runs entirely on a standard CPU-only laptop without heavy deep learning frameworks, databases, or external network dependencies.

---

## 3. System Workflow

```
[Satellite Multispectral Bands: Green, NIR, SWIR, Red]
                       │
                       ▼
         ┌───────────────────────────┐
         │  1. Ingestion & Quality   │ ──> Checks shapes, cloud cover %,
         │     Validation Checks     │     NaN/Inf bounds, core bands
         └───────────────────────────┘
                       │
                       ▼
         ┌───────────────────────────┐
         │ 2. Spectral Water Index   │ ──> Computes NDWI / MNDWI / AWEI;
         │     & Threshold Masking   │     applies water threshold (>= 0.0)
         └───────────────────────────┘
                       │
                       ▼
         ┌───────────────────────────┐
         │ 3. Surface Area & Bounds  │ ──> Calculates area (m², ha, acres);
         │        Estimation         │     models boundary uncertainty
         └───────────────────────────┘
                       │
                       ▼
         ┌───────────────────────────┐
         │ 4. Multi-Temporal Change  │ ──> Calculates % delta & status:
         │         Detection         │     (stable, potential_decline, ...)
         └───────────────────────────┘
                       │
                       ▼
         ┌───────────────────────────┐
         │ 5. Operational Alerts &   │ ──> Categorical 2D transition maps,
         │    Dashboard Reporting    │     KPI cards, prioritized warnings
         └───────────────────────────┘
```

---

## 4. Architecture & Central Statuses

Detailed system architecture diagrams and API contracts are documented in:
* [Architecture Documentation](docs/architecture.md)
* [API & Shared Contracts](docs/api-contract.md)
* [Demonstration Guide](docs/demo-script.md)
* [Validation Report](docs/validation-report.md)

### Central Status Definitions
Multi-temporal comparisons assign one of five standardized states:
* `stable`: Surface area remains within normal variation bounds ($-10\% < \Delta < +10\%$).
* `potential_decline`: Significant water shrinkage detected ($\Delta \le -10\%$).
* `potential_increase`: Storage expansion or inflow detected ($\Delta \ge +10\%$).
* `insufficient_data`: High cloud cover ($> 20\%$) or low valid data coverage ($< 70\%$).
* `invalid_comparison`: Incompatible geometries, spatial dimensions, or coordinate reference frames.

---

## 5. Installation & Virtual Environment Setup

### Prerequisites
* Operating System: Windows, macOS, or Linux
* Python: Version **3.11** or **3.12**
* Hardware: Standard CPU laptop (no GPU or CUDA needed)

### Step 1: Create Virtual Environment

Using standard Python `venv`:
```bash
# Windows
python -m venv .venv
.venv\Scripts\activate

# macOS / Linux
python3 -m venv .venv
source .venv/bin/activate
```

*(Alternatively, using `uv` for instant environment provisioning)*:
```bash
uv venv .venv --python 3.12
.venv\Scripts\activate
```

### Step 2: Install Pinned Dependencies

```bash
pip install -r requirements.txt
```

Core pinned libraries:
* `rasterio>=1.3.10` (Geospatial raster I/O)
* `numpy>=1.26.4,<2.3.0` (Vectorized numerical mathematics)
* `pandas>=2.2.2` (Tabular metadata & time-series)
* `streamlit>=1.36.0` (Interactive web UI)
* `matplotlib>=3.9.0` & `plotly>=5.22.0` (Visualizations)
* `pytest>=8.2.0` (Automated testing suite)

---

## 6. Launching the Interactive Dashboard

Launch the Streamlit web dashboard in your local browser:

```bash
streamlit run app.py
```

Or using python module syntax:
```bash
python -m streamlit run app.py
```

The application will open automatically at `http://localhost:8501`.

### Dashboard Input Modes & Expected Formats

1. **📁 Mode 1: Local GeoTIFF Files**:
   * **Reservoir Identifier**: User-defined water body name or code (e.g., `RES-001`, `Gudibande Tank`).
   * **Baseline Observation**:
     * Scene ID & Acquisition Date (`YYYY-MM-DD`).
     * Layout Option A: *Separate Single-Band Files* (Paths to Sentinel-2 Band 3 Green `.tif` and Band 8 NIR `.tif`).
     * Layout Option B: *Multiband GeoTIFF* (Path to multi-channel `.tif` plus explicit 1-indexed band numbers, e.g., Green: `1`, NIR: `2`).
     * Optional: External cloud mask `.tif` path.
   * **Follow-up (Comparison) Observation**:
     * Matching layout specifications and paths for the second acquisition date.
   * *Note*: The baseline date must strictly precede the comparison date, and both rasters must share matching dimensions and projected CRS.

2. **🧪 Mode 2: Synthetic Demonstration Scenarios (Benchmark Exploration)**:
   * Select from 4 pre-configured synthetic multi-temporal scenarios:
     * `Seasonal Reservoir Drawdown`: 67% area shrinkage (`POTENTIAL_DECLINE`).
     * `Monsoon Inflow Recharge`: Significant storage expansion (`POTENTIAL_INCREASE`).
     * `Controlled Stable Storage`: Minor fluctuation within ±10% (`STABLE`).
     * `Cloud Obscuration Deficit`: 68% cloud cover (`INSUFFICIENT_DATA`).
   * *Data Honesty*: Synthetic benchmark data is visibly labeled with a warning banner indicating simulated test samples, NOT real satellite observations.

### Dashboard Export Options
* **📄 CSV Report Export**: Structured metric-by-metric breakdown of baseline and comparison surface area ($m^2$ and ha), percentage shifts, operational status, and hydrological disclaimers.
* **📋 JSON Report Export**: Machine-readable payload containing full observation metadata, change metrics, active alerts, and diagnostic caveats.

---

## 7. Command-Line Demo Runner

To run automated end-to-end evaluation across all test scenarios in the terminal without opening a browser:

```bash
python scripts/run_demo.py
```

Generated summary metrics are serialized to `data/processed/demo_summary.json`.

---

## 8. Input Data & Geospatial Requirements

| Requirement | Specification |
| :--- | :--- |
| **Format** | Cloud-Optimized GeoTIFF (`.tif`, `.tiff`) |
| **Bands Required** | Minimum: `green` (Sentinel-2 B03) and `nir` (Sentinel-2 B08) |
| **Ground Resolution** | Nominal 10 meters per pixel (or explicit affine transform) |
| **Coordinate Reference System (CRS)** | Projected planar CRS with linear metre units (e.g., UTM `EPSG:32643`). Geographic degree coordinates (e.g. `EPSG:4326`) are rejected to avoid distorted area measurements |
| **Radiometric Range** | Digital Numbers (`0` to `10000`) or surface reflectance (`0.0` to `1.0`) |
| **Cloud Contamination** | $\le 20.0\%$ cloud cover for reliable change status |

---

## 9. Testing & Quality Assurance

Execute the complete 97-test unit, integration, and dashboard test suite:

```bash
pytest -v
```

Execute with test coverage reporting:
```bash
pytest --cov=src.microreservoir tests/ -v
```

All 97 tests run 100% locally on CPU in ~5 seconds.

---

## 10. Assumptions, Hydrological Limitations, & Known Issues

### Scientific & Operational Assumptions
1. **Surface Area vs Bathymetric Volume**: Satellite multispectral indexing quantifies horizontal surface water extent ($m^2$ and ha). Surface area does not directly measure reservoir volume or water depth without an integrated Digital Elevation Model (DEM) and depth-capacity curve.
2. **Hydrological Caveat**: Surface-water extent changes reflect open surface water only. Reductions must **never** be used to infer groundwater depletion, aquifer overdraft, or confirmed regional drought without independent hydrological and meteorological data.
3. **Cloud Sensitivity & Limitation**: Optical sensors (Sentinel-2, Landsat) cannot penetrate cloud cover. Automatic internal cloud masking is not performed; clear-sky conditions must be visually verified or supplied via an external cloud mask raster (e.g. Sentinel-2 SCL layer). Occluded observations are flagged via pre-flight checks and classified as `insufficient_data` to suppress false decline alerts.
4. **Boundary Mixed-Pixel Uncertainty**: Narrow irrigation channels and small percolation ponds (< 1 ha) contain edge pixels with mixed water/soil signatures. Boundary uncertainty is calculated and reported alongside area estimates.

### Known Issues & Operational Status
* **Real Satellite Data Availability Status**: `AWAITING_GENUINE_DATA`. No genuine multi-gigabyte satellite imagery is bundled in the repository. Users can supply genuine local GeoTIFFs through Mode 1 in the dashboard without code changes. Synthetic benchmark fixtures are provided solely for offline mechanics testing.
* **Geographic CRS Rejection**: Rasters in unprojected angular coordinate systems (e.g. `EPSG:4326` in degrees) cannot be converted directly into ground square meters without planar projection. The system reports area as unavailable or rejects the raster rather than inventing inaccurate numbers. Users should reproject to a local UTM zone (e.g., `EPSG:32643`).
* **Zero-Baseline Delta**: When a baseline reservoir is completely dry ($0.0\text{ m}^2$), percentage change is mathematically undefined. The dashboard displays `N/A (Baseline Area is Zero)` rather than dividing by zero or raising an error.
* **Pixel Processing Safety Limit**: Rasters exceeding `max_pixel_limit` (default 25,000,000 pixels / 5000×5000) raise `RasterReadError` to prevent out-of-memory crashes on laptop hardware. Users must clip rasters to the reservoir Area of Interest (AOI) before ingestion.


