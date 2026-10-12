# User Operational Guide: Micro-Reservoir Intelligence
## Step-by-Step Instructions for Ingestion, Analysis, and Decision Support

---

## 1. Introduction

**Micro-Reservoir Intelligence** is an automated, CPU-friendly software system designed to analyze multispectral satellite imagery, detect open surface water bodies, calculate ground area coverage in physical units, and track multi-temporal storage changes.

This guide provides step-by-step instructions for:
- Setting up the Python virtual environment and verifying dependencies.
- Running the automated test suite and CLI demonstration runner.
- Downloading genuine Sentinel-2 satellite imagery over the Mettur Reservoir study area.
- Launching and operating the interactive Streamlit web dashboard.
- Configuring spectral indices and operational alert thresholds.
- Interpreting analytical outputs, heatmaps, transition maps, and quality checks.
- Exporting structured assessment reports in CSV and JSON formats.

---

## 2. System Prerequisites & Environment Setup

### 2.1 Hardware and Operating System
- **Operating System**: Windows 10/11 (64-bit), Linux (x86_64 or aarch64), or macOS.
- **Hardware**: Standard laptop CPU (Intel Core, AMD Ryzen, or Apple Silicon). No GPU or CUDA required.
- **Memory**: 4 GB RAM minimum (8 GB recommended).
- **Disk Space**: At least 500 MB free disk space.

### 2.2 Python Virtual Environment
The system runs on **Python 3.12** (or Python 3.11). An isolated virtual environment (`.venv`) is located at the workspace root.

#### Activating the Virtual Environment on Windows (PowerShell)
```powershell
# From the project root (C:\Users\gokul\Documents\MICRO-RESERVOIR):
.\.venv\Scripts\Activate.ps1
```

If script execution is disabled in PowerShell, activate the environment using module invocation directly without altering system execution policies:
```powershell
# Invoke python directly via the virtual environment interpreter:
.\.venv\Scripts\python.exe --version
```

### 2.3 Dependency Verification
Verify that required libraries are present:
```powershell
.\.venv\Scripts\python.exe -c "import rasterio, streamlit, numpy, pytest, pandas, plotly, matplotlib; print('All core dependencies verified successfully!')"
```

---

## 3. Running Automated Tests

Before running operational analyses, verify software integrity using the automated test suite:

### 3.1 Running Pytest from Workspace Root
```powershell
# From C:\Users\gokul\Documents\MICRO-RESERVOIR:
.\.venv\Scripts\python.exe -m pytest -v
```
*Expected Result*: `204 passed in ~10 seconds` (102 tests discovered in root `tests/` and 102 in nested `micro-reservoir-intelligence/tests/`).

### 3.2 Running Pytest from Nested Application Directory
```powershell
# From C:\Users\gokul\Documents\MICRO-RESERVOIR\micro-reservoir-intelligence:
cd micro-reservoir-intelligence
$env:PYTHONPATH = ".."
..\.venv\Scripts\python.exe -m pytest -v
```
*Expected Result*: `102 passed in ~4.4 seconds`.

---

## 4. Downloading Real Satellite Imagery (Mettur Reservoir)

A standalone downloader script (`download_mettur_sentinel2.py`) is provided in the project root to fetch genuine Sentinel-2 Level-2A imagery over the Mettur Reservoir region in Tamil Nadu, India.

### 4.1 Running the Downloader
> [!NOTE]
> The downloader requires an active internet connection to query the public AWS Earth Search STAC catalog. It does not require an API key or account credentials.

Run the script from the workspace root:
```powershell
.\.venv\Scripts\python.exe .\download_mettur_sentinel2.py
```

