"""Command-line demonstration script for Micro-Reservoir Intelligence.

Executes the end-to-end analysis across all temporal test scenarios defined in
`data/samples/sample_manifest.json` and outputs a formatted status summary.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
import numpy as np

# Ensure root package is in python path
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

from config import DEFAULT_CONFIG
from scripts.prepare_sample import prepare_all_samples
from src.microreservoir.reporting import build_dashboard_data, run_analysis
from src.microreservoir.schemas import Observation, ObservationMetadata


def load_observation_from_npz(npz_path: Path, scene_meta: dict) -> Observation:
    """Load spectral band arrays and build an Observation object."""
    data = np.load(npz_path)
    bands = {
        "green": data["green"],
        "nir": data["nir"],
        "red": data["red"],
        "blue": data["blue"],
        "swir1": data["swir1"],
    }
    valid_mask = data["valid_mask"] if "valid_mask" in data else None

    metadata = ObservationMetadata(
        scene_id=scene_meta["scene_id"],
        date=scene_meta["date"],
        cloud_cover_percent=scene_meta.get("cloud_cover_percent", 0.0),
        notes=scene_meta.get("description"),
    )

    return Observation(metadata=metadata, bands=bands, valid_mask=valid_mask)


def run_demo() -> int:
    """Run all demonstration scenarios from manifest and print formatted results."""
    manifest_path = DEFAULT_CONFIG.sample_manifest_path

    if not manifest_path.exists():
        print(f"Manifest not found at {manifest_path}. Generating samples now...")
        prepare_all_samples()

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    scenarios = manifest.get("sample_scenarios", [])
    print("=" * 80)
    print("MICRO-RESERVOIR INTELLIGENCE - MULTI-TEMPORAL ANALYSIS DEMO")
    print(f"Total Scenarios: {len(scenarios)} | Target Hardware: CPU")
    print("=" * 80)

    summary_records = []
    all_passed = True

    for i, scenario in enumerate(scenarios, 1):
        s_id = scenario["id"]
        s_name = scenario["name"]
        expected_status = scenario["expected_status"]

        base_info = scenario["baseline"]
        comp_info = scenario["comparison"]

        base_file = PACKAGE_ROOT / base_info["file_path"]
        comp_file = PACKAGE_ROOT / comp_info["file_path"]

        # Ensure sample files exist
        if not base_file.exists() or not comp_file.exists():
            print(f"Sample data missing for scenario {s_id}. Generating...")
            prepare_all_samples()

        base_obs = load_observation_from_npz(base_file, base_info)
        comp_obs = load_observation_from_npz(comp_file, comp_info)

        print(f"\n[{i}/{len(scenarios)}] SCENARIO: {s_name} ({s_id})")
        print(f"  Baseline:   {base_obs.metadata.scene_id} ({base_obs.metadata.date})")
        print(f"  Comparison: {comp_obs.metadata.scene_id} ({comp_obs.metadata.date})")

        # Run pipeline
        analysis = run_analysis(base_obs, comp_obs, cfg=DEFAULT_CONFIG)
        dashboard_data = build_dashboard_data(analysis)
        status = analysis.comparison.status

        match = status == expected_status
        if not match:
            all_passed = False

        status_marker = "[OK]" if match else "[MISMATCH]"
        print(f"  Result Status:    {status.upper()} (Expected: {expected_status.upper()}) {status_marker}")
        print(f"  Baseline Area:    {analysis.baseline_area.water_area_hectares:.3f} ha "
              f"({analysis.baseline_area.pixel_count} px)")
        print(f"  Comparison Area:  {analysis.comparison_area.water_area_hectares:.3f} ha "
              f"({analysis.comparison_area.pixel_count} px)")
        delta_pct_str = (
            f"{analysis.comparison.area_delta_percent:+.1f}%"
            if analysis.comparison.area_delta_percent is not None
            else "N/A"
        )
        print(f"  Area Delta:       {analysis.comparison.area_delta_ha:+.3f} ha "
              f"({delta_pct_str})")
        print(f"  Confidence:       {analysis.comparison.confidence_score * 100:.0f}%")

        if analysis.alerts:
            print("  Alerts Generated:")
            for a in analysis.alerts:
                print(f"    - [{a.severity.value}] {a.title}: {a.message}")

        summary_records.append({
            "scenario_id": s_id,
            "status": status,
            "expected_status": expected_status,
            "matched": match,
            "baseline_ha": analysis.baseline_area.water_area_hectares,
            "comparison_ha": analysis.comparison_area.water_area_hectares,
            "delta_percent": analysis.comparison.area_delta_percent,
        })

    # Save output to data/processed
    out_dir = DEFAULT_CONFIG.processed_dir
    out_dir.mkdir(parents=True, exist_ok=True)
    summary_path = out_dir / "demo_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary_records, f, indent=2)

    print("\n" + "=" * 80)
    print(f"DEMO COMPLETE | Saved summary report to: {summary_path}")
    print(f"All Scenarios Matched Expected Status: {'YES' if all_passed else 'NO'}")
    print("=" * 80)

    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(run_demo())
