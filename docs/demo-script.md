# Demonstration & Evaluation Guide: Micro-Reservoir Intelligence

This guide provides the complete evaluation protocol and an exact **Three-Minute Live Hackathon Demonstration Script** for presenting **Micro-Reservoir Intelligence** using either local GeoTIFF satellite files or verified benchmark demonstration scenarios.

---

## 1. Quick Launch Commands

### A. Activate Environment
* **Windows (PowerShell)**:
  ```powershell
  .venv\Scripts\Activate.ps1
  ```
* **macOS / Linux**:
  ```bash
  source .venv/bin/activate
  ```

### B. Launch Streamlit Dashboard
```powershell
streamlit run app.py
```
*(Or explicitly with Python)*:
```powershell
python -m streamlit run app.py
```

### C. Run Command-Line Regression Suite
```powershell
python scripts/run_demo.py
```

---

## 2. Three-Minute Live Hackathon Demonstration Script

### Timing Overview
| Timestamp | Segment | Visual / Action | Speaker Talking Points |
| :--- | :--- | :--- | :--- |
| **0:00 – 0:30** | **The Problem & Objective** | Title screen, Dashboard header, Methodology Expander | Climate volatility and rural water security challenge. |
| **0:30 – 1:00** | **Data Loading & Inputs** | Select data mode (Synthetic demo or GeoTIFF paths) | Two verified satellite observations, strict band mapping, 100% offline. |
| **1:00 – 1:40** | **Spectral Extraction & Water Masks** | Tabs: "Spectral Imagery & NDWI" and "Classified Water Masks" | Green vs NIR physics, continuous NDWI index, threshold segmentation. |
| **1:40 – 2:15** | **Area Quantification & Dynamic Shifts** | KPI Cards, "Comparison Chart" & "Transition Change Map" | Dual unit metrics (ha, m²), delta shift, boundary uncertainty. |
| **2:15 – 2:40** | **Quality Assurance & Operational Status** | "Quality Pre-Flight Checks" & "Operational Alerts" | CRS checks, cloud screening, status badges, drought caveat. |
| **2:40 – 3:00** | **Export, Limitations & Next Steps** | "Export Reports" (CSV / JSON download) & Closing | RFC 4180 CSV / JSON report, limitations (surface vs groundwater), next steps. |

---

### Step-by-Step Script & Speaker Notes

#### [0:00 – 0:30] 1. Introduce the Problem
* **On Screen**: Open `http://localhost:8501`. Show the header: **"Micro-Reservoir Intelligence: Surface Water Dynamics"**. Click the **"ℹ️ Analysis Methodology & Scientific Principles"** expander.
* **Speaker Script**:
  > *"Judges, over 80% of smallholder farmers and rural communities rely on ungauged minor reservoirs and irrigation tanks. Because these water bodies are small and unmonitored, severe drawdowns and seasonal shortages go undetected until crops fail or emergency water trucking is required.  
  > Micro-Reservoir Intelligence solves this. We built a 100% local, CPU-bound computer vision tool that ingests multispectral satellite imagery, isolates surface water, quantifies surface area in square meters and hectares, tracks bi-temporal shifts, and generates quality-aware operational alerts—without requiring internet connectivity, cloud APIs, or GPUs."*

#### [0:30 – 1:00] 2. Load Benchmark Demonstration Scenario (or Local GeoTIFF Files)
* **On Screen**: In the sidebar under **"Data Source Mode"**, select **"Synthetic Demonstration Scenarios"** and pick **"Scenario 1: Severe Summer Drawdown (October ➔ March)"** (or switch to **"Local GeoTIFF Files"** to show single-band / multiband path inputs). Click the **"🚀 Run Surface Water Analysis"** button.
* **Speaker Script**:
  > *"Our pipeline ingests two temporally separated observations: a baseline reference—here from October following the monsoon—and a follow-up observation from March during pre-summer dry season.  
  > We support both separate single-band GeoTIFFs (Sentinel-2 B03 Green and B08 NIR) and stacked multiband rasters with explicit band mappings. Notice our data honesty guarantee: because multi-gigabyte satellite rasters are not bundled in the repo, we demonstrate using our verified synthetic benchmark scenario, which the system visibly labels with a warning banner. Operators can input their real clipped GeoTIFF files directly via Mode 1 without changing any code."*