### 4.2 Downloader Execution Logic
1. **Catalog Query**: Queries `https://earth-search.aws.element84.com/v1/search` for the `sentinel-2-c1-l2a` collection intersecting bounding box `[77.72°E, 11.74°N, 77.90°E, 11.88°N]`.
2. **Compatible Pair Selection**: Finds two cloud-screened ($\le 35\%$) scenes on the same MGRS tile (`MGRS-43PHP`) separated by at least 30 days.
3. **Window Extraction**: Uses HTTP range requests to download only the cropped $1614 \times 1571$ pixel bounding window for Band 3 (Green) and Band 8 (NIR) directly from AWS S3 COGs, avoiding full 1-gigabyte tile downloads.
4. **Local Storage**: Saves four cropped GeoTIFF files and a verification manifest to `data/real_mettur/`:
   - `data/real_mettur/date1_2026-08-30_B03.tif` (Baseline Green, 3.7 MB)
   - `data/real_mettur/date1_2026-08-30_B08.tif` (Baseline NIR, 3.9 MB)
   - `data/real_mettur/date2_2026-09-29_B03.tif` (Follow-up Green, 3.6 MB)
   - `data/real_mettur/date2_2026-09-29_B08.tif` (Follow-up NIR, 4.0 MB)
   - `data/real_mettur/download_manifest.json` (Download log & verification manifest)

Once downloaded, all subsequent analysis runs completely offline.

---

## 5. Non-Interactive CLI Demo Runner

To evaluate the pipeline without opening a web browser, execute the command-line demo runner:

```powershell
.\.venv\Scripts\python.exe scripts/run_demo.py
```

The script evaluates all 4 pre-configured multi-temporal test scenarios:
- **Scenario 1 (Seasonal Drawdown)**: -67.0% shrinkage (`POTENTIAL_DECLINE`, `CRITICAL` alert).
- **Scenario 2 (Monsoon Recharge)**: +552.7% expansion (`POTENTIAL_INCREASE`, `INFO` alert).
- **Scenario 3 (Stable Regimen)**: -8.7% minor fluctuation (`STABLE`, `INFO` alert).
- **Scenario 4 (Cloud Obscuration)**: 68% cloud cover (`INSUFFICIENT_DATA`, `WARNING` alert).

Summary results are serialized to `data/processed/demo_summary.json`.

---

## 6. Operating the Interactive Streamlit Dashboard

### 6.1 Launching the Web App
From the nested application directory:
```powershell
cd micro-reservoir-intelligence
..\.venv\Scripts\python.exe -m streamlit run app.py
```

Or from the workspace root:
```powershell
.\.venv\Scripts\python.exe -m streamlit run app.py
```

The browser automatically opens to `http://localhost:8501`.

---

### 6.2 Mode 1: Local GeoTIFF Files (Real Satellite Analysis)

Use Mode 1 to process genuine Sentinel-2 satellite files stored on your local disk:

#### Step 1: Sidebar Setup
1. In the sidebar under **Input Data Source**, select **📁 Local GeoTIFF Files**.
2. **Reservoir Identifier**: Enter a name (e.g., `METTUR-STANLEY` or `RES-001`).
3. **Water Index Algorithm**: Select `NDWI` (default).
4. **Index Decision Threshold**: Leave at `0.0` (standard water threshold).
5. **Decline Flag Threshold (%)**: Set to `-10%` (loss triggering potential decline).
6. **Critical Decline Threshold (%)**: Set to `-25%` (loss triggering critical alert).
7. **Increase Flag Threshold (%)**: Set to `+10%` (expansion flag).
8. **Minimum Valid Coverage (%)**: Set to `70%`.
9. **Maximum Cloud Cover (%)**: Set to `20%`.

#### Step 2: Ingest Baseline Observation (Earlier Date)
In the main panel under **1️⃣ Baseline Observation**:
- **Baseline Scene ID**: `REAL_METTUR_2026-08-30`
- **Baseline Acquisition Date (YYYY-MM-DD)**: `2026-08-30`
- **Baseline Raster Layout**: Select `Separate Single-Band Files`
- **Green Band (B03) GeoTIFF Path**: `data/real_mettur/date1_2026-08-30_B03.tif` (or `micro-reservoir-intelligence/data/real_mettur/date1_2026-08-30_B03.tif`)
- **NIR Band (B08) GeoTIFF Path**: `data/real_mettur/date1_2026-08-30_B08.tif` (or `micro-reservoir-intelligence/data/real_mettur/date1_2026-08-30_B08.tif`)
- **Optional Cloud Mask Path**: Leave blank

