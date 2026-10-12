# Project Documentation Report: Micro-Reservoir Intelligence
## Satellite-Based Reservoir Water Surface Monitoring

---

### Document Information & Metadata

| Metadata Field | Project Detail |
| :--- | :--- |
| **Project Title** | **Micro-Reservoir Intelligence** |
| **Subtitle** | Satellite-Based Reservoir Water Surface Monitoring |
| **Study Area** | Mettur Reservoir Region (Stanley Reservoir), Salem District, Tamil Nadu, India |
| **Project Category** | Remote Sensing / Geospatial Data Analysis / Applied Computer Vision |
| **Technology Stack** | Python 3.12, Streamlit, Rasterio, GDAL (via Rasterio), NumPy, Matplotlib, Plotly, pytest |
| **Target Architecture** | Standard CPU Laptop (Zero GPU requirement, Zero Database, Zero External Network at Runtime) |
| **Prepared By** | `[Enter Name]` |
| **Institution** | `[Enter Institution]` |
| **Academic Year / Date** | `[Enter Academic Year / Date]` |
| **Software Version** | v0.2.0 (Verified Local Build) |

---

## Table of Contents

1. [Abstract](#1-abstract)
2. [Introduction](#2-introduction)
3. [Problem Statement](#3-problem-statement)
4. [Objectives](#4-objectives)
5. [Scope](#5-scope)
6. [Existing System and Proposed System](#6-existing-system-and-proposed-system)
7. [Requirements Analysis](#7-requirements-analysis)
8. [System Architecture](#8-system-architecture)
9. [Technology Stack](#9-technology-stack)
10. [Data Source and Dataset Description](#10-data-source-and-dataset-description)
11. [Mathematical Methodology](#11-mathematical-methodology)
12. [Algorithm and Implementation Details](#12-algorithm-and-implementation-details)
13. [Project Directory Structure](#13-project-directory-structure)
14. [Dashboard and User Guide](#14-dashboard-and-user-guide)
15. [Validation and Testing](#15-validation-and-testing)
16. [Results and Discussion](#16-results-and-discussion)
17. [Limitations and Risk Analysis](#17-limitations-and-risk-analysis)
18. [Security, Reliability, and Error Handling](#18-security-reliability-and-error-handling)
19. [Applications and Benefits](#19-applications-and-benefits)
20. [Future Enhancements](#20-future-enhancements)
21. [Conclusion](#21-conclusion)
22. [References](#22-references)
- [Appendix A: Exact Windows Commands](#appendix-a-exact-windows-commands)
- [Appendix B: Input File Inventory](#appendix-b-input-file-inventory)
- [Appendix C: Key Configuration Parameters](#appendix-c-key-configuration-parameters)
- [Appendix D: Glossary of Technical Terms](#appendix-d-glossary-of-technical-terms)
- [Appendix E: Troubleshooting Guide](#appendix-e-troubleshooting-guide)

---

## 1. Abstract

Water security across semi-arid agricultural landscapes depends heavily on surface reservoirs, check dams, and local irrigation tanks. Traditional monitoring of these water bodies often relies on physical gauge stations or manual field inspections that are resource-intensive, geographically fragmented, and infrequent. **Micro-Reservoir Intelligence** is an automated, lightweight, CPU-efficient software system designed to monitor surface-water extent using optical multispectral satellite imagery from the European Space Agency's (ESA) Sentinel-2 constellation. 

The pipeline ingests Level-2A surface reflectance data—specifically Band 3 (Green, 560 nm) and Band 8 (Near-Infrared, 842 nm)—at nominal 10-meter spatial resolution. By computing the Normalized Difference Water Index (NDWI) with vectorized numerical routines, applying configurable threshold segmentation, deriving planar physical surface area via projected coordinate system affine transforms, and executing bi-temporal change detection, the system quantifies water-body dynamics between two observation dates. The system incorporates rigorous geospatial quality assurance, including Coordinate Reference System (CRS) verification, spatial grid dimension matching, NoData/invalid-pixel quarantine, and boundary mixed-pixel uncertainty modeling. A quality-aware alerting engine classifies transitions into standardized operational states (`stable`, `potential_decline`, `potential_increase`, `insufficient_data`, `invalid_comparison`) and generates tiered advisory notifications while suppressing unverified alerts when quality checks fail. 

The application is implemented in Python and presented through an interactive Streamlit web dashboard alongside an offline CLI runner. The solution was validated against real Sentinel-2 satellite observations over the Mettur Reservoir region in Tamil Nadu, India, spanning August 30, 2026, and September 29, 2026, as well as a comprehensive automated test suite consisting of 102 individual test cases (204 tests collected across workspace scopes) with a 100% pass rate. This documentation report presents the complete theoretical foundation, system architecture, verified implementation details, mathematical formulations, operational user workflows, and scientific caveats of the project.

---

## 2. Introduction

### 2.1 Reservoir Monitoring Context
Reservoirs, percolation tanks, and village storage impoundments serve as vital buffers against hydrological variability in drought-prone and agricultural regions. In states such as Tamil Nadu, India, surface water storage dictates seasonal cropping schedules, municipal drinking water supplies, and rural groundwater recharge. However, monitoring reservoir surface water extent across extensive river basins presents significant operational challenges. Conventional monitoring typically relies on telemetric water-level sensors installed at major dam structures or periodic manual gauge-staff readings conducted by irrigation department personnel.

### 2.2 Importance of Monitoring Surface-Water Extent
While water-level gauges provide vertical stage measurements at a single localized point, surface-water area observations provide a two-dimensional spatial perspective on reservoir surface retreat and expansion. Surface extent directly influences open-water evaporation losses, defines the boundaries of receding shorelines, highlights siltation accretion zones, and enables monitoring of ungauged or remote reservoir arms where physical telemetry is absent.

### 2.3 Satellite Remote Sensing as an Observation Tool
Satellite earth observation provides systematic, repeatable, and non-intrusive monitoring capabilities over broad geographical areas. The Sentinel-2 mission, operated by the European Space Agency under the Copernicus Programme, comprises twin satellites (Sentinel-2A and Sentinel-2B) flying in a sun-synchronous orbit with a combined 5-day revisit cycle at the equator. Sentinel-2’s Multispectral Instrument (MSI) captures 13 spectral bands spanning visible, near-infrared (NIR), and shortwave-infrared (SWIR) wavelengths. The availability of open-access, atmospherically corrected Level-2A Bottom-Of-Atmosphere (BOA) surface reflectance imagery makes Sentinel-2 well-suited for automated surface-water extraction without data acquisition costs.

### 2.4 Role of Automated Multi-Temporal Comparison
Water-resource authorities and environmental analysts require objective comparison between distinct temporal epochs—such as post-monsoon full storage versus pre-summer depletion. Manually downloading gigabyte-scale satellite granules, clipping bands in desktop GIS applications, and calculating raster math is time-consuming and prone to human procedural error. An automated, scriptable, CPU-compatible pipeline standardizes this analytical workflow: it validates spatial compatibility, computes spectral water indices, extracts water masks, calculates surface area with confidence intervals, compares temporal shifts, and issues structured warnings when significant surface shrinkage is detected.

---

## 3. Problem Statement

Water management agencies, watershed planners, and local stakeholders face distinct operational hurdles when tracking surface storage dynamics:

1. **Infrequent and Localized Ground Gauging**: Physical gauging stations are predominantly concentrated at major dam heads, leaving upstream reservoir stretches, secondary percolation ponds, and micro-reservoirs unmonitored.
2. **High Latency and Manual Overhead**: Manual interpretation of satellite rasters in desktop Geographic Information Systems (GIS) requires specialized geospatial training, manual band registration, and substantial processing time, preventing timely response.
3. **Hardware and Connectivity Barriers**: Many modern geospatial analysis workflows rely on cloud compute credits, specialized graphical processing units (GPUs), deep learning models, or persistent database servers, making them inaccessible to field officers operating on standard CPU laptops with intermittent internet connectivity.
4. **Data Reliability and Misinterpretation Risks**: Rudimentary water extraction algorithms often ignore spatial grid alignment, fail to quarantine invalid or cloudy pixels, miscalculate ground area by treating angular degrees (such as WGS84 `EPSG:4326`) as planar meters, or fail to disclose boundary mixed-pixel uncertainties. Furthermore, automated tools frequently issue alarmist drought warnings based purely on optical surface shrinkage without disclosing hydrological caveats.

There is a defined need for an open-source, CPU-bound, robustly tested software utility that automates multispectral satellite water extraction, enforces geospatial integrity, quantifies surface area in physical units, performs quality-aware temporal change detection, and delivers actionable operational alerts through an accessible interface.

---

## 4. Objectives

### 4.1 Primary Objectives
- **Automated Water Extraction**: Implement a vectorized numerical engine in Python to ingest Sentinel-2 Level-2A Green (Band 3) and Near-Infrared (Band 8) GeoTIFF rasters and compute the Normalized Difference Water Index (NDWI) with zero-division and invalid-pixel protection.
- **Physical Surface Area Quantification**: Derive planar ground surface area in square meters ($m^2$), hectares (ha), and acres based on authoritative Coordinate Reference System (CRS) parameters and affine transformation determinants, incorporating boundary mixed-pixel uncertainty bounds.
- **Multi-Temporal Change Detection**: Compare baseline and comparison observations across matching spatial grids to calculate net area shifts and percentage changes, classifying results into standardized operational states (`stable`, `potential_decline`, `potential_increase`, `insufficient_data`, `invalid_comparison`).
- **Quality-Aware Operational Alerting**: Implement an alert generator that translates multi-temporal changes into graded operational advisories (`CRITICAL`, `WARNING`, `INFO`) while suppressing unverified decline alerts when quality validation checks fail.
- **Interactive Visualization Dashboard**: Provide an accessible Streamlit web application enabling users to load local GeoTIFF files, inspect continuous NDWI heatmaps, view binary water masks and categorical transition maps, evaluate quality checks, and export structured CSV/JSON summary reports.

### 4.2 Secondary Objectives
- **Resilient Public Satellite Data Retrieval**: Develop a standalone downloader script capable of querying the public Earth Search STAC catalog, filtering compatible Sentinel-2 scenes over the Mettur Reservoir study area, and downloading study-window cropped GeoTIFFs using HTTP range requests without requiring API keys.
- **Rigorous Path and Memory Safety**: Enforce strict filesystem path validation (blocking directory traversal and null-byte injection) and a pixel processing safety threshold (`max_pixel_limit = 25,000,000` pixels) to protect CPU laptop memory from exhaustion.
- **Offline Synthetic Scenario Exploration**: Provide synthetic multi-temporal benchmark scenarios with clear labeling to allow offline evaluation of pipeline mechanics without live satellite data.
- **Comprehensive Quality Assurance**: Maintain a fully automated unit, integration, and regression test suite verifying mathematical formulations, edge cases, grid mismatches, and reporting serialization.

---

## 5. Scope

### 5.1 Implemented Capabilities
- Ingestion of single-band GeoTIFF rasters (`green`, `nir`) and multiband rasters with explicit 1-indexed band mappings using Rasterio and GDAL.
- Vectorized calculation of McFeeters (1996) NDWI, Xu (2006) MNDWI, and Feyisa et al. (2014) AWEI.
- Rejection of angular geographic coordinate systems (e.g., `EPSG:4326`) for area calculations to avoid dimensional distortion.
- Affine transform-based ground pixel area derivation: $\text{Pixel Area} = |a \cdot e - b \cdot d|$.
- Edge-pixel boundary uncertainty quantification: $\pm \sqrt{N} \times \text{pixel\_area}$.
- Enforced temporal ordering: baseline observation date must strictly precede comparison date.
- Joint NoData and validity mask intersection, quarantining NaN, Inf, and cloud-obscured pixels.
- Zero-baseline protection: percentage change is reported as mathematically unavailable (`None`) when baseline area is $0.0\text{ m}^2$, avoiding zero-division crashes.
- Dual interface: interactive browser-based Streamlit dashboard (`app.py`) and non-interactive command-line runner (`scripts/run_demo.py`).
- Export of assessment reports in structured CSV and machine-readable JSON formats.
- Standalone downloader script (`download_mettur_sentinel2.py`) with HTTP range-request window cropping and automated grid compatibility checks.

### 5.2 Current Limitations
- **Optical Sensor Cloud Limitation**: The pipeline relies on optical imagery; optical sensors cannot penetrate cloud cover. Automatic internal cloud detection is not performed by the application; cloud filtering relies on catalog metadata or externally supplied cloud masks.
- **Surface Area vs. Bathymetric Storage Volume**: Multispectral indexing quantifies horizontal surface-water area ($m^2$, ha). It does not calculate water depth, bathymetry, or storage volume ($m^3$) without an integrated Digital Elevation Model (DEM) and depth-capacity curve.
- **Rectangular Study Window vs. Surveyed Boundary**: The current Mettur study dataset uses a rectangular bounding box (`77.72°E` to `77.90°E`, `11.74°N` to `11.88°N`), capturing surrounding land and river stretches rather than an officially surveyed administrative reservoir boundary polygon.
- **Bi-Temporal Epoch Comparison**: The core pipeline compares two discrete dates. It does not perform continuous daily or seasonal time-series trend fitting.
- **Spectral Confusion Risks**: NDWI is an empirical spectral ratio. Terrain shadows, cloud shadows, dark basaltic soils, high water turbidity, and eutrophic algal blooms can induce false-positive or false-negative classifications.

### 5.3 Proposed Future Enhancements
- Integration of automated local pixel-level cloud and cloud-shadow masking (e.g., Sentinel-2 Scene Classification Layer / SCL).
- Ingestion of official vector shapefiles/GeoJSON polygons to clip raster calculations strictly to gazetted reservoir boundaries.
- Implementation of dynamic Otsu thresholding alongside the current fixed threshold ($0.0$).
- Incorporation of bathymetric stage-storage elevation curves to estimate water volume in million cubic meters (MCM).
- Integration of ground-truth telemetric water level and rainfall telemetry data.

---

## 6. Existing System and Proposed System

### 6.1 Existing / Conventional Monitoring Workflow
Conventional reservoir monitoring is typically conducted via one of two workflows:
1. **Manual Field & Gauge Staff Monitoring**: Technicians record water levels from physical staff gauges installed at the dam structure. These readings are manually entered into paper logbooks or localized databases. They provide single-point elevation data but no spatial extent information.
2. **Ad-Hoc Desktop GIS Analysis**: An analyst manually downloads full 500 MB–1 GB Sentinel-2 SAFE archives, extracts JPEG2000 or GeoTIFF files, loads them into desktop GIS software (e.g., QGIS or ArcGIS), manually runs raster calculator expressions, clips the result, and manually summarizes pixel counts in spreadsheets.

**Drawbacks of Existing Workflows**:
- High human latency and manual processing overhead.
- Inconsistent thresholding and NoData handling between different analysts.
- Risk of incorrect area calculation if rasters are not reprojected from geographic degrees to planar meters.
- Heavy computational requirements when processing entire 10,980 × 10,980 pixel satellite tiles on local machines.

### 6.2 Proposed System: Micro-Reservoir Intelligence
The proposed system automates the end-to-end processing chain via a standalone, CPU-optimized Python pipeline:
- **Direct Window Ingestion**: Accesses only the required spatial bounding window using Cloud-Optimized GeoTIFF (COG) HTTP range requests or pre-cropped local files.
- **Standardized Geospatial Validation**: Enforces CRS projection, spatial resolution alignment, and temporal sequence checks automatically before computation.
- **Vectorized Mathematics**: Employs pure NumPy array operations for instant NDWI computation and threshold classification in seconds on CPU.
- **Quality-Aware Safeguards**: Automatically identifies low data coverage ($< 70\%$) or high cloud cover ($> 20\%$), assigns standardized status codes, and suppresses unverified decline alerts.
- **Integrated Decision Support**: Presents key metrics, continuous index maps, binary water masks, categorical change maps, and alert advisories in a unified web dashboard.

### 6.3 Comparative Feature Matrix

| Feature / Dimension | Conventional Manual / Desktop GIS | Proposed Micro-Reservoir Intelligence |
| :--- | :--- | :--- |
| **Observation Medium** | Local staff gauges or manual GIS imports | Automated ingestion of Sentinel-2 L2A GeoTIFFs |
| **Spatial Perspective** | 1D single-point gauge elevation | 2D surface water extent and transition mapping |
| **Processing Speed** | Hours to days per observation pair | $< 5$ seconds per observation pair on CPU |
| **Hardware Requirement** | High-spec workstation for large SAFE tiles | Standard CPU-only laptop ($< 4$ GB RAM used) |
| **CRS & Grid Enforcement** | Manual check by analyst; prone to error | Automated programmatic verification; rejects angular CRS |
| **Zero-Baseline Safeguard** | Frequent `#DIV/0!` errors in spreadsheets | Mathematically guarded; reports delta as unavailable (`None`) |
| **Alerting Mechanism** | Ad-hoc emails or delayed bureaucratic reports | Automated, tiered operational alerts (`CRITICAL`, `WARNING`, `INFO`) |
| **Data Honesty Controls** | Often undocumented mixed pixels and clouds | Boundary uncertainty ranges and quality caveat banners |
| **Operational Replacement** | Official regulatory authority record | **Screening / Decision-Support Prototype** (Does not replace official dam safety telemetry) |

> [!IMPORTANT]
> **Operational Disclaimer**: Micro-Reservoir Intelligence is an analytical decision-support prototype. It is designed to flag potential storage shifts for targeted inspection. It does not replace official reservoir monitoring, dam safety telemetric instrumentation, or regulatory reporting conducted by statutory water authorities (such as the Central Water Commission or State Water Resources Departments).

---

## 7. Requirements Analysis

### 7.1 Functional Requirements
- **FR-01 (Raster Ingestion)**: Ingest single-band GeoTIFF rasters (`green`, `nir`) and multiband GeoTIFF rasters with user-specified 1-indexed band assignments.
- **FR-02 (Path Validation)**: Validate all filesystem paths against null-byte injection (`\0`) and unauthorized directory traversal (`../`).
- **FR-03 (Spatial Consistency Verification)**: Verify that baseline and comparison rasters share identical dimensions ($H \times W$), matching CRS, and aligned affine transforms within a coordinate tolerance of $0.001\text{ m}$.
- **FR-04 (Temporal Sequence Enforcement)**: Parse observation dates in strict ISO-8601 calendar format (`YYYY-MM-DD`) and assert that baseline date strictly precedes comparison date.
- **FR-05 (NDWI Computation)**: Compute McFeeters NDWI vectorially with zero-division protection ($|Green + NIR| \le 10^{-7}$) and NaN/Inf sanitization.
- **FR-06 (Threshold Segmentation)**: Segment the index array into a binary water mask using a configurable threshold (default `0.0`), applying strict inequality (`index > threshold`) on valid pixels.
- **FR-07 (Area and Uncertainty Estimation)**: Calculate surface area in $m^2$, hectares, and acres based on the affine determinant, computing boundary uncertainty as $\pm \sqrt{N} \times \text{pixel\_area}$.
- **FR-08 (Bi-Temporal Change Classification)**: Compute absolute area shifts and percentage changes, classifying observations into one of five statuses: `stable`, `potential_decline`, `potential_increase`, `insufficient_data`, or `invalid_comparison`.
- **FR-09 (Alert Generation)**: Generate operational alert items with severity ratings (`CRITICAL`, `WARNING`, `INFO`) and actionable advice, suppressing unverified decline alerts when quality validation fails.
- **FR-10 (Report Export)**: Export complete analytical findings, metadata, and diagnostic warnings to standard CSV and JSON formats.

### 7.2 Non-Functional Requirements
- **NFR-01 (Performance & Latency)**: End-to-end analysis of a $1614 \times 1571$ pixel raster pair must execute in under 5.0 seconds on standard laptop CPU hardware.
- **NFR-02 (Memory Safety)**: Prevent out-of-memory crashes by enforcing a maximum raster safety limit of $25,000,000$ pixels (`max_pixel_limit`).
- **NFR-03 (Offline Reliability)**: Core analytical and dashboard execution must run 100% locally without external network dependencies, APIs, or database connections.
- **NFR-04 (Maintainability & Modularity)**: Pipeline modules must maintain a clean separation of concerns, communicating via strongly-typed, immutable dataclasses.
- **NFR-05 (Reproducibility & Testability)**: Automated test suite must execute cleanly via `pytest` without requiring live internet access or external credentials.

### 7.3 Hardware Requirements
- **Processor**: Standard 64-bit x86_64 or ARM64 multi-core CPU (Intel Core i3/i5/i7, AMD Ryzen, or Apple Silicon).
- **RAM**: Minimum 4 GB RAM (8 GB recommended for multi-band image buffering).
- **Storage**: Minimum 500 MB free disk space for Python virtual environment, dependencies, sample arrays, and local GeoTIFFs.
- **GPU**: None required (100% CPU-compatible numerical implementation).

### 7.4 Software Requirements
- **Operating System**: Microsoft Windows 10/11 (x64), Linux (Ubuntu 20.04+, Debian 11+, RHEL 8+), or macOS (12+).
- **Shell**: PowerShell 5.1+ or PowerShell 7+ (Windows), Bash/Zsh (Linux/macOS).
- **Web Browser**: Modern Chromium-based browser (Chrome, Edge, Brave) or Firefox for Streamlit dashboard rendering.

### 7.5 Verified Python Environment & Dependency Requirements

The project dependencies are strictly specified in `requirements.txt` and verified in the active `.venv` environment:

| Dependency Package | Verified Active Version | Specification in `requirements.txt` | Functional Role in Pipeline |
| :--- | :--- | :--- | :--- |
| **Python Runtime** | `3.12.14` (CPython 64-bit) | `>= 3.11, < 3.13` | Underlying execution runtime |
| **numpy** | `2.5.4` | `>= 1.26.4` | Vectorized numerical mathematics, NDWI array operations |
| **rasterio** | `1.5.2` | `>= 1.3.10` | Geospatial raster I/O, CRS parsing, affine transformations |
| **GDAL** | Bundled with Rasterio wheel | Provided via Rasterio | Geospatial Data Abstraction Library C-bindings |
| **pandas** | `3.0.6` | `>= 2.2.2` | Tabular data structures and CSV report formatting |
| **matplotlib** | `3.11.2` | `>= 3.9.0` | False-color and RGB raster composite rendering |
| **plotly** | `7.1.0` | `>= 5.22.0` | Interactive web heatmaps and comparative bar charts |
| **streamlit** | `1.65.0` | `>= 1.36.0` | Interactive web dashboard and UI state management |
| **python-dotenv** | `1.2.4` | `>= 1.0.1` | Environment variable configuration loading |
| **pytest** | `9.1.1` | `>= 8.2.0` | Automated test suite execution framework |
| **requests** | Available in environment | Downloader script dependency | HTTP STAC search and remote asset querying |

---

## 8. System Architecture

### 8.1 The Twelve-Stage Processing Architecture
The Micro-Reservoir Intelligence processing architecture follows a twelve-stage operational pipeline:

```
[Public Satellite Catalog Query]
               │
               ▼
   [Scene Discovery & Selection]
               │
               ▼
    [B03/B08 Asset Retrieval]
               │
               ▼
 [Study-Area Window Extraction]
               │
               ▼
     [GeoTIFF Generation]
               │
               ▼
   [Raster & Mask Validation]
               │
               ▼
       [NDWI Computation]
               │
               ▼
  [Water-Pixel Classification]
               │
               ▼
 [Surface-Water Area Estimation]
               │
               ▼
   [Multi-Temporal Comparison]
               │
               ▼
     [Threshold-Based Alerts]
               │
               ▼
    [Streamlit Visualization]
```

1. **Public Satellite Catalog Query**: Queries the public Earth Search STAC API (`https://earth-search.aws.element84.com/v1/search`) filtering for the `sentinel-2-c1-l2a` collection intersecting the study area bounding polygon.
2. **Scene Discovery and Selection**: Evaluates candidate scenes, filters for scene cloud cover $\le 35\%$, matches identical MGRS grid tiles (e.g., `MGRS-43PHP`), and selects two observations separated by $\ge 30$ days.
3. **B03/B08 Asset Retrieval**: Resolves direct S3 HTTPS URLs for Band 3 (Green, 10m) and Band 8 (NIR, 10m) Cloud-Optimized GeoTIFF assets.
4. **Study-Area Window Extraction**: Uses Rasterio GDAL virtual filesystem drivers (`/vsicurl/`) with range requests to read only the spatial bounding window intersecting the study area, avoiding downloading entire 10,980 × 10,980 pixel scenes.
5. **GeoTIFF Generation**: Writes cropped single-band Cloud-Optimized GeoTIFFs to local storage (`data/real_mettur/`) with internal compression and embedded valid-data masks.
6. **Raster and Mask Validation**: `load_geotiff_observation` and `validate_observation` inspect file integrity, verify projected planar CRS, check affine transforms, and construct validity masks excluding NoData, NaN, and cloud pixels.
7. **NDWI Computation**: `compute_ndwi` executes vectorized floating-point ratio arithmetic with epsilon zero-division guards.
8. **Water-Pixel Classification**: `detect_water` segments the index array using a user-configured threshold (default $0.0$) on valid pixels.
9. **Surface-Water Area Estimation**: `estimate_area` calculates water coverage in physical units ($m^2$, ha, acres) derived from affine determinants and models boundary mixed-pixel uncertainty.
10. **Multi-Temporal Comparison**: `compare_observations` evaluates baseline versus follow-up observations, verifies temporal precedence, calculates net area shifts, and constructs a 2D categorical transition map.
11. **Threshold-Based Alerts**: `generate_alerts` applies quality-aware rules, assigning operational severities (`CRITICAL`, `WARNING`, `INFO`) while suppressing unverified decline alerts if quality checks fail.
12. **Streamlit Visualization**: `app.py` renders interactive Plotly heatmaps, transition maps, metric cards, quality audit tables, and CSV/JSON download handlers.

### 8.2 Mermaid Architecture Flowchart

```mermaid
graph TD
    subgraph Stage 1: Public Satellite Catalog & Data Acquisition
        A1[Earth Search STAC API<br>POST /v1/search] --> A2[Scene Discovery & Filtering<br>BBox, Cloud <= 35%, Delta >= 30 days]
        A2 --> A3[Select Compatible Pair<br>Same Tile MGRS-43PHP]
        A3 --> A4[Remote COG Asset Reading<br>HTTP Range Requests via /vsicurl/]
        A4 --> A5[Local GeoTIFF Files<br>date1_B03/B08 & date2_B03/B08]
    end

    subgraph Stage 2: Ingestion & Geospatial Pre-Flight Validation
        A5 --> B1[load_geotiff_observation<br>geotiff.py]
        B1 --> B2[validate_safe_path<br>Path Traversal & Null Byte Guard]
        B1 --> B3[read_geotiff_metadata<br>Dimensions, Transform, CRS, NoData]
        B3 --> B4[validate_grid_compatibility<br>Assert Identical CRS, Dims, Grid]
        B4 --> B5[validate_temporal_order<br>Assert Baseline Date < Follow-up Date]
        B5 --> B6[Observation Dataclass<br>Metadata, Band Arrays, Valid Mask]
    end

    subgraph Stage 3: Spectral Water Detection Engine
        B6 --> C1[detect_water<br>water_detection.py]
        C1 --> C2[compute_ndwi<br>Green - NIR / Green + NIR]
        C2 --> C3[Epsilon Zero-Division Guard<br>Abs Denom <= 1e-7 -> 0.0]
        C3 --> C4[Binary Threshold Masking<br>Strict: Index > Threshold & Valid Mask]
        C4 --> C5[WaterDetectionResult<br>Binary Water Mask, NDWI Map, Stats]
    end

    subgraph Stage 4: Physical Area Quantification
        C5 --> D1[estimate_area<br>area_estimation.py]
        D1 --> D2[Planar CRS Check<br>Reject Unprojected Degrees]
        D2 --> D3[Pixel Area Calculation<br>Determinant: |a*e - b*d|]
        D3 --> D4[Area Conversion<br>m², Hectares, Acres]
        D4 --> D5[Boundary Uncertainty<br>± sqrt N * pixel_area]
        D5 --> D6[AreaEstimate Dataclass]
    end

    subgraph Stage 5: Multi-Temporal Dynamics & Alerting
        D6 & C5 --> E1[compare_observations<br>change_detection.py]
        E1 --> E2[Area Delta & Percentage Shift<br>Zero-Baseline Guard: Delta % = None]
        E2 --> E3[Quality-Aware Status Classification<br>stable / potential_decline / potential_increase]
        E3 --> E4[Categorical 2D Transition Map<br>Persistent, Lost, Gained, Invalid]
        E4 --> E5[generate_alerts<br>alerts.py]
        E5 --> E6[Tiered Alerts<br>CRITICAL, WARNING, INFO]
    end

    subgraph Stage 6: Dashboard Presentation & Reporting
        E3 & E4 & E6 --> F1[build_dashboard_data<br>reporting.py]
        F1 --> F2[Streamlit Web UI<br>app.py]
        F2 --> G1[KPI Cards & Status Badges]
        F2 --> G2[Interactive Plotly NDWI Heatmaps]
        F2 --> G3[Categorical Transition Map Image]
        F2 --> G4[Pre-Flight Quality Audit Panel]
        F2 --> G5[Export Handlers: CSV & JSON Reports]
    end
```

---

## 9. Technology Stack

Every technology listed below was verified directly against the project configuration, source modules, and active virtual environment:

### 9.1 Core Programming Language & Numerical Libraries
- **Python (v3.12.14)**: The core programming language. Python 3.12 provides improved execution performance, enhanced tracebacks, and native type hinting support.
- **NumPy (v2.5.4)**: Powers the entire mathematical processing core. Used for multi-dimensional array manipulation, vectorized floating-point NDWI ratio calculations, boolean mask masking, and statistical reductions (`min`, `max`, `mean`, `std`, `median`). All raster operations execute in compiled C memory space.

### 9.2 Geospatial Data Abstraction
- **Rasterio (v1.5.2)**: Geospatial raster I/O library built on GDAL. Rasterio handles reading and writing GeoTIFF files, parsing Well-Known Text (WKT) and EPSG Coordinate Reference Systems, evaluating affine coordinate transformations, and extracting windowed bounding boxes from remote or local rasters.
- **GDAL (Bundled C-Bindings)**: Embedded within the Rasterio binary distribution. GDAL handles low-level geospatial format parsing, decompression (Deflate compression), and virtual filesystem HTTP/S3 network streaming (`/vsicurl/`).

### 9.3 Data Management & Tabular Processing
- **Pandas (v3.0.6)**: Provides tabular data structures used in `src/microreservoir/reporting.py` for structuring analytical results, formatting observation metadata, and exporting CSV reports.

### 9.4 Visualization & Web Interface
- **Streamlit (v1.65.0)**: Powers the interactive web application (`app.py`). Streamlit manages UI widgets, reactive state management (`st.session_state`), tabbed layouts, and file download generation.
- **Plotly (v7.1.0)**: Generates client-side interactive charts, including continuous NDWI heatmaps (`px.imshow`) and surface-water area comparison bar charts (`go.Figure`) with rich hover tooltips.
- **Matplotlib (v3.11.2)**: Used for rendering false-color and true-color RGB composite arrays.

### 9.5 Quality Assurance & Testing
- **pytest (v9.1.1)**: Automated testing framework used to execute the 102 individual test functions across 9 test modules covering all algorithms, edge cases, error conditions, and dashboard components.

---

## 10. Data Source and Dataset Description

### 10.1 Satellite Mission Overview
The satellite data utilized by the project originates from the **Sentinel-2 Multispectral Instrument (MSI)**, a Copernicus Earth observation mission operated by the European Space Agency (ESA). Sentinel-2 captures optical data across 13 spectral channels with a 290 km swath width.

### 10.2 Spectral Bands Utilized
The pipeline specifically requires two primary spectral channels:
- **Band 3 (Green)**: Central wavelength $\approx 560\text{ nm}$, bandwidth $36\text{ nm}$, nominal spatial resolution $10\text{ meters}$. Water bodies exhibit moderate reflectance in the green band, whereas vegetation and bare soil have lower reflectance relative to NIR.
- **Band 8 (Near-Infrared - NIR)**: Central wavelength $\approx 842\text{ nm}$, bandwidth $115\text{ nm}$, nominal spatial resolution $10\text{ meters}$. Clear open water absorbs virtually all incident NIR radiation, resulting in near-zero surface reflectance. Conversely, healthy green vegetation displays high NIR reflectance due to mesophyll leaf scattering.

### 10.3 Public STAC Catalog & Data Acquisition Log
Satellite imagery for the Mettur Reservoir study area was discovered and acquired via the public **Earth Search STAC API** operated by Element 84:
- **Catalog Endpoint**: `https://earth-search.aws.element84.com/v1/search`
- **Collection Identifier**: `sentinel-2-c1-l2a` (Sentinel-2 Collection 1 Level-2A surface reflectance)
- **Study Bounding Box (WGS84)**: `[77.72°E, 11.74°N, 77.90°E, 11.88°N]` (West, South, East, North)
- **Selected Tile**: `MGRS-43PHP`
- **Temporal Epochs Selected**:
  - **Baseline Observation**: `2026-08-30` (Acquisition: `2026-08-30T05:25:28.418Z`, Scene ID: `S2B_T43PHP_20260830T052309_L2A`)
  - **Follow-up Observation**: `2026-09-29` (Acquisition: `2026-09-29T05:25:30.888Z`, Scene ID: `S2B_T43PHP_20260929T052225_L2A`)
  - **Temporal Separation**: 30 days apart

### 10.4 Verified Raster Characteristics (from `download_manifest.json`)
The downloaded and verified rasters stored in `data/real_mettur/` exhibit the following properties:

| Parameter | Baseline Observation (2026-08-30) | Follow-up Observation (2026-09-29) | Verification Status |
| :--- | :--- | :--- | :--- |
| **B03 File Path** | `data/real_mettur/date1_2026-08-30_B03.tif` | `data/real_mettur/date2_2026-09-29_B03.tif` | Verified on disk (3.7 MB / 3.6 MB) |
| **B08 File Path** | `data/real_mettur/date1_2026-08-30_B08.tif` | `data/real_mettur/date2_2026-09-29_B08.tif` | Verified on disk (3.9 MB / 4.0 MB) |
| **Coordinate System (CRS)** | `EPSG:32643` (UTM Zone 43N, projected) | `EPSG:32643` (UTM Zone 43N, projected) | Verified matching |
| **Raster Dimensions** | $1614\text{ width} \times 1571\text{ height}$ | $1614\text{ width} \times 1571\text{ height}$ | Verified identical |
| **Pixel Resolution** | $10.0\text{ m} \times 10.0\text{ m}$ ($100.0\text{ m}^2/\text{pixel}$) | $10.0\text{ m} \times 10.0\text{ m}$ ($100.0\text{ m}^2/\text{pixel}$) | Verified matching |
| **Affine Transform** | `[10.0, 0.0, 799980.0, 0.0, -10.0, 1314940.0]` | `[10.0, 0.0, 799980.0, 0.0, -10.0, 1314940.0]` | Verified identical origin |
| **Total Pixel Count** | $2,535,594\text{ pixels}$ ($1614 \times 1571$) | $2,535,594\text{ pixels}$ ($1614 \times 1571$) | Verified |
| **Valid Pixels Reported** | $2,488,475\text{ pixels}$ ($98.14\%$) | $2,488,475\text{ pixels}$ ($98.14\%$) | Verified |
| **NoData Pixels** | $47,119\text{ pixels}$ ($1.86\%$, outer margin) | $47,119\text{ pixels}$ ($1.86\%$, outer margin) | Verified |
| **Catalog Scene Cloud Cover** | $25.58\%$ (Scene-level catalog metadata) | $19.79\%$ (Scene-level catalog metadata) | Verified |
| **Study Area Overlap Ratio** | $82.6\%$ overlap between study bounding box and tile footprint | $82.6\%$ overlap between study bounding box and tile footprint | Verified (Geometric footprint overlap) |

> [!NOTE]
> **Study Area Overlap vs. Water Coverage**: The reported $82.6\%$ value in the download logs refers strictly to the geometric intersection area between the rectangular study bounding box and the Sentinel-2 MGRS-43PHP tile footprint. It does **not** represent water coverage.

---

## 11. Mathematical Methodology

### 11.1 Normalized Difference Water Index (NDWI)
The Normalized Difference Water Index, originally introduced by McFeeters (1996), is calculated as:

$$\text{NDWI} = \frac{\rho_{\text{Green}} - \rho_{\text{NIR}}}{\rho_{\text{Green}} + \rho_{\text{NIR}}}$$

Where:
- $\rho_{\text{Green}}$ is the surface reflectance in Sentinel-2 Band 3 (Green).
- $\rho_{\text{NIR}}$ is the surface reflectance in Sentinel-2 Band 8 (Near-Infrared).

#### Spectral Principle
- **Water Bodies**: Water absorbs heavily in the NIR region while scattering moderately in the green band ($\rho_{\text{Green}} > \rho_{\text{NIR}}$). Consequently, the numerator is positive, yielding positive NDWI values typically between $+0.1$ and $+0.8$.
- **Vegetation and Soil**: Photosynthetic vegetation strongly reflects NIR radiation due to leaf mesophyll scattering while absorbing green light via chlorophyll ($\rho_{\text{NIR}} \gg \rho_{\text{Green}}$). This makes the numerator strongly negative, producing negative NDWI values typically between $-0.2$ and $-0.8$.
- **Dry Soil and Built-Up Land**: Non-water surfaces generally have higher or comparable NIR reflectance, keeping NDWI below zero.

### 11.2 Numerical Epsilon Division Protection
In digital processing, pixels with zero surface reflectance (such as shadowed voids or sensor anomalies) cause the denominator $\rho_{\text{Green}} + \rho_{\text{NIR}}$ to equal zero. To prevent `ZeroDivisionError` and unhandled IEEE floating-point exceptions (`NaN`/`Inf`), the implementation incorporates a positive numerical epsilon guard ($\epsilon = 10^{-7}$):

$$\text{safe\_denom} = \begin{cases} 1.0 & \text{if } |\rho_{\text{Green}} + \rho_{\text{NIR}}| \le \epsilon \\ \rho_{\text{Green}} + \rho_{\text{NIR}} & \text{otherwise} \end{cases}$$

$$\text{raw\_ndwi} = \begin{cases} 0.0 & \text{if } |\rho_{\text{Green}} + \rho_{\text{NIR}}| \le \epsilon \\ \frac{\rho_{\text{Green}} - \rho_{\text{NIR}}}{\text{safe\_denom}} & \text{otherwise} \end{cases}$$

Pixels failing radiometric validity checks (NaN or Inf in either band) are overwritten with a dedicated invalid sentinel value (`invalid_fill = -1.0`), and the output array is strictly clipped to the theoretical bounds $[-1.0, 1.0]$.

### 11.3 Binary Water Pixel Classification
Classification is executed by applying a user-configurable decision threshold $\tau$ (default $\tau = 0.0$) across valid pixels:

$$\text{WaterMask}(x, y) = \begin{cases} \text{True} & \text{if } \text{NDWI}(x, y) > \tau \text{ and } \text{ValidMask}(x, y) = \text{True} \\ \text{False} & \text{otherwise} \end{cases}$$

> [!IMPORTANT]
> **Strict Inequality**: The implementation applies a strict inequality ($\text{NDWI} > \tau$). A pixel with an index value exactly equal to the threshold is classified as non-water.

### 11.4 Ground Surface Area Estimation
Ground surface area is derived using the 2D linear affine coordinate transformation matrix:

$$\begin{bmatrix} x' \\ y' \end{bmatrix} = \begin{bmatrix} a & b \\ d & e \end{bmatrix} \begin{bmatrix} x \\ y \end{bmatrix} + \begin{bmatrix} c \\ f \end{bmatrix}$$

The physical ground area per pixel in square meters ($m^2$) equals the absolute value of the determinant of the affine transformation tensor:

$$\text{Pixel Area (m}^2\text{)} = |a \cdot e - b \cdot d|$$

For a standard Sentinel-2 UTM raster with $10\text{ m}$ pixel pitch ($a = 10.0, e = -10.0, b = 0.0, d = 0.0$):

$$\text{Pixel Area} = |(10.0) \cdot (-10.0) - (0.0) \cdot (0.0)| = |-100.0| = 100.0\text{ m}^2$$

Total surface water extent is calculated directly:

$$\text{Area (m}^2\text{)} = N_{\text{water}} \times \text{Pixel Area (m}^2\text{)}$$

$$\text{Area (Hectares)} = \text{Area (m}^2\text{)} \times 10^{-4}$$

$$\text{Area (Acres)} = \text{Area (m}^2\text{)} \times 0.000247105$$

Where $N_{\text{water}}$ is the sum of classified water pixels strictly located within valid data boundaries:

$$N_{\text{water}} = \sum_{x, y} (\text{WaterMask}(x, y) \land \text{ValidMask}(x, y))$$

### 11.5 Boundary Mixed-Pixel Uncertainty Quantification
Small water bodies, shallow shorelines, and irrigation channels contain perimeter pixels that straddle the land-water boundary. These edge pixels exhibit composite reflectance signals (mixed spectral signatures). The system models perimeter uncertainty proportional to the square root of the water pixel count:

$$\text{Uncertainty Pixels} = \max\left(1.0, \sqrt{N_{\text{water}}}\right)$$

$$\text{Uncertainty (m}^2\text{)} = \text{Uncertainty Pixels} \times \text{Pixel Area (m}^2\text{)}$$

$$\text{Uncertainty (ha)} = \text{Uncertainty (m}^2\text{)} \times 10^{-4}$$

$$\text{Confidence Interval} = \left[\max\left(0.0, \text{Area}_{\text{ha}} - \text{Uncertainty}_{\text{ha}}\right), \text{Area}_{\text{ha}} + \text{Uncertainty}_{\text{ha}}\right]$$

### 11.6 Multi-Temporal Change & Percentage Shift Formulations
Bi-temporal change compares a baseline observation at time $t_0$ against a comparison observation at time $t_1$ ($t_1 > t_0$):

$$\Delta \text{Area (ha)} = \text{Area}_{t_1} - \text{Area}_{t_0}$$

$$\Delta \text{Area (m}^2\text{)} = \text{Area}_{t_1, \text{m}^2} - \text{Area}_{t_0, \text{m}^2}$$

$$\text{Percentage Change (\%)} = \left(\frac{\text{Area}_{t_1} - \text{Area}_{t_0}}{\text{Area}_{t_0}}\right) \times 100$$

#### Zero-Baseline Protection
When a baseline reservoir is completely dry ($\text{Area}_{t_0} = 0.0\text{ m}^2$), percentage change is mathematically undefined. Rather than dividing by zero or outputting infinity, the pipeline sets:

$$\text{Percentage Change} = \text{None (Reported as "Unavailable")}$$

#### Hydrological Interpretation Warning
A negative percentage change indicates an empirical reduction in detected open-water surface area between the two observation dates. It does **not** automatically confirm regional drought, climate stress, or aquifer depletion; surface shrinkage may result from scheduled agricultural canal releases, seasonal evaporation, or cloud-shadow variation.

---

## 12. Algorithm and Implementation Details

### 12.1 Module Architecture & Responsibilities
The codebase is structured under `src/microreservoir/`:

- `schemas.py`: Strongly-typed dataclasses (`ObservationMetadata`, `Observation`, `ValidationResult`, `WaterDetectionResult`, `AreaEstimate`, `ChangeComparisonResult`, `AlertItem`, `AnalysisResult`).
- `config.py`: Central configuration dataclass (`AppConfig`), default thresholds, status string constants (`STATUS_STABLE`, `STATUS_POTENTIAL_DECLINE`, etc.).
- `exceptions.py`: Custom exception hierarchy (`PathTraversalError`, `CorruptRasterError`, `IncompatibleGridError`, `TemporalOrderError`, `MissingCRSError`, `MissingBandError`, `NoDataError`).
- `geotiff.py`: Low-level raster ingestion using Rasterio. Implements path validation, date verification, metadata extraction, grid compatibility validation, and observation assembly.
- `validation.py`: Data-quality inspection engine. Evaluates array dimensionality, core band presence, NaN/Inf bounds, cloud cover ratios, and valid-pixel coverage.
- `water_detection.py`: Vectorized spectral indexing. Implements `compute_ndwi`, `compute_mndwi`, `compute_awei`, and threshold segmentation (`detect_water`).
- `area_estimation.py`: Physical area quantification engine. Implements `estimate_area`, affine determinant derivation, CRS projection verification, and boundary uncertainty calculation.
- `change_detection.py`: Bi-temporal change comparison engine. Implements `compare_observations`, spatial alignment verification, categorical transition mask generation, and status classification.
- `alerts.py`: Operational alert generation engine. Implements `generate_alerts`, assigning severity ratings (`CRITICAL`, `WARNING`, `INFO`) and advisory actions with quality safeguards.
- `reporting.py`: Pipeline orchestration (`run_analysis`), dashboard data serialization (`build_dashboard_data`), and CSV/JSON report exports.
- `app.py`: Interactive Streamlit application interface.

### 12.2 Real Code Paths and Function Signatures

#### Path Traversal & File Safety (`geotiff.py:validate_safe_path`)
```python
def validate_safe_path(
    path: Union[str, Path],
    base_dir: Optional[Union[str, Path]] = None,
    must_exist: bool = True,
) -> Path:
    # 1. Checks for null bytes (\0)
    # 2. Resolves path to absolute canonical path
    # 3. Enforces that resolved path is relative to base_dir (if provided)
    # 4. Asserts file exists and is not a directory
```

#### GeoTIFF Metadata Extraction (`geotiff.py:read_geotiff_metadata`)
```python
def read_geotiff_metadata(
    path: Union[str, Path],
    base_dir: Optional[Union[str, Path]] = None,
    max_pixels: Optional[int] = None,
) -> Dict[str, Any]:
    # 1. Inspects file size; raises CorruptRasterError if 0 bytes
    # 2. Opens with rasterio.open
    # 3. Validates non-null CRS (raises MissingCRSError if absent)
    # 4. Asserts non-degenerate affine transform (t.a != 0, t.e != 0)
    # 5. Asserts total pixels <= max_pixel_limit (default 25,000,000)
    # 6. Returns dictionary of metadata
```

#### Observation Loading (`geotiff.py:load_geotiff_observation`)
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
) -> Observation:
    # Supports separate single-band files or multiband GeoTIFF with explicit 1-indexed mapping
    # Enforces identical dimensions and CRS across bands
    # Builds valid_mask integrating NoData and external cloud mask
```

#### Vectorized NDWI Computation (`water_detection.py:compute_ndwi`)
```python
def compute_ndwi(
    green: np.ndarray,
    nir: np.ndarray,
    eps: float = 1e-7,
    invalid_fill: float = -1.0,
) -> np.ndarray:
    # 1. Validates green and nir are 2D arrays with identical shape
    # 2. Casts to float32
    # 3. Identifies zero denominators (|g + n| <= eps) and invalid entries (NaN/Inf)
    # 4. Computes safe division and clips output to [-1.0, 1.0]
```

#### End-to-End Orchestration (`reporting.py:run_analysis`)
```python
def run_analysis(
    baseline_obs: Observation,
    comparison_obs: Observation,
    cfg: Optional[AppConfig] = None,
) -> AnalysisResult:
    # 1. validate_observation on baseline and comparison
    # 2. detect_water on baseline and comparison
    # 3. estimate_area on baseline and comparison
    # 4. compare_observations (verifies grid alignment, dates, deltas, transition mask)
    # 5. generate_alerts (evaluates quality, decline thresholds, advisories)
    # 6. Returns consolidated AnalysisResult
```

---

## 13. Project Directory Structure

The directory structure of the project is documented below:

```
MICRO-RESERVOIR/
│
├── .env.example                               # Template for optional environment variables
├── .gitignore                                  # Git exclusion rules (venv, caches, large rasters)
├── README.md                                   # Root project overview and documentation
├── requirements.txt                            # Pinned Python package dependencies
├── config.py                                   # System thresholds, constants, and AppConfig
├── app.py                                      # Streamlit interactive dashboard entry point
├── download_mettur_sentinel2.py                # Public STAC Sentinel-2 downloader for Mettur
│
├── data/                                       # Workspace data directory
│   ├── README.md                               # Dataset documentation, sources, and licenses
│   ├── processed/                              # Generated summaries and demo outputs
│   │   ├── .gitkeep
│   │   └── demo_summary.json                   # Output from CLI demo runner
│   ├── real_mettur/                            # Downloaded genuine Sentinel-2 GeoTIFFs
│   │   ├── date1_2026-08-30_B03.tif            # Mettur baseline Green band (1614x1571, 3.7 MB)
│   │   ├── date1_2026-08-30_B08.tif            # Mettur baseline NIR band (1614x1571, 3.9 MB)
│   │   ├── date2_2026-09-29_B03.tif            # Mettur follow-up Green band (1614x1571, 3.6 MB)
│   │   ├── date2_2026-09-29_B08.tif            # Mettur follow-up NIR band (1614x1571, 4.0 MB)
│   └── samples/                                # Offline synthetic benchmark fixtures
│       ├── res01_20231015.npz                  # Scenario 1 baseline synthetic array
│       ├── res01_20240315.npz                  # Scenario 1 follow-up (Seasonal drawdown)
│       ├── res02_20240520.npz                  # Scenario 2 baseline synthetic array
│       ├── res02_20240810.npz                  # Scenario 2 follow-up (Monsoon recharge)
│       ├── res03_20231101.npz                  # Scenario 3 baseline synthetic array
│       ├── res03_20231121.npz                  # Scenario 3 follow-up (Stable storage)
│       ├── res04_20240705.npz                  # Scenario 4 baseline synthetic array
│       ├── res04_20240725.npz                  # Scenario 4 follow-up (Cloud obscuration)
│       └── sample_manifest.json                # Synthetic scenario catalog
│
├── docs/                                       # Technical documentation repository
│   ├── api-contract.md                         # Detailed API method signatures and contracts
│   ├── architecture.md                         # System architecture and design documentation
│   ├── demo-script.md                          # 3-minute evaluation presentation script
│   ├── validation-report.md                    # Verification logs and test outputs
│   ├── PROJECT_DOCUMENTATION_REPORT.md         # Complete Markdown technical report (this document)
│   ├── PROJECT_DOCUMENTATION_REPORT.docx       # Primary Word documentation report
│   ├── ARCHITECTURE.md                         # Expanded architecture specification
│   ├── USER_GUIDE.md                           # Operational user manual
│   └── VALIDATION_AND_LIMITATIONS.md           # Technical validation and limitations audit
│
├── scripts/                                    # Automation and demonstration utilities
│   ├── prepare_sample.py                       # Generates synthetic test fixtures
│   └── run_demo.py                             # Non-interactive CLI demonstration runner
│
├── src/                                        # Core application package
│   └── microreservoir/                         # Main package namespace
│       ├── __init__.py                         # Package exports and version metadata (v0.2.0)
│       ├── alerts.py                           # Operational alert generation logic
│       ├── area_estimation.py                  # Physical surface area & uncertainty calculation
│       ├── change_detection.py                 # Multi-temporal comparison & transition mapping
│       ├── exceptions.py                       # Structured custom exception hierarchy
│       ├── geotiff.py                          # GeoTIFF I/O, validation, and metadata extraction
│       ├── preprocessing.py                    # Reflectance scaling and RGB composite rendering
│       ├── reporting.py                        # Pipeline runner and report serialization
│       ├── schemas.py                          # Data contracts and typed dataclasses
│       ├── validation.py                       # Quality checks and input validation rules
│       └── water_detection.py                  # NDWI, MNDWI, AWEI indexing algorithms
│
├── tests/                                      # Automated testing suite (102 tests)
│   ├── conftest.py                             # Pytest fixtures and mock raster generators
│   ├── test_alerts.py                          # Unit tests for alert rules (8 tests)
│   ├── test_area_estimation.py                 # Unit tests for area calculation & CRS (9 tests)
│   ├── test_change_detection.py                # Unit tests for temporal comparisons (15 tests)
│   ├── test_dashboard.py                       # Integration tests for UI & exports (8 tests)
│   ├── test_download_script.py                 # Tests for STAC downloader logic (5 tests)
│   ├── test_end_to_end.py                      # Full end-to-end integration test (1 test)
│   ├── test_geotiff.py                         # Tests for raster ingestion & safety (34 tests)
│   ├── test_validation.py                      # Tests for observation validation (8 tests)
│   └── test_water_detection.py                 # Tests for NDWI vector math & bounds (14 tests)
│
└── micro-reservoir-intelligence/               # Nested application mirror directory
    ├── .env.example
    ├── .gitignore
    ├── README.md
    ├── requirements.txt
    ├── config.py
    ├── app.py
    ├── data/                                   # Mirrored data directory (real_mettur & samples)
    ├── docs/                                   # Documentation deliverables directory
    ├── scripts/                                # Utility scripts
    ├── src/                                    # Source modules
    └── tests/                                  # Test suite
```

---

## 14. Dashboard and User Guide

### 14.1 Launching the Application
To launch the interactive dashboard, open a terminal (PowerShell on Windows) and run:

```powershell
# From the project root:
.\.venv\Scripts\python.exe -m streamlit run app.py

# Or from the nested application directory:
cd micro-reservoir-intelligence
..\.venv\Scripts\python.exe -m streamlit run app.py
```

The Streamlit web application opens automatically in your default browser at `http://localhost:8501`.

### 14.2 Operating Mode 1: Local GeoTIFF Files (Real Satellite Analysis)
To process the downloaded Sentinel-2 observations over the Mettur Reservoir study area:

1. In the left sidebar under **Input Data Source**, select **📁 Local GeoTIFF Files**.
2. Set **Reservoir Identifier**: Enter a descriptive code (e.g., `METTUR-RES-01` or `Stanley Reservoir`).
3. Set **Water Index Algorithm**: Select `NDWI` (standard for Green B03 and NIR B08).
4. Set **Index Decision Threshold**: Leave at `0.0` (standard water classification cutoff).
5. In the main input area under **1️⃣ Baseline Observation**:
   - **Baseline Scene ID**: Enter `REAL_METTUR_2026-08-30`.
   - **Baseline Acquisition Date**: Enter `2026-08-30`.
   - **Baseline Raster Layout**: Select `Separate Single-Band Files`.
   - **Green Band (B03) GeoTIFF Path**: Enter `data/real_mettur/date1_2026-08-30_B03.tif` (or `micro-reservoir-intelligence/data/real_mettur/date1_2026-08-30_B03.tif` if running from root).
   - **NIR Band (B08) GeoTIFF Path**: Enter `data/real_mettur/date1_2026-08-30_B08.tif` (or `micro-reservoir-intelligence/data/real_mettur/date1_2026-08-30_B08.tif` if running from root).
   - **Cloud Mask Path**: Leave blank (no local mask available).
6. Under **2️⃣ Follow-up (Comparison) Observation**:
   - **Comparison Scene ID**: Enter `REAL_METTUR_2026-09-29`.
   - **Comparison Acquisition Date**: Enter `2026-09-29`.
   - **Comparison Raster Layout**: Select `Separate Single-Band Files`.
   - **Green Band (B03) GeoTIFF Path**: Enter `data/real_mettur/date2_2026-09-29_B03.tif` (or `micro-reservoir-intelligence/data/real_mettur/date2_2026-09-29_B03.tif` if running from root).
   - **NIR Band (B08) GeoTIFF Path**: Enter `data/real_mettur/date2_2026-09-29_B08.tif` (or `micro-reservoir-intelligence/data/real_mettur/date2_2026-09-29_B08.tif` if running from root).
   - **Cloud Mask Path**: Leave blank.
7. Click the primary button: **🔍 Run Multi-Temporal Analysis**.

### 14.3 Operating Mode 2: Synthetic Test Scenarios (Offline Benchmark Exploration)
When live satellite GeoTIFFs are not available, users can explore pipeline mechanics using Mode 2:
1. Select **🧪 Synthetic Test Scenarios (Demo Mode)** in the sidebar.
2. Select one of four pre-configured scenarios:
   - `Seasonal Reservoir Drawdown`: Simulates severe summer depletion (Expected status: `POTENTIAL_DECLINE`, `CRITICAL` alert).
   - `Monsoon Inflow Recharge`: Simulates post-monsoon storage expansion (Expected status: `POTENTIAL_INCREASE`, `INFO` alert).
   - `Controlled Stable Storage`: Simulates minor normal fluctuation (Expected status: `STABLE`, `INFO` alert).
   - `Cloud Obscuration Deficit`: Simulates severe cloud contamination (Expected status: `INSUFFICIENT_DATA`, `WARNING` alert).
3. Click **🔍 Run Multi-Temporal Analysis**.

> [!WARNING]
> **Synthetic Data Disclaimer**: Mode 2 outputs are generated from simulated benchmark arrays strictly intended to verify software mechanics. They do **not** reflect real physical satellite observations and must never be reported as actual environmental measurements.

### 14.4 Dashboard Inspection Tabs
Once analysis completes, the dashboard displays:
- **Top Summary Header**: Reservoir ID, baseline and comparison scene metadata, and a colored status badge (`STABLE`, `POTENTIAL DECLINE`, `POTENTIAL INCREASE`, `INSUFFICIENT DATA`, `INVALID COMPARISON`).
- **Primary KPI Cards**: Baseline Area (ha, m², px), Follow-up Area (ha, m², px), Net Surface Area Shift (ha, %), and Confidence Index.
- **Tab 1: 🛰️ Spectral Imagery & NDWI**: Side-by-side interactive Plotly heatmaps of continuous NDWI values with zoom and pan controls.
- **Tab 2: 💧 Classified Water Masks**: Binary surface-water classification masks with computed mixed-pixel uncertainty ranges.
- **Tab 3: 🔄 Transition Change Map**: Categorical 2D transition image (Blue = Persistent Water, Red = Water Lost / Retreat, Green = Water Gained / Expansion, Gray = Invalid/NoData) with pixel and hectare area breakdowns.
- **Tab 4: 📊 Comparison Chart**: Interactive Plotly bar chart comparing baseline and follow-up water coverage alongside a structured summary table.
- **Tab 5: 🛡️ Quality Pre-Flight Checks**: Five-point audit panel verifying CRS projection, dimension match, ground resolution alignment, valid coverage ratio, cloud screening, and temporal precedence.
- **Tab 6: ⚠️ Operational Alerts**: Graded advisory cards (`CRITICAL`, `WARNING`, `INFO`) displaying alert explanations and recommended field actions.
- **Tab 7: 📥 Export Reports**: Download buttons for formatted CSV reports and machine-readable JSON payloads containing full analysis metadata.

---

## 15. Validation and Testing

### 15.1 Testing Strategy & Implementation
The testing architecture is organized around 102 individual automated test cases implemented with pytest. The tests execute on CPU without internet access or GPU acceleration.

### 15.2 Test Module Breakdown

| Test Module | Test Count | Scope & Verification Coverage |
| :--- | :--- | :--- |
| `tests/test_alerts.py` | 8 tests | Critical decline alerting, quality-check failure suppression, moderate decline, expansion notifications, zero-baseline safety, insufficient data handling, invalid comparison alerts, stable state notifications. |
| `tests/test_area_estimation.py` | 9 tests | Standard area formula ($100\text{ px} = 1.0\text{ ha}$), variable pixel resolutions (15m, 20m, 30m), affine transformation determinants, geographic unprojected CRS rejection, NoData pixel exclusion, zero-pixel boundary handling, non-positive resolution rejection. |
| `tests/test_change_detection.py` | 15 tests | Absolute and percentage delta calculations, zero-baseline division protection ($0 \to 0$ and $0 \to >0$), decline/increase/stable status classifications, spatial dimension mismatch rejection, CRS mismatch rejection, reversed temporal order rejection, coverage and cloud thresholds, categorical transition mask values. |
| `tests/test_dashboard.py` | 8 tests | HTML status badge rendering, Plotly comparison bar chart generation, CSV export formatting, JSON report serialization, cloud limitation disclosure, synthetic vs. genuine manifest classification, Streamlit headless startup via `AppTest`. |
| `tests/test_download_script.py` | 5 tests | Docstring syntax warning check, bounding box overlap calculation (`bbox_overlap_ratio`), STAC asset resolution (`get_asset`), high-coverage tile selection (`choose_pair`), spatial raster validation (`validate_downloaded_rasters`). |
| `tests/test_end_to_end.py` | 1 test | Complete pipeline integration: ingestion, validation, NDWI extraction, area estimation, change detection, alerting, and report export. |
| `tests/test_geotiff.py` | 34 tests | Single-band and multiband GeoTIFF ingestion, explicit 1-indexed band mapping, path traversal attack prevention (`../`), null-byte injection rejection, maximum pixel limit enforcement (`max_pixel_limit`), CRS validation, affine alignment checks, ISO-8601 date parsing, temporal precedence validation, NoData masking. |
| `tests/test_validation.py` | 8 tests | Observation validation, core band presence verification, shape mismatch detection, empty band handling, cloud cover limit warnings, low valid-pixel ratio warnings, date format validation. |
| `tests/test_water_detection.py` | 14 tests | Vectorized NDWI math, positive/negative reflectance behavior, zero-denominator epsilon safety ($10^{-7}$), NaN and Inf sanitization, array shape compatibility, threshold boundary conditions (`> 0.0`), validity mask preservation, statistical distributions, heuristic classification caveat warnings. |
| **Total Test Suite** | **102 tests** | **100% Pass Rate across all modules** |

### 15.3 Test Execution Evidence
When executed from the project root, pytest discovers both the root test directory and the nested application test directory, collecting 204 test items (102 unique tests duplicated across workspace trees):

```text
============================= test session starts =============================
platform win32 -- Python 3.12.14, pytest-9.1.1, pluggy-1.6.0
rootdir: C:\Users\gokul\Documents\MICRO-RESERVOIR
plugins: anyio-4.15.1
collected 204 items

micro-reservoir-intelligence\tests\test_alerts.py ........               [  3%]
micro-reservoir-intelligence\tests\test_area_estimation.py .........     [  8%]
micro-reservoir-intelligence\tests\test_change_detection.py ............ [ 14%]
...                                                                      [ 15%]
micro-reservoir-intelligence\tests\test_dashboard.py ........            [ 19%]
micro-reservoir-intelligence\tests\test_download_script.py .....         [ 22%]
micro-reservoir-intelligence\tests\test_end_to_end.py .                  [ 22%]
micro-reservoir-intelligence\tests\test_geotiff.py ..................... [ 32%]
.............                                                            [ 39%]
micro-reservoir-intelligence\tests\test_validation.py ........           [ 43%]
micro-reservoir-intelligence\tests\test_water_detection.py ............. [ 49%]
.                                                                        [ 50%]
tests\test_alerts.py ........                                            [ 53%]
tests\test_area_estimation.py .........                                  [ 58%]
tests\test_change_detection.py ...............                           [ 65%]
tests\test_dashboard.py ........                                         [ 69%]
tests\test_download_script.py .....                                      [ 72%]
tests\test_end_to_end.py .                                               [ 72%]
tests\test_geotiff.py ..................................                 [ 89%]
tests\test_validation.py ........                                        [ 93%]
tests\test_water_detection.py ..............                             [100%]

============================ 204 passed in 10.37s =============================
```

When executed specifically inside `micro-reservoir-intelligence` with `PYTHONPATH=".."`:
```text
============================= 102 passed in 4.37s =============================
```

### 15.4 Scope and Limits of Software Testing
It is vital to distinguish between software testing and scientific validation:
- **What Automated Tests Prove**: The tests prove that the code executes without syntax or runtime exceptions, that mathematical functions correctly implement their defined formulas, that zero-division conditions are safely trapped, that spatial invariants (matching CRS, resolution, transform) are enforced, that malicious path traversal is blocked, and that reporting outputs conform to expected schema definitions.
- **What Automated Tests Do NOT Prove**: Software tests do **not** prove that NDWI is 100% accurate under turbid or algae-rich water conditions, do not calibrate water classification against on-ground GPS survey perimeters, and do not validate reservoir storage capacity without bathymetric data.

---

## 16. Results and Discussion

### 16.1 Verified Real Data Results: Mettur Reservoir Study Area
The four genuine Sentinel-2 Level-2A GeoTIFF rasters downloaded by `download_mettur_sentinel2.py` were ingested and evaluated through the core analysis engine (`run_analysis`). The results are:

| Metric / Parameter | Baseline Observation | Follow-up Observation | Net Differential ($\Delta$) |
| :--- | :--- | :--- | :--- |
| **Observation Date** | `2026-08-30` | `2026-09-29` | 30 days temporal separation |
| **Sentinel-2 Scene ID** | `REAL_METTUR_2026-08-30` | `REAL_METTUR_2026-09-29` | Same tile `MGRS-43PHP` |
| **Classified Water Pixels** | $342,744\text{ pixels}$ | $312,046\text{ pixels}$ | $-30,698\text{ pixels}$ |
| **Water Surface Area (m²)** | $34,274,400.0\text{ m}^2$ | $31,204,600.0\text{ m}^2$ | $-3,069,800.0\text{ m}^2$ |
| **Water Surface Area (Hectares)** | **$3,427.44\text{ ha}$** | **$3,120.46\text{ ha}$** | **$-306.98\text{ ha}$** |
| **Water Surface Area (Acres)** | $8,469.37\text{ acres}$ | $7,710.82\text{ acres}$ | $-758.55\text{ acres}$ |
| **Relative Area Shift (%)** | — | — | **$-8.96\%$** |
| **Boundary Uncertainty Range** | $[3421.59, 3433.29]\text{ ha}$ ($\pm 5.85\text{ ha}$) | $[3114.87, 3126.05]\text{ ha}$ ($\pm 5.59\text{ ha}$) | — |
| **Operational Status** | — | — | **`stable`** (Shift is within $\pm 10.0\%$) |
| **Confidence Score** | — | — | **$77\%$** (Average catalog cloud: $22.7\%$) |
| **Active Operational Alerts** | — | — | **`[INFO] Reservoir Area Stable`** |
| **Data Quality Verification** | Passed pre-flight checks | Passed pre-flight checks | `quality_passed = True` |

### 16.2 Discussion of Empirical Findings
1. **Measured Area Dynamics**: Between August 30, 2026, and September 29, 2026, the detected surface water extent inside the Mettur study window decreased by $306.98\text{ ha}$ ($3,069,800\text{ m}^2$), representing an $8.96\%$ contraction.
2. **Status Threshold Evaluation**: Because the default alert threshold for `potential_decline` is configured at $-10.0\%$, the observed reduction of $-8.96\%$ does not exceed the decline threshold. Consequently, the operational status is categorized as **`stable`**, triggering an `INFO` operational notification.
3. **Traceability of Previously Reported Values**: The empirical results ($3,427.44\text{ ha}$ and $3,120.46\text{ ha}$) correspond exactly to the previously reported preliminary estimates of $3,427.4\text{ ha}$ and $3,120.5\text{ ha}$.
4. **Boundary and Cloud Caveats**: As documented in the download manifest, no local pixel-level cloud mask was evaluated. Furthermore, the rectangular study area captures portions of the Kaveri River arm and riparian margins surrounding the reservoir. Therefore, these values are **preliminary screening measurements** and must not be cited as certified reservoir storage data without ground validation.

---

## 17. Limitations and Risk Analysis

### 17.1 Optical Cloud and Cloud-Shadow Contamination
Optical sensors cannot penetrate cloud cover. While catalog metadata indicated scene cloud cover of $25.58\%$ and $19.79\%$, scene-level metrics represent the entire 100 km × 100 km Sentinel-2 tile. Local cloud patches or cloud shadows situated directly over the water body can distort measurements:
- Cloud cover directly obscures water, causing false-negative omissions.
- Cloud shadows reduce reflectance across all bands, mimicking the low NIR reflectance of water and potentially causing false-positive water classifications.

### 17.2 Study Area Geometry vs. Surveyed Boundary
The current study window uses a rectangular bounding box (`77.72°E` to `77.90°E`, `11.74°N` to `11.88°N`). This bounding box captures agricultural fields, river stretches, and surrounding settlements in addition to the reservoir body. While the NDWI threshold isolates open water, any adjacent irrigation pond or flooded paddy field inside the bounding box is included in the aggregate area count.

### 17.3 Spectral Heuristic Classification Ambiguities
The Normalized Difference Water Index is an empirical ratio heuristic subject to known spectral confusions:
- **Mountain and Topographic Shadow**: Steep terrain cast shadows exhibit low reflectance in both green and NIR bands, occasionally mimicking water.
- **Water Turbidity and Suspended Sediment**: High sediment loads in post-monsoon runoff increase NIR scattering, depressing NDWI values and causing shallow turbid water to be omitted.
- **Eutrophication and Algal Blooms**: Dense chlorophyll concentrations on the water surface reflect NIR light, occasionally depressing NDWI below $0.0$.
- **Dark Soil and Urban Concrete**: Asphalt and dark basaltic soils can produce NDWI values near zero, requiring careful threshold tuning.

### 17.4 Surface Water Area vs. Hydrological Storage Volume
Satellite imagery captures two-dimensional horizontal surface area ($m^2$, ha). Reservoirs possess three-dimensional bathymetry. Due to non-linear stage-storage relationships, a small change in water surface area in shallow shelving arms may correspond to negligible volume loss, whereas vertical drop in a steep-sided gorge can represent substantial volume depletion with minimal surface area shift. Surface area observations must not be interpreted as storage volume without bathymetric elevation models.

### 17.5 Bi-Temporal Observation Horizon
Evaluating two discrete satellite overpasses separated by 30 days provides a snapshot comparison. It does not establish continuous depletion trajectories or account for transient rainfall events that may have temporarily replenished the reservoir between overpasses.

---

## 18. Security, Reliability, and Error Handling

### 18.1 Filesystem Path Traversal Prevention
Local file handling implements security checks in `src/microreservoir/geotiff.py:validate_safe_path`:
- **Null-Byte Injection Blocking**: Paths containing null-byte characters (`\0`) trigger an immediate `PathTraversalError`.
- **Directory Traversal Containment**: Relative path components (such as `../`) are resolved to canonical absolute paths and validated against permitted directory roots using `Path.resolve().is_relative_to(...)`.
- **Directory Type Guard**: Asserts that paths point to regular files, rejecting directory paths with actionable error messages.

### 18.2 Memory Safety & Pixel Limits
To protect CPU laptop environments from out-of-memory crashes when handling unclipped full-scene satellite rasters, the pipeline enforces a maximum pixel safety limit (`max_pixel_limit = 25,000,000` pixels, or approximately $5000 \times 5000$). Rasters exceeding this threshold raise a descriptive `RasterReadError` advising the user to clip the raster to the area of interest before ingestion.

### 18.3 HTTP Resilience in Downloader
The downloader script (`download_mettur_sentinel2.py`) implements resilient network mechanisms:
- Configures GDAL `/vsicurl/` parameters (`GDAL_HTTP_MAX_RETRY = 4`, `GDAL_HTTP_TIMEOUT = 30`, `GDAL_HTTP_MULTIRANGE = YES`).
- Implements exponential backoff on HTTP read errors.
- Provides actionable diagnostic error messages with network troubleshooting steps upon failure.

### 18.4 Structured Exception Hierarchy
All errors inherit from `MicroReservoirError` under `src/microreservoir/exceptions.py`:
- `RasterReadError`, `CorruptRasterError`, `UnsupportedRasterError`
- `MissingBandError`, `MissingCRSError`, `IncompatibleGridError`
- `InvalidDateError`, `TemporalOrderError`
- `PathTraversalError`, `NoDataError`

---

## 19. Applications and Benefits

### 19.1 Potential Practical Applications
- **Preliminary Reservoir Depletion Screening**: Providing regional water resource analysts with rapid, automated screening of potential surface storage shrinkage between pre- and post-monsoon periods.
- **Ungauged Micro-Reservoir Monitoring**: Extending observation capabilities to rural percolation tanks, farm ponds, and community check dams that lack physical telemetry.
- **Irrigation Planning Support**: Assisting agricultural extension officers in estimating available open surface storage before releasing water for seasonal crop cultivation.
- **Environmental & Shoreline Observation**: Tracking receding shorelines, identifying sediment accretion zones, and flagging localized evaporative shrinkage.

### 19.2 Operational Benefits
- **Zero Operating Costs**: Relies entirely on free, open Sentinel-2 satellite data and open-source Python libraries.
- **Hardware Accessibility**: Runs efficiently on standard CPU-only laptops without requiring cloud compute accounts or GPUs.
- **Data Integrity Safeguards**: Enforces strict geospatial checks, mixed-pixel uncertainty bounds, and quality-aware alert suppression.

---

## 20. Future Enhancements

The following enhancements are prioritized for future development phases:

1. **Automated Local Cloud & Shadow Masking**: Integrate the native Sentinel-2 Scene Classification Layer (SCL) or automated CloudScore algorithms to mask clouds and cloud shadows at the pixel level.
2. **Administrative Reservoir Boundary Shapefile Integration**: Ingest official vector polygons (GeoJSON/Shapefile) to clip analysis strictly to gazetted full-reservoir levels (FRL), eliminating surrounding land features.
3. **Dynamic & Sensitivity Thresholding**: Implement automated Otsu thresholding alongside the fixed $0.0$ threshold to adapt to seasonal turbidity shifts.
4. **Interactive Geospatial Map Overlays**: Export classified water masks and transition categories as georeferenced GeoTIFFs or vector polygons for overlay in Leaflet/Mapbox mapping widgets.
5. **Multi-Temporal Dense Time-Series Trends**: Extend comparison from two dates to continuous multi-year time-series analysis with automated seasonal anomaly detection.
6. **Bathymetry & In-Situ Level Integration**: Integrate Digital Elevation Models (DEMs) and depth-capacity curves to translate surface area into physical storage volume ($m^3$).
7. **Ground-Truth Calibration**: Validate satellite extraction against physical water level telemetry and differential GPS perimeter surveys.
8. **Automated Batch Processing Daemon**: Package the downloader and analysis pipeline into a scheduled daemon for continuous automated reservoir monitoring.

---

## 21. Conclusion

**Micro-Reservoir Intelligence** provides an automated, lightweight, and thoroughly verified software solution for monitoring reservoir surface-water extent using Sentinel-2 multispectral satellite imagery. The system successfully combines vectorized Normalized Difference Water Index (NDWI) extraction, affine transformation-based physical area quantification, quality-aware bi-temporal change detection, and tiered operational alerting on standard CPU hardware.

The implementation was verified through an automated test suite of 102 individual tests (204 tests collected across workspace scopes) with a 100% pass rate. Evaluation on real Sentinel-2 Level-2A imagery over the Mettur Reservoir study area between August 30, 2026, and September 29, 2026, confirmed an estimated water surface contraction from $3,427.44\text{ ha}$ to $3,120.46\text{ ha}$ ($-8.96\%$), classified as operational state `stable`. 

The software architecture enforces rigorous geospatial standards, path safety, memory containment, and data honesty, clearly distinguishing synthetic benchmark demonstrations from verified satellite observations and providing explicit hydrological caveats. With proposed future integrations—such as pixel-level cloud masking and surveyed boundary shapefile clipping—the system offers a reliable foundation for decision-support and screening in water resource management.

---

## 22. References

1. **McFeeters, S. K. (1996)**. *The use of the Normalized Difference Water Index (NDWI) in the delineation of open water features*. International Journal of Remote Sensing, 17(7), 1425–1432. [doi:10.1080/01431169608948714](https://doi.org/10.1080/01431169608948714)
2. **Xu, H. (2006)**. *Modification of normalised difference water index (MNDWI) to enhance open water features in remotely sensed imagery*. International Journal of Remote Sensing, 27(14), 3025–3033. [doi:10.1080/01431160600589179](https://doi.org/10.1080/01431160600589179)
3. **Feyisa, G. L., Meilby, H., Fensholt, R., & Proud, S. R. (2014)**. *Automated Water Extraction Index: A new technique for surface water mapping using Landsat imagery*. Remote Sensing of Environment, 140, 23–35. [doi:10.1016/j.rse.2013.08.029](https://doi.org/10.1016/j.rse.2013.08.029)
4. **European Space Agency (ESA)**. *Sentinel-2 User Handbook*. Standard document GMES-GSEG-EOPG-TN-13-0002. [https://sentinel.esa.int/web/sentinel/user-guides/sentinel-2-msi](https://sentinel.esa.int/web/sentinel/user-guides/sentinel-2-msi)
5. **SpatioTemporal Asset Catalog (STAC) Specification**. *STAC API Specification v1.0.0*. [https://stacspec.org/](https://stacspec.org/)
6. **Gillies, S., et al. (2013–2024)**. *Rasterio: Geospatial raster I/O for Python*. [https://github.com/rasterio/rasterio](https://github.com/rasterio/rasterio)
7. **GDAL/OGR contributors (2024)**. *GDAL: Geospatial Data Abstraction Library*. Open Source Geospatial Foundation. [https://gdal.org/](https://gdal.org/)
8. **Harris, C. R., et al. (2020)**. *Array programming with NumPy*. Nature, 585, 357–362. [doi:10.1038/s41586-020-2649-2](https://doi.org/10.1038/s41586-020-2649-2)
9. **Streamlit Inc. (2024)**. *Streamlit Documentation*. [https://docs.streamlit.io/](https://docs.streamlit.io/)

---

## Appendices

### Appendix A: Exact Windows Commands

All commands verified on Windows 11 with PowerShell in workspace `C:\Users\gokul\Documents\MICRO-RESERVOIR`:

#### 1. Automated Test Suite Execution (Root Directory)
```powershell
.\.venv\Scripts\python.exe -m pytest
```
*Expected Output*: `204 passed` (102 tests in root and 102 in nested directory).

#### 2. Automated Test Suite Execution (Nested Directory)
```powershell
cd micro-reservoir-intelligence
$env:PYTHONPATH = ".."
..\.venv\Scripts\python.exe -m pytest
```
*Expected Output*: `102 passed in ~4.4 seconds`.

#### 3. Launching the Interactive Web Dashboard
```powershell
# From nested application directory:
cd micro-reservoir-intelligence
..\.venv\Scripts\python.exe -m streamlit run app.py

# Or from project root:
.\.venv\Scripts\python.exe -m streamlit run app.py
```
*Expected Result*: Opens web dashboard at `http://localhost:8501`.

#### 4. Executing the Satellite Downloader
```powershell
# Requires active internet connection to query AWS Earth Search STAC:
.\.venv\Scripts\python.exe .\download_mettur_sentinel2.py
```
*Note*: The downloader requires internet access to query the STAC API and stream remote COG rasters. Once downloaded, dashboard execution using local files runs completely offline.

#### 5. Executing the Command-Line Demo Runner
```powershell
.\.venv\Scripts\python.exe scripts/run_demo.py
```
*Expected Result*: Evaluates all 4 synthetic scenarios and outputs `data/processed/demo_summary.json`.

---

### Appendix B: Input File Inventory

| File Path | Description | Dimensions / Size | Format / CRS |
| :--- | :--- | :--- | :--- |
| `data/real_mettur/date1_2026-08-30_B03.tif` | Mettur Baseline Green Band (2026-08-30) | $1614 \times 1571$ (3.7 MB) | GeoTIFF / `EPSG:32643` |
| `data/real_mettur/date1_2026-08-30_B08.tif` | Mettur Baseline NIR Band (2026-08-30) | $1614 \times 1571$ (3.9 MB) | GeoTIFF / `EPSG:32643` |
| `data/real_mettur/date2_2026-09-29_B03.tif` | Mettur Follow-up Green Band (2026-09-29) | $1614 \times 1571$ (3.6 MB) | GeoTIFF / `EPSG:32643` |
| `data/real_mettur/date2_2026-09-29_B08.tif` | Mettur Follow-up NIR Band (2026-09-29) | $1614 \times 1571$ (4.0 MB) | GeoTIFF / `EPSG:32643` |
| `data/real_mettur/download_manifest.json` | STAC download metadata & verification log | 125 lines (3.9 KB) | JSON (UTF-8) |
| `data/samples/sample_manifest.json` | Catalog of synthetic benchmark scenarios | 70 lines (2.4 KB) | JSON (UTF-8) |
| `data/samples/res01_20231015.npz` | Synthetic test array: Baseline 100x100 | $100 \times 100$ (31 KB) | NumPy compressed archive |
| `data/samples/res01_20240315.npz` | Synthetic test array: Drawdown 100x100 | $100 \times 100$ (31 KB) | NumPy compressed archive |

---

### Appendix C: Key Configuration Parameters

Parameters defined in `config.py:AppConfig`:

| Configuration Key | Default Value | Environment Variable Override | Purpose |
| :--- | :--- | :--- | :--- |
| `default_water_index` | `"NDWI"` | `DEFAULT_WATER_INDEX` | Primary spectral index algorithm |
| `ndwi_threshold` | `0.0` | `NDWI_WATER_THRESHOLD` | Cutoff above which pixels are water |
| `decline_threshold_percent` | `-10.0` | `ALERT_DECLINE_THRESHOLD_PERCENT` | Percentage loss triggering `potential_decline` |
| `critical_decline_threshold_percent`| `-25.0` | `ALERT_CRITICAL_DECLINE_THRESHOLD_PERCENT`| Severe percentage loss triggering `CRITICAL` alert |
| `increase_threshold_percent`| `10.0` | `ALERT_INCREASE_THRESHOLD_PERCENT`| Percentage gain triggering `potential_increase` |
| `min_valid_pixel_ratio` | `0.70` ($70\%$) | `MIN_VALID_PIXEL_RATIO` | Minimum coverage required for analysis |
| `max_cloud_cover_percent` | `20.0` ($20\%$) | `MAX_CLOUD_COVER_PERCENT` | Maximum cloud obscuration permitted |
| `max_pixel_limit` | `25,000,000` | `MAX_PIXEL_LIMIT` | Laptop CPU memory safety limit |
| `default_crs` | `"EPSG:32643"` | `DEFAULT_CRS` | Fallback projected coordinate reference system |
| `m2_to_hectare` | `0.0001` | — | Multiplier converting $m^2$ to hectares |
| `m2_to_acre` | `0.000247105` | — | Multiplier converting $m^2$ to acres |

---

### Appendix D: Glossary of Technical Terms

- **Affine Transformation**: A geometric mapping that preserves collinearity and ratios of distances, translating raster row and column indices into real-world geographic coordinates.
- **COG (Cloud-Optimized GeoTIFF)**: A GeoTIFF file formatted with internal tiling and overviews, allowing HTTP range requests to read specific spatial windows without downloading the complete raster.
- **CRS (Coordinate Reference System)**: A coordinate system that relates numerical spatial coordinates to locations on the Earth's surface. Planar projected CRS (e.g., UTM) uses linear meter units.
- **Level-2A (L2A)**: Bottom-of-atmosphere (BOA) surface reflectance imagery corrected for atmospheric scattering and absorption.
- **MGRS (Military Grid Reference System)**: A geographic grid reference system used to index Sentinel-2 tiles (e.g., `43PHP`).
- **MNDWI (Modified Normalized Difference Water Index)**: A spectral index combining Green and Shortwave-Infrared (SWIR) bands to enhance water features while suppressing built-up urban features.
- **NDWI (Normalized Difference Water Index)**: A spectral index combining Green and Near-Infrared (NIR) bands to delineate surface water bodies.
- **NoData**: A designated numerical value indicating missing, unmeasured, or invalid data in a raster.
- **STAC (SpatioTemporal Asset Catalog)**: A standardized specification for discovering and cataloging geospatial datasets across public web endpoints.
- **UTM (Universal Transverse Mercator)**: A projected conformal map projection dividing the Earth into 60 longitudinal zones, providing planar linear coordinates in meters.

---

### Appendix E: Troubleshooting Guide

| Issue / Error Symptom | Probable Cause | Recommended Resolution |
| :--- | :--- | :--- |
| `ModuleNotFoundError: No module named 'download_mettur_sentinel2'` when running pytest in nested directory | Python search path does not include parent directory containing downloader script. | Set `$env:PYTHONPATH = ".."` in PowerShell before executing `..\.venv\Scripts\python.exe -m pytest`. |
| `RasterReadError: ... exceeds safety processing limit of 25,000,000 pixels` | An uncropped full Sentinel-2 tile ($10,980 \times 10,980 \approx 120\text{ Mpx}$) was passed to the loader. | Use a cropped window GeoTIFF (such as the provided `data/real_mettur/` files) or clip the raster in GIS before ingestion. |
| `IncompatibleGridError: Coordinate Reference System mismatch` | Baseline and comparison files use different coordinate projections (e.g., UTM Zone 43N vs. UTM Zone 44N). | Reproject both rasters to a common projected coordinate system (e.g., `EPSG:32643`) before processing. |
| `IncompatibleGridError: Spatial raster dimension mismatch` | Baseline and comparison files have different pixel matrix dimensions ($H \times W$). | Ensure both images are clipped to the exact same spatial bounding box. |
| `TemporalOrderError: Baseline date must strictly precede comparison date` | The baseline date was set after or identical to the comparison date. | Ensure the earlier observation is configured as Baseline and the later observation as Follow-up. |
| `NoDataError: Observation contains no valid pixels` | The supplied GeoTIFF is completely empty, contains all-zero data, or is completely obscured by cloud mask. | Verify raster content in GIS or inspect file size. |
| `PathTraversalError: Unsafe path detected` | File path contains `\0` null bytes or escapes designated directory boundaries. | Supply clean, relative or canonical paths within the project workspace. |