#### [1:00 – 1:40] 3. Show NDWI and Water Masks
* **On Screen**: Click Tab 1: **"🛰️ Spectral Imagery & NDWI"**, then Tab 2: **"💧 Classified Water Masks"**.
* **Speaker Script**:
  > *"Water has a unique optical signature: it strongly reflects green light around 560 nanometers and strongly absorbs near-infrared light around 842 nanometers. Terrestrial soil and vegetation do the exact opposite.  
  > We use McFeeters' Normalized Difference Water Index (NDWI) implemented with vectorized NumPy C-level routines. As you can see on the continuous heatmaps, deep water yields positive index values while surrounding vegetation yields negative values.  
  > By applying our configured threshold of 0.0, we generate binary surface-water masks. Notice that boundary pixels outside valid radiometric bounds are quarantined, and zero-denominator pixels are protected against numeric overflow."*

#### [1:40 – 2:15] 4. Show the Two Area Estimates and Measured Change
* **On Screen**: Point to the 4 Top KPI Cards and Tab 3: **"🔄 Transition Change Map"** and Tab 4: **"📊 Comparison Chart"**.
* **Speaker Script**:
  > *"Next, we convert pixel counts into physical ground metrics using the raster's affine transform determinant. We never assume a generic 10-meter square without checking the CRS; if an unprojected geographic CRS like EPSG:4326 is passed, we explicitly flag it rather than inventing inaccurate areas.  
  > Here, our baseline October reservoir was 17.800 hectares (178,000 m²). By March, it contracted to 5.880 hectares (58,800 m²). That represents a net loss of 11.920 hectares, or a -67.0% surface area decline.  
  > On our categorical transition map, blue pixels show persistent water, while red pixels reveal exactly where the reservoir shoreline retreated. Our Plotly comparison chart displays these measurements alongside boundary mixed-pixel uncertainty bounds."*

#### [2:15 – 2:40] 5. Explain Quality Checks and Resulting Status
* **On Screen**: Click Tab 5: **"🛡️ Quality Pre-Flight Checks"** and Tab 6: **"⚠️ Operational Alerts"**.
* **Speaker Script**:
  > *"Crucially, we do not issue unqualified decline alerts blindly. Our pre-flight quality engine checks CRS alignment, pixel grid compatibility, valid data coverage (requiring at least 70%), and cloud screening (flagging scenes with over 20% cloud cover).  
  > If cloud cover is high or the comparison is invalid, the status automatically degrades to 'INSUFFICIENT_DATA' or 'INVALID_COMPARISON', and severe alerts are suppressed.  
  > Because this test passed all quality checks with 98% confidence, the system issues a verified 'POTENTIAL_DECLINE' status and triggers a CRITICAL alert advising field teams to verify storage levels. We also embed an explicit hydrological disclaimer: surface water retreat does not directly prove groundwater or aquifer depletion."*

#### [2:40 – 3:00] 6. Export Reports, Limitations & Next Improvements
* **On Screen**: Click Tab 7: **"📥 Export Reports"**. Point out the **"Download CSV Report"** and **"Download JSON Report"** buttons. Click to download.
* **Speaker Script**:
  > *"To support field operations and environmental agencies, the entire analysis—including raw metrics, coordinate reference systems, quality flags, and alert recommendations—can be exported in one click as a structured CSV or JSON report.  
  > Limitations: Optical sensors cannot penetrate cloud cover, and surface area does not capture bathymetric depth.  
  > Next improvements: Integrating Sentinel-1 Synthetic Aperture Radar (SAR) for all-weather day/night observation, and estimating volumetric curves using digital elevation models.  
  > Micro-Reservoir Intelligence is fully tested with 92 passing unit and integration tests, compiles cleanly, runs 100% locally on CPU, and is ready for live demonstration."*

---

## 3. Alternative Quick Demonstrations

### Demonstrating Cloud Obscuration Fallback
1. Switch sidebar scenario to **"Scenario 4: Cloud-Obscured Scene (July 2024)"**.
2. Click **"🚀 Run Surface Water Analysis"**.
3. Point out the resulting **`INSUFFICIENT_DATA`** status badge (Orange) and 20% confidence score.
4. Explain how the cloud check detected 68% cloud cover and suppressed a false decline alert.

### Demonstrating Monsoon Recharge
1. Switch sidebar scenario to **"Scenario 2: Post-Monsoon Storage Recovery (May ➔ August)"**.
2. Click **"🚀 Run Surface Water Analysis"**.
3. Point out the **`POTENTIAL_INCREASE`** status badge (Teal), $+552.7\%$ change ($+12.16\text{ ha}$ gained), and the green expansion ring on the transition map.