#### Step 3: Ingest Follow-up Observation (Later Date)
Under **2️⃣ Follow-up (Comparison) Observation**:
- **Comparison Scene ID**: `REAL_METTUR_2026-09-29`
- **Comparison Acquisition Date (YYYY-MM-DD)**: `2026-09-29`
- **Comparison Raster Layout**: Select `Separate Single-Band Files`
- **Green Band (B03) GeoTIFF Path**: `data/real_mettur/date2_2026-09-29_B03.tif` (or `micro-reservoir-intelligence/data/real_mettur/date2_2026-09-29_B03.tif`)
- **NIR Band (B08) GeoTIFF Path**: `data/real_mettur/date2_2026-09-29_B08.tif` (or `micro-reservoir-intelligence/data/real_mettur/date2_2026-09-29_B08.tif`)
- **Optional Cloud Mask Path**: Leave blank

#### Step 4: Run Analysis
Click the blue button: **🔍 Run Multi-Temporal Analysis**.

---

### 6.3 Mode 2: Synthetic Benchmark Scenarios (Offline Demonstration)

When real GeoTIFF files are not present on disk, use Mode 2 to evaluate pipeline functionality:

1. In the sidebar under **Input Data Source**, select **🧪 Synthetic Test Scenarios (Demo Mode)**.
2. Under **Select Benchmark Test Scenario**, choose one of the pre-configured options:
   - `Seasonal Reservoir Drawdown (Expected: POTENTIAL_DECLINE)`
   - `Monsoon Inflow Recharge (Expected: POTENTIAL_INCREASE)`
   - `Controlled Stable Storage (Expected: STABLE)`
   - `Cloud Obscuration Deficit (Expected: INSUFFICIENT_DATA)`
3. Click **🔍 Run Multi-Temporal Analysis**.

> [!WARNING]
> **Data Honesty Warning**: Synthetic benchmark scenarios display a prominent amber banner in the dashboard. These scenarios use simulated arrays to verify computational pipelines and must **never** be reported as real satellite observations.

---

## 7. Interpreting Analytical Results & Dashboard Tabs

Once analysis completes, the dashboard presents findings across multiple visual sections:

### 7.1 Summary Header & Status Badges
- **Reservoir Name and Dates**: Displays the water body identifier and date span.
- **Operational Status Badge**:
  - 🟩 **STABLE**: Surface area changed by less than $\pm 10\%$.
  - 🟥 **POTENTIAL DECLINE**: Surface area contracted by more than $10\%$.
  - 🟦 **POTENTIAL INCREASE**: Surface area expanded by more than $10\%$.
  - 🟨 **INSUFFICIENT DATA**: Cloud cover $> 20\%$ or valid coverage $< 70\%$.
  - ⬛ **INVALID COMPARISON**: Mismatched spatial grids, CRS, or reversed dates.

### 7.2 KPI Metric Cards
- **Baseline Area**: Measured water extent on baseline date ($m^2$, hectares, acres, pixel count).
- **Follow-up Area**: Measured water extent on follow-up date.
- **Net Surface Area Shift**: Absolute change in hectares and relative percentage shift.
- **Confidence Index**: Confidence percentage based on cloud obscuration and data quality verification.

### 7.3 Detailed Inspection Tabs

#### Tab 1: 🛰️ Spectral Imagery & NDWI
Displays side-by-side continuous Normalized Difference Water Index (NDWI) heatmaps for both observation dates. Use the Plotly toolbar to zoom in, pan, or inspect individual pixel values. Values range from $-1.0$ (dry land/vegetation) to $+1.0$ (deep open water).

