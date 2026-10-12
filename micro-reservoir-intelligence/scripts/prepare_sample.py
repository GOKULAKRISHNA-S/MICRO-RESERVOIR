"""Sample data generator script for Micro-Reservoir Intelligence.

Generates physically plausible multispectral synthetic satellite observation scenes
(Green, NIR, Red, Blue, SWIR1) representing water bodies, soil, and vegetation
for offline testing and demonstrations on CPU.
"""

from __future__ import annotations

import json
from pathlib import Path
import numpy as np

# Ensure root paths are resolvable
REPO_ROOT = Path(__file__).resolve().parent.parent
SAMPLES_DIR = REPO_ROOT / "data" / "samples"
MANIFEST_PATH = SAMPLES_DIR / "sample_manifest.json"


def generate_scene(
    height: int = 100,
    width: int = 100,
    water_center: tuple[int, int] = (50, 50),
    water_radii: tuple[int, int] = (25, 20),
    cloud_fraction: float = 0.0,
    seed: int = 42,
) -> dict[str, np.ndarray]:
    """Synthesize a multispectral satellite scene with realistic water and land reflectance.

    Spectral signatures:
      - Water: High Green (~0.22), Low NIR (~0.04), Low SWIR (~0.02) -> NDWI > 0.6
      - Surrounding Vegetation/Soil: Low Green (~0.12), High NIR (~0.45), Moderate SWIR (~0.25) -> NDWI < -0.5
    """
    rng = np.random.default_rng(seed)

    # 1. Base land surface background (vegetated soil with subtle texture)
    noise = rng.normal(0.0, 0.015, (height, width)).astype(np.float32)
    green = np.clip(0.12 + noise, 0.05, 0.25)
    nir = np.clip(0.42 + rng.normal(0.0, 0.02, (height, width)), 0.25, 0.65)
    red = np.clip(0.10 + rng.normal(0.0, 0.01, (height, width)), 0.05, 0.20)
    blue = np.clip(0.08 + rng.normal(0.0, 0.01, (height, width)), 0.03, 0.15)
    swir1 = np.clip(0.28 + rng.normal(0.0, 0.02, (height, width)), 0.15, 0.45)

    valid_mask = np.ones((height, width), dtype=bool)

    # 2. Reservoir Geometry (Elliptical water body)
    cy, cx = water_center
    ry, rx = water_radii
    y_coords, x_coords = np.ogrid[:height, :width]
    dist_sq = ((y_coords - cy) / max(1, ry)) ** 2 + ((x_coords - cx) / max(1, rx)) ** 2
    water_mask = dist_sq <= 1.0

    # Apply water spectral signature
    green[water_mask] = np.clip(0.22 + rng.normal(0.0, 0.01, int(np.sum(water_mask))), 0.16, 0.28)
    nir[water_mask] = np.clip(0.035 + rng.normal(0.0, 0.005, int(np.sum(water_mask))), 0.01, 0.07)
    red[water_mask] = np.clip(0.06 + rng.normal(0.0, 0.008, int(np.sum(water_mask))), 0.03, 0.10)
    blue[water_mask] = np.clip(0.14 + rng.normal(0.0, 0.01, int(np.sum(water_mask))), 0.08, 0.20)
    swir1[water_mask] = np.clip(0.02 + rng.normal(0.0, 0.004, int(np.sum(water_mask))), 0.005, 0.05)

    # 3. Cloud Contamination (if requested)
    if cloud_fraction > 0.0:
        cloud_y = int(height * 0.4)
        cloud_r = int(min(height, width) * (cloud_fraction ** 0.5) * 0.6)
        cloud_dist = ((y_coords - cloud_y) / max(1, cloud_r)) ** 2 + ((x_coords - cx) / max(1, cloud_r)) ** 2
        cloud_pixels = cloud_dist <= 1.0

        # Clouds exhibit high reflectance across all optical bands
        green[cloud_pixels] = 0.85
        nir[cloud_pixels] = 0.88
        red[cloud_pixels] = 0.86
        blue[cloud_pixels] = 0.90
        swir1[cloud_pixels] = 0.80
        valid_mask[cloud_pixels] = False

    return {
        "green": green.astype(np.float32),
        "nir": nir.astype(np.float32),
        "red": red.astype(np.float32),
        "blue": blue.astype(np.float32),
        "swir1": swir1.astype(np.float32),
        "valid_mask": valid_mask,
    }


def prepare_all_samples() -> None:
    """Generate all scenario sample npz files specified in sample_manifest.json."""
    SAMPLES_DIR.mkdir(parents=True, exist_ok=True)

    scenes_spec = {
        # Scenario 1: Drawdown (Res 01)
        "res01_20231015.npz": dict(water_radii=(28, 22), cloud_fraction=0.015, seed=101),
        "res01_20240315.npz": dict(water_radii=(18, 14), cloud_fraction=0.022, seed=102),

        # Scenario 2: Monsoon Recharge (Res 02)
        "res02_20240520.npz": dict(water_radii=(12, 10), cloud_fraction=0.03, seed=201),
        "res02_20240810.npz": dict(water_radii=(26, 24), cloud_fraction=0.048, seed=202),

        # Scenario 3: Stable (Res 03)
        "res03_20231101.npz": dict(water_radii=(20, 20), cloud_fraction=0.008, seed=301),
        "res03_20231121.npz": dict(water_radii=(20, 19), cloud_fraction=0.011, seed=302),

        # Scenario 4: Cloudy (Res 04)
        "res04_20240705.npz": dict(water_radii=(22, 18), cloud_fraction=0.05, seed=401),
        "res04_20240725.npz": dict(water_radii=(22, 18), cloud_fraction=0.68, seed=402),
    }

    print(f"Preparing sample multispectral scenes in: {SAMPLES_DIR}")
    for filename, params in scenes_spec.items():
        data = generate_scene(**params)
        out_path = SAMPLES_DIR / filename
        np.savez_compressed(out_path, **data)
        print(f"  -> Generated {filename} (shape={data['green'].shape})")

    print("[SUCCESS] All sample datasets prepared successfully.")


if __name__ == "__main__":
    prepare_all_samples()
