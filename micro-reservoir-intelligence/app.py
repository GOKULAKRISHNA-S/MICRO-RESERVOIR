"""Streamlit Interactive Application for Micro-Reservoir Intelligence.

Provides visual multi-temporal satellite imagery inspection, spectral water extraction,
surface area quantification, change classification, quality-assurance inspection,
alert monitoring, and structured report exports.
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
from typing import Any, Dict, Optional
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
import streamlit as st

# Ensure repository root is on Python path
REPO_ROOT = Path(__file__).resolve().parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import (
    DEFAULT_CONFIG,
    STATUS_INSUFFICIENT_DATA,
    STATUS_INVALID_COMPARISON,
    STATUS_POTENTIAL_DECLINE,
    STATUS_POTENTIAL_INCREASE,
    STATUS_STABLE,
    AppConfig,
)
from scripts.prepare_sample import prepare_all_samples
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
from src.microreservoir.geotiff import load_geotiff_observation
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
    AnalysisResult,
    ChangePixelClass,
    Observation,
    ObservationMetadata,
    WaterIndexMethod,
)


def load_sample_manifest() -> Dict[str, Any]:
    """Load sample metadata catalog or auto-generate if missing."""
    manifest_path = DEFAULT_CONFIG.sample_manifest_path
    if not manifest_path.exists():
        prepare_all_samples()
    with open(manifest_path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_npz_scene(file_rel_path: str, meta_dict: dict) -> Observation:
    """Load a compressed synthetic sample array from disk."""
    abs_path = REPO_ROOT / file_rel_path
    if not abs_path.exists():
        prepare_all_samples()
    data = np.load(abs_path)
    bands = {
        "green": data["green"],
        "nir": data["nir"],
        "red": data["red"],
        "blue": data["blue"],
        "swir1": data["swir1"],
    }
    valid_mask = data["valid_mask"] if "valid_mask" in data else None
    metadata = ObservationMetadata(
        scene_id=meta_dict["scene_id"],
        date=meta_dict["date"],
        cloud_cover_percent=meta_dict.get("cloud_cover_percent", 0.0),
        cloud_assessed=True,
        notes=meta_dict.get("description"),
    )
    return Observation(metadata=metadata, bands=bands, valid_mask=valid_mask)


def render_status_badge(status: str) -> str:
    """Return colored HTML badge corresponding to operational change status."""
    badge_styles = {
        STATUS_STABLE: ("#16a34a", "#dcfce7", "STABLE"),
        STATUS_POTENTIAL_DECLINE: ("#dc2626", "#fee2e2", "POTENTIAL DECLINE"),
        STATUS_POTENTIAL_INCREASE: ("#0284c7", "#e0f2fe", "POTENTIAL INCREASE"),
        STATUS_INSUFFICIENT_DATA: ("#d97706", "#fef3c7", "INSUFFICIENT DATA"),
        STATUS_INVALID_COMPARISON: ("#4b5563", "#f3f4f6", "INVALID COMPARISON"),
    }
    color, bg, label = badge_styles.get(status, ("#4b5563", "#f3f4f6", status.upper()))
    return f"""
    <span style="
        background-color: {bg};
        color: {color};
        padding: 6px 18px;
        border-radius: 9999px;
        font-weight: 700;
        font-size: 0.95rem;
        letter-spacing: 0.05em;
        border: 1px solid {color}50;
        display: inline-block;
    ">
        {label}
    </span>
    """


def render_comparison_bar_chart(analysis: AnalysisResult) -> go.Figure:
    """Generate an interactive Plotly comparison bar chart of measured surface water area."""
    comp = analysis.comparison
    base_ha = analysis.baseline_area.water_area_hectares
    comp_ha = analysis.comparison_area.water_area_hectares
    base_m2 = analysis.baseline_area.water_area_m2
    comp_m2 = analysis.comparison_area.water_area_m2

    base_date = analysis.baseline_observation.date
    comp_date = analysis.comparison_observation.date

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=[f"Baseline ({base_date})", f"Follow-up ({comp_date})"],
            y=[base_ha, comp_ha],
            customdata=[f"{base_m2:,.0f} m²", f"{comp_m2:,.0f} m²"],
            hovertemplate="<b>%{x}</b><br>Water Area: %{y:.3f} ha (%{customdata})<extra></extra>",
            marker=dict(
                color=["#2563eb", "#0ea5e9" if comp_ha >= base_ha else "#ef4444"],
                line=dict(color="#1e293b", width=1.5),
            ),
            text=[f"{base_ha:.3f} ha", f"{comp_ha:.3f} ha"],
            textposition="auto",
        )
    )

    delta_str = (
        f"{comp.area_delta_percent:+.1f}%"
        if comp.area_delta_percent is not None
        else "N/A"
    )

    fig.update_layout(
        title=f"Surface Water Area Comparison (Net Shift: {comp.area_delta_ha:+.3f} ha / {delta_str})",
        yaxis_title="Water Area (Hectares)",
        xaxis_title="Observation Acquisition Date",
        template="plotly_white",
        height=380,
        margin=dict(l=40, r=40, t=60, b=40),
    )
    return fig


def main():
    st.set_page_config(
        page_title="Micro-Reservoir Intelligence",
        page_icon="💧",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Header
    st.markdown(
        """
        <div style="padding: 1.0rem 0 1.2rem 0; border-bottom: 2px solid #e2e8f0; margin-bottom: 1.5rem;">
            <h1 style="margin: 0; font-size: 2.2rem; font-weight: 800; color: #0f172a; display: flex; align-items: center; gap: 0.6rem;">
                <span>💧 Micro-Reservoir Intelligence</span>
            </h1>
            <p style="margin: 0.3rem 0 0 0; color: #64748b; font-size: 1.05rem;">
                Operational Multispectral Surface-Water Extraction, Area Quantification & Multi-Temporal Change Monitoring
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Explanation Expander
    with st.expander("ℹ️ Scientific Methodology, Spectral Algorithms & Operational Disclaimers"):
        st.markdown(
            """
            ### Analysis Workflow & Core Formulations
            1. **Spectral Water Extraction**:
               * **NDWI (McFeeters, 1996)**: $\\text{NDWI} = \\frac{\\text{Green} - \\text{NIR}}{\\text{Green} + \\text{NIR}}$ (using Sentinel-2 Band 3 and Band 8).
               * **MNDWI (Xu, 2006)**: $\\text{MNDWI} = \\frac{\\text{Green} - \\text{SWIR1}}{\\text{Green} + \\text{SWIR1}}$ (suppresses built-up urban features).
               * Safe zero-division handling and NoData quarantine are applied vectorially.
            2. **Geospatial Area Estimation**:
               * Pixel ground area is derived using trustworthy CRS projection and affine transform determinants: $|a \\cdot e - b \\cdot d|$.
               * Area is reported in both square metres ($m^2$) and hectares ($1\\text{ ha} = 10,000\\text{ m}^2$), alongside boundary mixed-pixel uncertainty bounds.
               * Unprojected geographic coordinate systems (degrees) are rejected or reported as unavailable to prevent distorted measurements.
            3. **Multi-Temporal Change Classification**:
               * Absolute Change: $\\Delta\\text{Area} = \\text{Comparison Area} - \\text{Baseline Area}$.
               * Percentage Change: $\\left(\\frac{\\text{Comparison Area} - \\text{Baseline Area}}{\\text{Baseline Area}}\\right) \\times 100\\%$ (reported as *Unavailable* if baseline area is zero).
            4. **Quality-Aware Operational Alerts**:
               * Statuses: `stable`, `potential_decline`, `potential_increase`, `insufficient_data`, `invalid_comparison`.
               * High-severity decline alerts are strictly suppressed if quality checks fail or data coverage is $< 70\\%$.
            5. **Hydrological Disclaimer**:
               * Surface-water extent reflects open surface water only and must **NOT** be used to infer groundwater depletion, aquifer trends, or confirmed regional drought without independent hydrological and meteorological data.
            """
        )

    # Sidebar: Setup and Controls
    with st.sidebar:
        st.header("⚙️ Analysis Configuration")

        input_mode = st.radio(
            "Input Data Source",
            options=["📁 Local GeoTIFF Files", "🧪 Synthetic Test Scenarios (Demo Mode)"],
            index=1,
            help="Select local GeoTIFF satellite files or pre-generated synthetic test scenarios.",
        )

        st.divider()

        # Reservoir Identifier
        reservoir_id = st.text_input(
            "Reservoir Identifier",
            value="RES-001",
            help="User-defined water body code or village tank name.",
        ).strip()
        if not reservoir_id:
            reservoir_id = "RESERVOIR_UNKNOWN"

        st.subheader("Spectral & Detection Thresholds")
        chosen_index = st.selectbox(
            "Water Index Algorithm",
            options=["NDWI", "MNDWI", "AWEI"],
            index=0,
            help="NDWI is standard for Green & NIR (Sentinel-2 B03 and B08).",
        )

        water_threshold = st.slider(
            "Index Decision Threshold",
            min_value=-0.5,
            max_value=0.5,
            value=0.0,
            step=0.05,
            help="Reflectance index cutoff above which valid pixels are classified as water.",
        )

        st.subheader("Change Alert Thresholds")
        decline_cutoff = st.slider(
            "Decline Flag Threshold (%)",
            min_value=-50,
            max_value=-5,
            value=-10,
            step=5,
            help="Percentage area loss triggering POTENTIAL_DECLINE status.",
        )

        critical_decline_cutoff = st.slider(
            "Critical Decline Threshold (%)",
            min_value=-60,
            max_value=-15,
            value=-25,
            step=5,
            help="Severe area loss percentage triggering CRITICAL operational alert.",
        )

        increase_cutoff = st.slider(
            "Increase Flag Threshold (%)",
            min_value=5,
            max_value=50,
            value=10,
            step=5,
            help="Percentage area expansion triggering POTENTIAL_INCREASE status.",
        )

        st.subheader("Quality Constraints")
        min_valid_coverage = st.slider(
            "Minimum Valid Coverage (%)",
            min_value=50,
            max_value=90,
            value=70,
            step=5,
            help="Minimum valid-pixel ratio required for trustworthy analysis.",
        )

        max_cloud_cover = st.slider(
            "Maximum Cloud Cover (%)",
            min_value=5,
            max_value=50,
            value=20,
            step=5,
            help="Maximum acceptable cloud obscuration percentage.",
        )

        # Dynamic AppConfig instance
        custom_config = AppConfig(
            default_water_index=chosen_index,
            ndwi_threshold=water_threshold,
            mndwi_threshold=water_threshold,
            awei_threshold=water_threshold,
            decline_threshold_percent=float(decline_cutoff),
            critical_decline_threshold_percent=float(critical_decline_cutoff),
            increase_threshold_percent=float(increase_cutoff),
            min_valid_pixel_ratio=min_valid_coverage / 100.0,
            max_cloud_cover_percent=float(max_cloud_cover),
        )

    # Input forms based on source mode
    if input_mode == "📁 Local GeoTIFF Files":
        st.subheader("📁 Local GeoTIFF Observations Input")
        st.caption(
            "Specify file paths for baseline (earlier) and follow-up (later) GeoTIFF rasters on your local filesystem."
        )

        col_base, col_comp = st.columns(2)

        with col_base:
            st.markdown("#### 1️⃣ Baseline Observation")
            base_scene_id = st.text_input("Baseline Scene ID", value="S2A_BASELINE", key="b_scene")
            base_date = st.text_input("Baseline Acquisition Date (YYYY-MM-DD)", value="2023-10-15", key="b_date")
            base_layout = st.radio(
                "Baseline Raster Layout",
                options=["Separate Single-Band Files", "Multiband GeoTIFF with Band Mapping"],
                key="b_layout",
            )

            if base_layout == "Separate Single-Band Files":
                base_green_file = st.text_input("Green Band (B03) GeoTIFF Path", value="data/samples/S2A_20231015_B03.tif", key="b_g_path")
                base_nir_file = st.text_input("NIR Band (B08) GeoTIFF Path", value="data/samples/S2A_20231015_B08.tif", key="b_n_path")
                base_cloud_file = st.text_input("Optional Cloud Mask GeoTIFF Path", value="", key="b_c_path")
                base_multi_file = ""
                base_g_idx, base_n_idx = 1, 2
            else:
                base_multi_file = st.text_input("Multiband GeoTIFF Path", value="data/samples/S2A_20231015_multiband.tif", key="b_m_path")
                base_g_idx = st.number_input("Green Band 1-Indexed Number", min_value=1, max_value=16, value=1, key="b_m_g")
                base_n_idx = st.number_input("NIR Band 1-Indexed Number", min_value=1, max_value=16, value=2, key="b_m_n")
                base_cloud_file = st.text_input("Optional Cloud Mask GeoTIFF Path", value="", key="b_cm_path")
                base_green_file, base_nir_file = "", ""

        with col_comp:
            st.markdown("#### 2️⃣ Follow-up (Comparison) Observation")
            comp_scene_id = st.text_input("Comparison Scene ID", value="S2B_FOLLOWUP", key="c_scene")
            comp_date = st.text_input("Comparison Acquisition Date (YYYY-MM-DD)", value="2024-03-15", key="c_date")
            comp_layout = st.radio(
                "Comparison Raster Layout",
                options=["Separate Single-Band Files", "Multiband GeoTIFF with Band Mapping"],
                key="c_layout",
            )

            if comp_layout == "Separate Single-Band Files":
                comp_green_file = st.text_input("Green Band (B03) GeoTIFF Path", value="data/samples/S2B_20240315_B03.tif", key="c_g_path")
                comp_nir_file = st.text_input("NIR Band (B08) GeoTIFF Path", value="data/samples/S2B_20240315_B08.tif", key="c_n_path")
                comp_cloud_file = st.text_input("Optional Cloud Mask GeoTIFF Path", value="", key="c_c_path")
                comp_multi_file = ""
                comp_g_idx, comp_n_idx = 1, 2
            else:
                comp_multi_file = st.text_input("Multiband GeoTIFF Path", value="data/samples/S2B_20240315_multiband.tif", key="c_m_path")
                comp_g_idx = st.number_input("Green Band 1-Indexed Number", min_value=1, max_value=16, value=1, key="c_m_g")
                comp_n_idx = st.number_input("NIR Band 1-Indexed Number", min_value=1, max_value=16, value=2, key="c_m_n")
                comp_cloud_file = st.text_input("Optional Cloud Mask GeoTIFF Path", value="", key="c_cm_path")
                comp_green_file, comp_nir_file = "", ""

    else:
        # Synthetic Demonstration Mode
        st.subheader("🧪 Synthetic Demonstration Scenarios")
        st.warning(
            "⚠️ **Synthetic Demonstration Mode Active**: Data loaded from simulated benchmark arrays. "
            "These values are synthetic test patterns strictly designed to verify the numerical and logical pipeline, "
            "**NOT real satellite observations**."
        )

        manifest = load_sample_manifest()
        scenarios = manifest.get("sample_scenarios", [])
        scenario_names = [f"{s['name']} (Expected: {s['expected_status']})" for s in scenarios]

        selected_idx = st.selectbox(
            "Select Benchmark Test Scenario",
            options=range(len(scenarios)),
            format_func=lambda i: scenario_names[i],
            index=0,
        )
        selected_scenario = scenarios[selected_idx]
        st.info(f"**Scenario Context**: {selected_scenario['description']}")

    # Analyse Button
    st.markdown("---")
    btn_col1, btn_col2 = st.columns([1, 3])
    with btn_col1:
        analyse_clicked = st.button("🔍 Run Multi-Temporal Analysis", type="primary", use_container_width=True)

    # Process Analysis Trigger
    if analyse_clicked:
        with st.spinner("Processing satellite observations and running geospatial analysis engine..."):
            try:
                if input_mode == "📁 Local GeoTIFF Files":
                    # Load Baseline
                    if base_layout == "Separate Single-Band Files":
                        base_obs = load_geotiff_observation(
                            scene_id=base_scene_id,
                            date_str=base_date,
                            band_files={"green": base_green_file, "nir": base_nir_file},
                            cloud_mask_file=base_cloud_file if base_cloud_file.strip() else None,
                        )
                    else:
                        base_obs = load_geotiff_observation(
                            scene_id=base_scene_id,
                            date_str=base_date,
                            multiband_file=base_multi_file,
                            band_mapping={"green": int(base_g_idx), "nir": int(base_n_idx)},
                            cloud_mask_file=base_cloud_file if base_cloud_file.strip() else None,
                        )

                    # Load Comparison
                    if comp_layout == "Separate Single-Band Files":
                        comp_obs = load_geotiff_observation(
                            scene_id=comp_scene_id,
                            date_str=comp_date,
                            band_files={"green": comp_green_file, "nir": comp_nir_file},
                            cloud_mask_file=comp_cloud_file if comp_cloud_file.strip() else None,
                        )
                    else:
                        comp_obs = load_geotiff_observation(
                            scene_id=comp_scene_id,
                            date_str=comp_date,
                            multiband_file=comp_multi_file,
                            band_mapping={"green": int(comp_g_idx), "nir": int(comp_n_idx)},
                            cloud_mask_file=comp_cloud_file if comp_cloud_file.strip() else None,
                        )

                    is_synthetic = False

                else:
                    # Synthetic Mode
                    base_info = selected_scenario["baseline"]
                    comp_info = selected_scenario["comparison"]
                    base_obs = load_npz_scene(base_info["file_path"], base_info)
                    comp_obs = load_npz_scene(comp_info["file_path"], comp_info)
                    is_synthetic = True

                # Run Full Analysis Engine
                analysis_result = run_analysis(base_obs, comp_obs, cfg=custom_config)
                dashboard_data = build_dashboard_data(analysis_result)

                # Persist in session state
                st.session_state["analysis_result"] = analysis_result
                st.session_state["dashboard_data"] = dashboard_data
                st.session_state["is_synthetic"] = is_synthetic
                st.session_state["reservoir_id"] = reservoir_id
                st.session_state["has_run"] = True

                st.success("Analysis executed successfully! See detailed inspection tabs below.")

            except FileNotFoundError as exc:
                st.error(f"❌ **File Not Found**: {exc}. Please verify file paths exist on the local disk.")
            except CorruptRasterError as exc:
                st.error(f"❌ **Corrupt Raster File**: {exc}. The GeoTIFF file may be empty (0 bytes) or truncated.")
            except MissingCRSError as exc:
                st.error(f"❌ **Missing Coordinate Reference System**: {exc}. An explicit projected CRS is required.")
            except IncompatibleGridError as exc:
                st.error(f"❌ **Incompatible Grid**: {exc}. Baseline and comparison observations must share matching spatial dimensions, CRS, and grid alignment.")
            except InvalidDateError as exc:
                st.error(f"❌ **Invalid Date Format**: {exc}. Dates must follow ISO-8601 calendar format 'YYYY-MM-DD'.")
            except TemporalOrderError as exc:
                st.error(f"❌ **Temporal Precedence Inversion**: {exc}. Baseline date must strictly precede the comparison date.")
            except NoDataError as exc:
                st.error(f"❌ **NoData Error**: {exc}. Raster observation contains zero valid pixels.")
            except MissingBandError as exc:
                st.error(f"❌ **Missing Spectral Band**: {exc}.")
            except PathTraversalError as exc:
                st.error(f"❌ **Path Security Violation**: {exc}.")
            except Exception as exc:
                st.error(f"❌ **Analysis Pipeline Error**: {exc}")

    # Display Analysis Dashboard if available
    if st.session_state.get("has_run") and "analysis_result" in st.session_state:
        analysis: AnalysisResult = st.session_state["analysis_result"]
        dashboard_data: Dict[str, Any] = st.session_state["dashboard_data"]
        is_synthetic: bool = st.session_state.get("is_synthetic", False)
        current_res_id: str = st.session_state.get("reservoir_id", "RES-001")

        comp_res = analysis.comparison
        base_area = analysis.baseline_area
        comp_area = analysis.comparison_area

        st.markdown("---")

        # Synthetic banner if applicable
        if is_synthetic:
            st.warning("⚠️ **Notice**: The displayed findings are derived from synthetic benchmark data. Strictly intended for test verification.")

        # Status & Header Overview
        hdr_c1, hdr_c2 = st.columns([3, 1])
        with hdr_c1:
            st.markdown(f"### Reservoir: **{current_res_id}**")
            st.caption(
                f"Baseline: `{analysis.baseline_observation.scene_id}` ({analysis.baseline_observation.date}) ➔ "
                f"Follow-up: `{analysis.comparison_observation.scene_id}` ({analysis.comparison_observation.date})"
            )
        with hdr_c2:
            st.markdown(
                f"<div style='text-align: right; padding-top: 0.5rem;'>{render_status_badge(comp_res.status)}</div>",
                unsafe_allow_html=True,
            )

        # Primary KPI Metric Cards
        m_cols = st.columns(4)
        with m_cols[0]:
            st.metric(
                label=f"Baseline Area ({analysis.baseline_observation.date})",
                value=f"{base_area.water_area_hectares:.3f} ha",
                delta=f"{base_area.water_area_m2:,.0f} m² ({base_area.pixel_count:,} px)",
                delta_color="off",
            )
        with m_cols[1]:
            st.metric(
                label=f"Follow-up Area ({analysis.comparison_observation.date})",
                value=f"{comp_area.water_area_hectares:.3f} ha",
                delta=f"{comp_area.water_area_m2:,.0f} m² ({comp_area.pixel_count:,} px)",
                delta_color="off",
            )
        with m_cols[2]:
            if comp_res.area_delta_percent is not None:
                d_color = "normal" if comp_res.area_delta_percent >= 0 else "inverse"
                delta_display = f"{comp_res.area_delta_percent:+.1f}%"
            else:
                d_color = "off"
                delta_display = "N/A (Zero Base)"

            st.metric(
                label="Net Surface Area Shift",
                value=f"{comp_res.area_delta_ha:+.3f} ha",
                delta=delta_display,
                delta_color=d_color,
            )
        with m_cols[3]:
            conf_pct = f"{comp_res.confidence_score * 100:.0f}%"
            st.metric(
                label="Confidence Index",
                value=conf_pct,
                delta="Quality Verified" if comp_res.quality_passed else "Quality Unverified",
                delta_color="normal" if comp_res.quality_passed else "inverse",
            )

        # Quality Inspection Banner / Alert if checks failed
        if not comp_res.quality_passed or comp_res.status in (STATUS_INVALID_COMPARISON, STATUS_INSUFFICIENT_DATA):
            st.error(f"⚠️ **Data Quality Notice**: {comp_res.details}")

        # Inspection Tabs
        tab_spectral, tab_masks, tab_change, tab_chart, tab_quality, tab_alerts, tab_export = st.tabs([
            "🛰️ Spectral Imagery & NDWI",
            "💧 Classified Water Masks",
            "🔄 Transition Change Map",
            "📊 Comparison Chart",
            "🛡️ Quality Pre-Flight Checks",
            "⚠️ Operational Alerts",
            "📥 Export Reports",
        ])

        # TAB 1: Spectral Imagery & NDWI
        with tab_spectral:
            st.markdown("#### Continuous Normalized Difference Water Index (NDWI)")
            st.caption("NDWI values range from -1.0 to +1.0. Positive values indicate open water surface reflectance.")

            s_cols = st.columns(2)
            with s_cols[0]:
                st.markdown(f"**Baseline NDWI** ({analysis.baseline_observation.date})")
                b_ndwi = analysis.baseline_detection.index_map
                fig_b = px.imshow(
                    b_ndwi,
                    color_continuous_scale="Blues",
                    zmin=-0.5,
                    zmax=0.5,
                    title="Baseline NDWI Index Map",
                )
                fig_b.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_b, use_container_width=True)

            with s_cols[1]:
                st.markdown(f"**Follow-up NDWI** ({analysis.comparison_observation.date})")
                c_ndwi = analysis.comparison_detection.index_map
                fig_c = px.imshow(
                    c_ndwi,
                    color_continuous_scale="Blues",
                    zmin=-0.5,
                    zmax=0.5,
                    title="Follow-up NDWI Index Map",
                )
                fig_c.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_c, use_container_width=True)

        # TAB 2: Classified Water Masks
        with tab_masks:
            st.markdown("#### Classified Binary Surface Water Extents")
            st.caption("Pixels classified as water (Index > Threshold AND valid pixel) are highlighted in cyan/blue.")

            wm_cols = st.columns(2)
            with wm_cols[0]:
                st.markdown(f"**Baseline Detected Water**: `{base_area.water_area_hectares:.3f} ha` ({base_area.pixel_count:,} px)")
                st.caption(f"Uncertainty: [{base_area.uncertainty_range_hectares[0]:.3f}, {base_area.uncertainty_range_hectares[1]:.3f}] ha")
                b_mask_img = np.where(analysis.baseline_detection.water_mask, 1.0, 0.0)
                fig_bm = px.imshow(
                    b_mask_img,
                    color_continuous_scale=[[0, "#f1f5f9"], [1, "#0284c7"]],
                    title="Baseline Water Mask",
                )
                fig_bm.update_coloraxes(showscale=False)
                fig_bm.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_bm, use_container_width=True)

            with wm_cols[1]:
                st.markdown(f"**Follow-up Detected Water**: `{comp_area.water_area_hectares:.3f} ha` ({comp_area.pixel_count:,} px)")
                st.caption(f"Uncertainty: [{comp_area.uncertainty_range_hectares[0]:.3f}, {comp_area.uncertainty_range_hectares[1]:.3f}] ha")
                c_mask_img = np.where(analysis.comparison_detection.water_mask, 1.0, 0.0)
                fig_cm = px.imshow(
                    c_mask_img,
                    color_continuous_scale=[[0, "#f1f5f9"], [1, "#0284c7"]],
                    title="Follow-up Water Mask",
                )
                fig_cm.update_coloraxes(showscale=False)
                fig_cm.update_layout(height=350, margin=dict(l=10, r=10, t=30, b=10))
                st.plotly_chart(fig_cm, use_container_width=True)

        # TAB 3: Transition Change Map
        with tab_change:
            st.markdown("#### Bi-Temporal Surface Water Transition Map")
            st.caption("Categorical breakdown of water stability, retreat, and expansion between observations.")

            tc_cols = st.columns([3, 2])
            with tc_cols[0]:
                if comp_res.change_mask is not None:
                    mask = comp_res.change_mask
                    h, w = mask.shape
                    rgb_map = np.full((h, w, 3), 0.95, dtype=np.float32)

                    rgb_map[mask == ChangePixelClass.PERSISTENT_WATER.value] = [0.08, 0.45, 0.82]  # Navy Blue
                    rgb_map[mask == ChangePixelClass.WATER_LOST.value] = [0.90, 0.22, 0.21]        # Red (Loss)
                    rgb_map[mask == ChangePixelClass.WATER_GAINED.value] = [0.12, 0.72, 0.53]      # Green (Gain)
                    rgb_map[mask == ChangePixelClass.INVALID.value] = [0.45, 0.45, 0.45]          # Dark Gray (Invalid)

                    st.image(
                        rgb_map,
                        caption="Blue = Persistent Water, Red = Water Lost (Decline), Green = Water Gained (Expansion)",
                        use_container_width=True,
                    )
                else:
                    st.warning("Change mask is unavailable because observations could not be compared.")

            with tc_cols[1]:
                st.markdown("##### Transition Breakdown")
                if comp_res.change_mask is not None:
                    mask = comp_res.change_mask
                    px_m2 = (analysis.baseline_observation.pixel_resolution_m) ** 2
                    px_ha = px_m2 * 0.0001

                    n_persist = int(np.sum(mask == ChangePixelClass.PERSISTENT_WATER.value))
                    n_lost = int(np.sum(mask == ChangePixelClass.WATER_LOST.value))
                    n_gained = int(np.sum(mask == ChangePixelClass.WATER_GAINED.value))
                    n_invalid = int(np.sum(mask == ChangePixelClass.INVALID.value))

                    st.markdown(f"- 🟦 **Persistent Water**: `{n_persist * px_ha:.3f} ha` ({n_persist:,} px)")
                    st.markdown(f"- 🟥 **Water Retracted (Lost)**: `{n_lost * px_ha:.3f} ha` ({n_lost:,} px)")
                    st.markdown(f"- 🟩 **Water Expanded (Gained)**: `{n_gained * px_ha:.3f} ha` ({n_gained:,} px)")
                    if n_invalid > 0:
                        st.markdown(f"- ⬛ **Invalid / Cloud Obscured**: `{n_invalid * px_ha:.3f} ha` ({n_invalid:,} px)")

                st.info(f"**Comparison Assessment**:\n\n{comp_res.details}")

        # TAB 4: Comparison Chart
        with tab_chart:
            st.markdown("#### Surface Water Area Comparison Chart")
            bar_fig = render_comparison_bar_chart(analysis)
            st.plotly_chart(bar_fig, use_container_width=True)

            # Numerical Summary Table
            st.markdown("##### Measured Surface Area Summary Table")
            summary_table = {
                "Observation": ["Baseline Reference", "Follow-up Comparison", "Net Absolute Shift", "Relative Change"],
                "Date": [analysis.baseline_observation.date, analysis.comparison_observation.date, "-", "-"],
                "Water Area (ha)": [
                    f"{base_area.water_area_hectares:.4f} ha",
                    f"{comp_area.water_area_hectares:.4f} ha",
                    f"{comp_res.area_delta_ha:+.4f} ha",
                    f"{comp_res.area_delta_percent:+.2f}%" if comp_res.area_delta_percent is not None else "N/A",
                ],
                "Water Area (m²)": [
                    f"{base_area.water_area_m2:,.1f} m²",
                    f"{comp_area.water_area_m2:,.1f} m²",
                    f"{comp_res.area_delta_m2:+,.1f} m²" if comp_res.area_delta_m2 is not None else "N/A",
                    "-",
                ],
                "Water Pixels": [
                    f"{base_area.pixel_count:,}",
                    f"{comp_area.pixel_count:,}",
                    f"{comp_area.pixel_count - base_area.pixel_count:+,}",
                    "-",
                ],
            }
            st.table(summary_table)

        # TAB 5: Quality Pre-Flight Checks
        with tab_quality:
            st.markdown("#### Quality Assurance & Study Area Integrity Checks")
            st.caption("Verifies spatial alignment, coordinate systems, and data completeness before change detection.")

            base_m = analysis.baseline_observation
            comp_m = analysis.comparison_observation

            q_cols = st.columns(2)
            with q_cols[0]:
                st.markdown("##### 1. Coordinate Reference System (CRS)")
                b_crs = base_m.crs or "Missing"
                c_crs = comp_m.crs or "Missing"
                crs_match = b_crs.strip().upper() == c_crs.strip().upper() and b_crs != "Missing"

                if crs_match:
                    st.success(f"✅ Matching Projected CRS: `{b_crs}`")
                else:
                    st.error(f"❌ CRS Mismatch or Unprojected: Baseline `{b_crs}` vs Comparison `{c_crs}`")

                st.markdown("##### 2. Spatial Grid Dimensions & Resolution")
                b_shape = analysis.baseline_detection.water_mask.shape
                c_shape = analysis.comparison_detection.water_mask.shape
                dim_match = b_shape == c_shape

                if dim_match:
                    st.success(f"✅ Grid Dimensions Match: `{b_shape[0]} × {b_shape[1]}` px")
                else:
                    st.error(f"❌ Dimension Mismatch: Baseline `{b_shape}` vs Comparison `{c_shape}`")

                res_match = abs(base_m.pixel_resolution_m - comp_m.pixel_resolution_m) <= 1e-3
                if res_match:
                    st.success(f"✅ Ground Resolution Match: `{base_m.pixel_resolution_m:.2f} m/px`")
                else:
                    st.error(f"❌ Resolution Mismatch: `{base_m.pixel_resolution_m:.2f}` vs `{comp_m.pixel_resolution_m:.2f}` m/px")

            with q_cols[1]:
                st.markdown("##### 3. Valid Data Coverage Ratio")
                b_tot = b_shape[0] * b_shape[1] if b_shape[0] * b_shape[1] > 0 else 1
                c_tot = c_shape[0] * c_shape[1] if c_shape[0] * c_shape[1] > 0 else 1
                b_ratio = analysis.baseline_detection.total_valid_pixels / b_tot
                c_ratio = analysis.comparison_detection.total_valid_pixels / c_tot

                min_ratio = custom_config.min_valid_pixel_ratio
                b_cov_ok = b_ratio >= min_ratio
                c_cov_ok = c_ratio >= min_ratio

                if b_cov_ok and c_cov_ok:
                    st.success(f"✅ Adequate Valid Coverage: Base `{b_ratio:.1%}`, Comp `{c_ratio:.1%}` (Min: `{min_ratio:.0%}`)")
                else:
                    st.warning(f"⚠️ Low Coverage: Base `{b_ratio:.1%}`, Comp `{c_ratio:.1%}` (Required: `{min_ratio:.0%}`)")

                st.markdown("##### 4. Cloud Obscuration Screening")
                b_cloud = base_m.cloud_cover_percent
                c_cloud = comp_m.cloud_cover_percent
                b_assessed = base_m.cloud_assessed
                c_assessed = comp_m.cloud_assessed

                if b_assessed and c_assessed:
                    max_c = custom_config.max_cloud_cover_percent
                    cloud_ok = (b_cloud or 0.0) <= max_c and (c_cloud or 0.0) <= max_c
                    if cloud_ok:
                        st.success(f"✅ Cloud Screening Passed: Base `{b_cloud:.1f}%`, Comp `{c_cloud:.1f}%` (Max: `{max_c:.0f}%`)")
                    else:
                        st.warning(f"⚠️ Excessive Cloud Cover: Base `{b_cloud:.1f}%`, Comp `{c_cloud:.1f}%`")
                else:
                    st.info("ℹ️ Cloud Assessment Unverified: No external cloud mask was supplied. Automatic internal cloud detection is not performed; clear-sky conditions must be visually or externally verified.")

                st.markdown("##### 5. Temporal Precedence")
                if base_m.date < comp_m.date:
                    st.success(f"✅ Temporal Order Verified: `{base_m.date}` precedes `{comp_m.date}`")
                else:
                    st.error(f"❌ Temporal Inversion: Baseline `{base_m.date}` is not before `{comp_m.date}`")

        # TAB 6: Operational Alerts
        with tab_alerts:
            st.markdown("#### Operational Advisory Alerts")
            if not analysis.alerts:
                st.success("No active advisory alerts. Reservoir storage is stable within nominal bounds.")
            else:
                for alert in analysis.alerts:
                    if alert.severity.value == "CRITICAL":
                        with st.error(f"**🚨 [{alert.severity.value}] {alert.title}**"):
                            st.write(alert.message)
                            st.caption(f"💡 **Recommended Action**: {alert.action_recommended}")
                    elif alert.severity.value == "WARNING":
                        with st.warning(f"**⚠️ [{alert.severity.value}] {alert.title}**"):
                            st.write(alert.message)
                            st.caption(f"💡 **Recommended Action**: {alert.action_recommended}")
                    else:
                        with st.info(f"**ℹ️ [{alert.severity.value}] {alert.title}**"):
                            st.write(alert.message)
                            st.caption(f"💡 **Recommended Action**: {alert.action_recommended}")

            st.markdown("---")
            st.caption(
                "📌 **Hydrological Policy**: Satellite surface water contraction reflects open surface area shrinkage "
                "and does **not** confirm aquifer depletion, groundwater loss, or drought without ground-truth precipitation records."
            )

        # TAB 7: Export Reports
        with tab_export:
            st.markdown("#### 📥 Export Operational Assessment Reports")
            st.caption("Download full analysis findings, geospatial metadata, assumptions, and quality warnings.")

            csv_data = export_report_csv(analysis, reservoir_id=current_res_id)
            json_data = export_report_json(analysis, reservoir_id=current_res_id)

            d_col1, d_col2 = st.columns(2)
            with d_col1:
                st.download_button(
                    label="📄 Download Assessment Report (CSV)",
                    data=csv_data,
                    file_name=f"micro_reservoir_{current_res_id}_report.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
            with d_col2:
                st.download_button(
                    label="📋 Download Detailed Report (JSON)",
                    data=json_data,
                    file_name=f"micro_reservoir_{current_res_id}_report.json",
                    mime="application/json",
                    use_container_width=True,
                )

            with st.expander("👁️ Preview Serialized Report Data (JSON)"):
                st.code(json_data, language="json")

    elif not st.session_state.get("has_run"):
        # Empty State
        st.markdown(
            """
            <div style="
                border: 2px dashed #cbd5e1;
                border-radius: 12px;
                padding: 3rem 2rem;
                text-align: center;
                background-color: #f8fafc;
                margin-top: 1rem;
            ">
                <span style="font-size: 3rem;">🛰️</span>
                <h3 style="color: #334155; margin: 1rem 0 0.5rem 0;">Awaiting Observation Analysis</h3>
                <p style="color: #64748b; max-width: 600px; margin: 0 auto 1.5rem auto;">
                    Select an input data source on the left (local GeoTIFF files or synthetic benchmark scenarios),
                    adjust spectral and alert thresholds, and click <strong>Run Multi-Temporal Analysis</strong>.
                </p>
                <div style="display: inline-block; text-align: left; background: white; padding: 1rem 1.5rem; border-radius: 8px; border: 1px solid #e2e8f0;">
                    <span style="font-weight: 600; color: #1e293b;">Supported Workflows:</span>
                    <ul style="margin: 0.5rem 0 0 0; padding-left: 1.2rem; color: #475569; font-size: 0.9rem;">
                        <li>Separate Single-Band GeoTIFFs (Sentinel-2 B03 Green & B08 NIR)</li>
                        <li>Multiband GeoTIFFs with explicit 1-indexed band mappings</li>
                        <li>Optional external cloud and shadow masks</li>
                        <li>Automated synthetic benchmark scenarios for offline exploration</li>
                    </ul>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


if __name__ == "__main__":
    main()