#### Tab 2: 💧 Classified Water Masks
Visualizes binary water masks where pixels exceeding the configured threshold (default $0.0$) on valid pixels are highlighted in cyan/blue. Displays computed boundary mixed-pixel uncertainty ranges:
$$\text{Confidence Interval} = \left[\text{Area} - \text{Uncertainty}, \text{Area} + \text{Uncertainty}\right]$$

#### Tab 3: 🔄 Transition Change Map
Presents a categorical 2D change map:
- 🟦 **Navy Blue**: Persistent Water (present in both observations).
- 🟥 **Red**: Water Lost / Retracted (water in baseline, dry in follow-up).
- 🟩 **Green**: Water Gained / Expanded (dry in baseline, water in follow-up).
- ⬛ **Dark Gray**: Invalid / Cloud-masked pixels.
The breakdown table shows exact pixel counts and hectare coverage for each transition class.

#### Tab 4: 📊 Comparison Chart
Displays an interactive Plotly bar chart comparing baseline and follow-up water coverage with custom hover tooltips showing both metric units ($m^2$ and ha). Below the chart, a structured table summarizes numerical shifts.

#### Tab 5: 🛡️ Quality Pre-Flight Checks
Displays the five automated pre-flight quality audit checks:
1. **Coordinate Reference System (CRS)**: Verifies matching projected planar CRS (e.g., `EPSG:32643`).
2. **Spatial Grid Dimensions & Resolution**: Verifies identical row/column count and pixel resolution.
3. **Valid Data Coverage Ratio**: Asserts that valid pixels comprise $\ge 70\%$ of the grid.
4. **Cloud Obscuration Screening**: Evaluates whether cloud contamination is $\le 20\%$. Discloses when cloud screening was unverified due to lack of local cloud mask.
5. **Temporal Precedence**: Verifies that the baseline date strictly precedes the follow-up date.

#### Tab 6: ⚠️ Operational Alerts
Displays structured advisory cards categorized by severity:
- 🚨 **CRITICAL**: Significant water shrinkage exceeding critical threshold ($\le -25\%$).
- ⚠️ **WARNING**: Moderate shrinkage ($-10\%$ to $-25\%$) or unverified data quality.
- ℹ️ **INFO**: Stable storage or post-monsoon storage expansion.
Each alert card provides the scientific rationale and recommended field actions (e.g., ground-truthing, bund inspection, irrigation scheduling).

#### Tab 7: 📥 Export Reports
Provides direct download buttons for:
- **📄 Download Assessment Report (CSV)**: Formatted tabular breakdown suitable for spreadsheets.
- **📋 Download Detailed Report (JSON)**: Machine-readable payload containing full observation metadata, change metrics, active alerts, and diagnostic caveats.

---

## 8. Troubleshooting & Common Operational Errors

| Error Message in Dashboard | Root Cause | Solution |
| :--- | :--- | :--- |
| `File Not Found: ...` | Specified GeoTIFF path does not exist on local disk. | Verify file path spelling. If running from nested directory, use `data/real_mettur/...`. |
| `Incompatible Grid: Spatial raster dimension mismatch` | Baseline and comparison files have different matrix dimensions ($H \times W$). | Ensure both images are clipped to the exact same spatial bounding box. |
| `Incompatible Grid: Coordinate Reference System mismatch` | Baseline and comparison files use different coordinate projections. | Reproject both rasters to a matching projected CRS (e.g., `EPSG:32643`) before loading. |
| `Temporal Precedence Inversion` | Baseline date was entered after or identical to comparison date. | Ensure earlier observation is in Section 1 and later observation is in Section 2. |
| `Geographic CRS detected` | Raster is projected in unprojected angular degrees (`EPSG:4326`). | Reproject raster to a planar UTM zone (e.g., `EPSG:32643`) using GDAL or QGIS. |
| `Maximum pixel limit exceeded` | Full unclipped satellite tile ($> 25,000,000$ pixels) was supplied. | Clip raster to reservoir Area of Interest (AOI) before ingestion to protect memory. |
| `NoData Error: zero valid pixels` | Supplied file is empty or 100% masked. | Check file size and verify band content in QGIS or GDALinfo. |
