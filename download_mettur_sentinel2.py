#!/usr/bin/env python3
r"""
Download and crop two genuine Sentinel-2 Level-2A B03/B08 observations
around Mettur Reservoir from the public Earth Search STAC catalog.

No account/API key is required. Requires: requests, rasterio, numpy.
Run from the Micro-Reservoir Intelligence project root:
    .\.venv\Scripts\python.exe .\download_mettur_sentinel2.py

Important:
- This script downloads real data only when run on a machine with internet access.
- It does not fabricate imagery or measurements.
- Catalog cloud cover is scene-level metadata, not a verified local cloud mask.
- The script refuses to continue if it cannot find two observations with a
  compatible tile/grid or if the resulting cropped rasters are incompatible.
"""
from __future__ import annotations

import json
import math
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

try:
    import requests
    import numpy as np
    import rasterio
    from rasterio.features import geometry_mask, geometry_window
    from rasterio.warp import transform_geom
except ImportError as exc:
    print(f"Missing dependency: {exc}")
    print("Install in the project environment with:")
    print(r"  .\.venv\Scripts\python.exe -m pip install requests rasterio")
    print("If pip is unavailable, use your existing environment's package manager.")
    sys.exit(2)

# Small study window around Mettur Reservoir, Tamil Nadu (WGS84).
# This is a rectangular study area, not a surveyed reservoir boundary.
STUDY_BBOX = (77.72, 11.74, 77.90, 11.88)  # west, south, east, north
COLLECTION = "sentinel-2-c1-l2a"
STAC_SEARCH = "https://earth-search.aws.element84.com/v1/search"
START_DATE = "2023-01-01T00:00:00Z"
END_DATE = datetime.now(timezone.utc).strftime("%Y-%m-%dT23:59:59Z")
MAX_SCENE_CLOUD = 35.0
MIN_DAYS_APART = 30
OUTPUT_DIR = Path("data/real_mettur")
MANIFEST_PATH = OUTPUT_DIR / "download_manifest.json"

# Recommended GDAL environment settings for efficient, resilient remote COG range reads
GDAL_ENV_SETTINGS: dict[str, str] = {
    "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
    "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif,.tiff",
    "GDAL_HTTP_MULTIRANGE": "YES",
    "GDAL_HTTP_MERGE_CONSECUTIVE_RANGES": "YES",
    "GDAL_HTTP_TIMEOUT": "30",
    "GDAL_HTTP_CONNECTTIMEOUT": "15",
    "GDAL_HTTP_MAX_RETRY": "4",
    "GDAL_HTTP_RETRY_DELAY": "2",
    "VSI_CACHE": "TRUE",
    "VSI_CACHE_SIZE": "10485760",
}


def get_asset(item: dict[str, Any], band: str) -> tuple[str, str]:
    """Return (asset key, href) for Sentinel-2 B03 or B08."""
    assets = item.get("assets", {})
    preferred = {
        "B03": ("B03_10m", "B03", "green"),
        "B08": ("B08_10m", "B08", "nir"),
    }[band]
    for key in preferred:
        asset = assets.get(key)
        if asset and str(asset.get("href", "")).startswith("https://"):
            return key, asset["href"]

    # Fall back to STAC EO metadata, while avoiding the B8A/NIR08 asset.
    for key, asset in assets.items():
        if not str(asset.get("href", "")).startswith("https://"):
            continue
        if band == "B08" and key.lower() in {"nir08", "nir_08", "b8a", "b08a"}:
            continue
        eo_bands = asset.get("eo:bands", [])
        names = " ".join(
            str(v).lower()
            for b in eo_bands
            for v in (b.get("name", ""), b.get("common_name", ""))
        )
        title = str(asset.get("title", "")).lower()
        combined = f"{key.lower()} {names} {title}"
        if band == "B03" and (
            "b03" in combined or key.lower() == "green" or "common_name green" in names
        ):
            return key, asset["href"]
        if band == "B08" and (
            "b08" in combined or key.lower() == "nir" or "common_name nir" in names
        ):
            return key, asset["href"]
    raise RuntimeError(
        f"Could not identify the {band} 10 m asset in item {item.get('id')}. "
        f"Available asset keys: {', '.join(assets.keys())}"
    )


def item_tile(item: dict[str, Any]) -> str:
    props = item.get("properties", {})
    return str(
        props.get("s2:mgrs_tile")
        or props.get("grid:code")
        or props.get("proj:epsg")
        or "unknown-grid"
    )


def item_datetime(item: dict[str, Any]) -> datetime:
    value = item.get("properties", {}).get("datetime")
    if not value:
        raise ValueError(f"Item {item.get('id')} has no acquisition datetime")
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def bbox_overlap_ratio(item_bbox: list[float] | None, study_bbox: tuple[float, float, float, float]) -> float:
    """Calculate the fractional overlap area between an item's bounding box and the study area."""
    if not item_bbox or len(item_bbox) < 4:
        return 0.0
    w = max(item_bbox[0], study_bbox[0])
    s = max(item_bbox[1], study_bbox[1])
    e = min(item_bbox[2], study_bbox[2])
    n = min(item_bbox[3], study_bbox[3])
    if e > w and n > s:
        study_area = (study_bbox[2] - study_bbox[0]) * (study_bbox[3] - study_bbox[1])
        return (e - w) * (n - s) / study_area if study_area > 0 else 0.0
    return 0.0


def search_items() -> list[dict[str, Any]]:
    west, south, east, north = STUDY_BBOX
    polygon = {
        "type": "Polygon",
        "coordinates": [[
            [west, south], [east, south], [east, north],
            [west, north], [west, south]
        ]],
    }
    body = {
        "collections": [COLLECTION],
        "intersects": polygon,
        "datetime": f"{START_DATE}/{END_DATE}",
        "limit": 100,
        "sortby": [{"field": "properties.datetime", "direction": "desc"}],
    }
    print("Searching public Earth Search catalog for Mettur-area scenes...")
    try:
        response = requests.post(STAC_SEARCH, json=body, timeout=60)
        response.raise_for_status()
    except requests.exceptions.Timeout as exc:
        raise RuntimeError(
            f"STAC search request timed out after 60s at {STAC_SEARCH}. "
            "Please check your internet connection or try again later."
        ) from exc
    except requests.exceptions.RequestException as exc:
        raise RuntimeError(
            f"STAC search failed against {STAC_SEARCH}: {exc}. "
            "Verify network connectivity and proxy settings."
        ) from exc

    features = response.json().get("features", [])
    print(f"Catalog returned {len(features)} candidate items.")
    if not features:
        raise RuntimeError(
            f"No Sentinel-2 items returned by Earth Search catalog for bounding box {STUDY_BBOX} "
            f"between {START_DATE} and {END_DATE}."
        )
    return features


def choose_pair(items: list[dict[str, Any]]) -> tuple[dict[str, Any], dict[str, Any]]:
    candidates = []
    for item in items:
        props = item.get("properties", {})
        cloud = props.get("eo:cloud_cover")
        if cloud is not None and float(cloud) > MAX_SCENE_CLOUD:
            continue
        try:
            get_asset(item, "B03")
            get_asset(item, "B08")
            acquired = item_datetime(item)
        except (RuntimeError, ValueError):
            continue
        overlap = bbox_overlap_ratio(item.get("bbox"), STUDY_BBOX)
        candidates.append((item, acquired, float(cloud) if cloud is not None else 100.0, overlap))

    # Evaluate candidate pairs that share tile and EPSG, and meet the minimum temporal separation.
    # Prioritize pairs with maximum coverage of the study bbox (e.g. MGRS-43PHP over 43PGN sliver),
    # then prefer more recent observations.
    valid_pairs = []
    for i, (newer, newer_dt, _, newer_cov) in enumerate(candidates):
        for older, older_dt, _, older_cov in candidates[i + 1:]:
            if item_tile(newer) != item_tile(older):
                continue
            if abs((newer_dt - older_dt).days) < MIN_DAYS_APART:
                continue
            if newer.get("properties", {}).get("proj:epsg") != older.get("properties", {}).get("proj:epsg"):
                continue
            pair_coverage = min(newer_cov, older_cov)
            valid_pairs.append((pair_coverage, newer_dt, older, newer))

    if valid_pairs:
        # Sort primarily by study area overlap coverage (descending), secondarily by acquisition recency
        valid_pairs.sort(key=lambda p: (p[0], p[1]), reverse=True)
        best_cov, _, older, newer = valid_pairs[0]
        print(f"Selected pair on tile {item_tile(newer)} (study area coverage: {best_cov * 100:.1f}%):")
        print(f"  Older: {older.get('id')} ({item_datetime(older).date()})")
        print(f"  Newer: {newer.get('id')} ({item_datetime(newer).date()})")
        return older, newer

    # Don't quietly choose incompatible observations.
    summary = [
        {
            "id": x.get("id"),
            "datetime": x.get("properties", {}).get("datetime"),
            "cloud_cover": x.get("properties", {}).get("eo:cloud_cover"),
            "tile": item_tile(x),
            "epsg": x.get("properties", {}).get("proj:epsg"),
            "study_overlap": round(cov, 3),
        }
        for x, _, _, cov in candidates[:12]
    ]
    raise RuntimeError(
        "Could not find two observations satisfying the same-tile/grid and "
        f"{MIN_DAYS_APART}-day requirements. Try a wider date range or looser "
        f"cloud threshold. Candidate summary:\n{json.dumps(summary, indent=2)}"
    )


def write_crop(item: dict[str, Any], band: str, destination: Path, max_retries: int = 3) -> dict[str, Any]:
    key, href = get_asset(item, band)
    west, south, east, north = STUDY_BBOX
    wgs84_geom = {
        "type": "Polygon",
        "coordinates": [[
            [west, south], [east, south], [east, north],
            [west, north], [west, south]
        ]],
    }
    print(f"Reading {band} from {item.get('id')} (asset: {key})...")

    last_error: Exception | None = None
    for attempt in range(1, max_retries + 1):
        try:
            with rasterio.Env(**GDAL_ENV_SETTINGS):
                with rasterio.open(href) as src:
                    if src.crs is None:
                        raise RuntimeError(f"{band} asset has no CRS")

                    # Transform study area geometry to the raster CRS (e.g. UTM EPSG:32643)
                    geom = transform_geom("EPSG:4326", src.crs, wgs84_geom)

                    # Compute the exact bounding raster window for the study area.
                    # This reads only the study-area raster window instead of unnecessarily
                    # reading a whole tile (10980x10980 pixels).
                    win = geometry_window(src, [geom])
                    out_transform = src.window_transform(win)

                    # Read only the study-area window from remote COG via HTTP range requests
                    band_data = src.read(1, window=win)
                    source_mask = src.read_masks(1, window=win)

                    # Create polygon geometry mask inside this window
                    win_height = int(win.height)
                    win_width = int(win.width)
                    geom_mask = geometry_mask(
                        [geom],
                        out_shape=(win_height, win_width),
                        transform=out_transform,
                        invert=True,  # True means inside polygon is valid
                    )

                    # Preserve NoData and invalid-pixel masks. Never convert missing pixels
                    # into valid dry-land pixels.
                    nodata_val = src.nodata if src.nodata is not None else 0
                    valid_mask = (source_mask > 0) & geom_mask
                    if nodata_val is not None:
                        if np.isnan(nodata_val):
                            valid_mask &= ~np.isnan(band_data)
                        else:
                            valid_mask &= (band_data != nodata_val)
                    valid_mask &= ~np.isnan(band_data)
                    valid_mask &= ~np.isinf(band_data)

                    # Ensure valid data exists in the window
                    valid_count = int(np.sum(valid_mask))
                    if valid_count == 0:
                        raise RuntimeError(
                            f"Cropped window for {band} in scene {item.get('id')} contains 0 valid pixels."
                        )

                    # Fill invalid/NoData pixels with nodata_val
                    out_image = band_data.copy()
                    out_image[~valid_mask] = nodata_val

                    profile = src.profile.copy()
                    profile.update(
                        driver="GTiff",
                        height=win_height,
                        width=win_width,
                        transform=out_transform,
                        count=1,
                        nodata=nodata_val,
                        compress="deflate",
                        tiled=True,
                    )

                    destination.parent.mkdir(parents=True, exist_ok=True)
                    # Write band raster and write internal GDAL mask band (255=valid, 0=nodata)
                    with rasterio.open(destination, "w", **profile) as dst:
                        dst.write(out_image, 1)
                        dst.write_mask((valid_mask.astype(np.uint8)) * 255)

                    return {
                        "path": str(destination.as_posix()),
                        "band": band,
                        "asset_key": key,
                        "source_href": href,
                        "source_item_id": item.get("id"),
                        "acquisition_datetime": item.get("properties", {}).get("datetime"),
                        "scene_cloud_cover_percent": item.get("properties", {}).get("eo:cloud_cover"),
                        "crs": str(src.crs),
                        "width": win_width,
                        "height": win_height,
                        "transform": list(out_transform)[:6],
                        "resolution": list(src.res),
                        "nodata": nodata_val,
                        "valid_pixel_count": valid_count,
                        "total_pixel_count": win_height * win_width,
                    }

        except Exception as exc:
            last_error = exc
            print(f"  Attempt {attempt}/{max_retries} failed for {band} ({key}): {exc}")
            if attempt < max_retries:
                backoff = attempt * 2
                print(f"  Waiting {backoff}s before retry...")
                time.sleep(backoff)

    # Provide actionable error details upon failure
    actionable_msg = (
        f"Failed to read remote Sentinel-2 {band} COG after {max_retries} attempts.\n"
        f"Asset href: {href}\n"
        f"Underlying error: {last_error}\n"
        "Actionable troubleshooting steps:\n"
        "1. Check your internet connection and verify that HTTP range requests to AWS S3 are allowed.\n"
        "2. If working behind a corporate proxy or VPN, ensure HTTPS access to s3.us-west-2.amazonaws.com is enabled.\n"
        "3. Earth Search S3 endpoints may experience temporary throttling; wait a few moments and re-run.\n"
        "4. If network latency is high, consider increasing GDAL_HTTP_TIMEOUT in GDAL_ENV_SETTINGS."
    )
    raise RuntimeError(actionable_msg) from last_error


def validate_downloaded_rasters(records: list[dict[str, Any]]) -> None:
    """Validate CRS, dimensions, affine transforms, and band compatibility before reporting success."""
    if len(records) != 4:
        raise RuntimeError(f"Expected 4 downloaded band files (2 dates x 2 bands); got {len(records)}.")

    paths = [Path(row["path"]) for row in records]
    for p in paths:
        if not p.is_file() or p.stat().st_size == 0:
            raise RuntimeError(f"Downloaded raster file is missing or empty: {p}")

    signatures = []
    for p in paths:
        with rasterio.open(p) as ds:
            if ds.crs is None:
                raise RuntimeError(f"Downloaded raster {p} has no CRS defined.")
            if ds.crs.is_geographic:
                raise RuntimeError(
                    f"Downloaded raster {p} has geographic CRS ({ds.crs}). Expected planar UTM CRS."
                )
            if ds.count != 1:
                raise RuntimeError(f"Downloaded raster {p} has {ds.count} bands. Expected single band.")
            # Verify that raster contains valid pixels
            mask = ds.read_masks(1)
            if np.sum(mask > 0) == 0:
                raise RuntimeError(f"Downloaded raster {p} contains 0 valid pixels.")
            signatures.append({
                "path": str(p),
                "crs": str(ds.crs),
                "width": ds.width,
                "height": ds.height,
                "transform": tuple(ds.transform),
            })

    # Validate identical CRS across all 4 files
    crss = {s["crs"] for s in signatures}
    if len(crss) != 1:
        raise RuntimeError(f"CRS mismatch among downloaded rasters: {crss}")

    # Validate identical dimensions
    dimensions = {(s["width"], s["height"]) for s in signatures}
    if len(dimensions) != 1:
        raise RuntimeError(f"Dimension mismatch among downloaded rasters: {dimensions}")

    # Validate affine transform consistency
    ref_transform = np.array(signatures[0]["transform"])
    for s in signatures[1:]:
        t = np.array(s["transform"])
        if not np.allclose(t, ref_transform, atol=1e-3):
            raise RuntimeError(
                f"Affine transform mismatch between {signatures[0]['path']} and {s['path']}:\n"
                f"  Ref: {ref_transform}\n  Got: {t}"
            )

    # Validate band pairing for each date
    by_date: dict[str, set[str]] = {}
    for r in records:
        dt = r["acquisition_datetime"][:10]
        by_date.setdefault(dt, set()).add(r["band"])

    if len(by_date) != 2:
        raise RuntimeError(f"Expected observations for exactly 2 distinct dates; got {len(by_date)}: {list(by_date.keys())}")

    for dt, bands in by_date.items():
        if bands != {"B03", "B08"}:
            raise RuntimeError(f"Observation {dt} is missing required bands. Expected {{'B03', 'B08'}}, got {bands}.")

    # Finally, validate compatibility using the project's own geotiff loader if available
    try:
        from src.microreservoir.geotiff import load_geotiff_observation
        dates_sorted = sorted(by_date.keys())
        for idx, dt in enumerate(dates_sorted):
            b03_file = next(r["path"] for r in records if r["acquisition_datetime"].startswith(dt) and r["band"] == "B03")
            b08_file = next(r["path"] for r in records if r["acquisition_datetime"].startswith(dt) and r["band"] == "B08")
            obs = load_geotiff_observation(
                scene_id=f"REAL_METTUR_{dt}",
                date_str=dt,
                band_files={"green": b03_file, "nir": b08_file},
            )
            print(f"Validated with project loader: observation {idx + 1} ({dt}) - {obs.metadata.notes}")
    except Exception as exc:
        raise RuntimeError(f"Project loader validation failed on downloaded files: {exc}") from exc


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    items = search_items()
    older, newer = choose_pair(items)
    selected = [("date1", older), ("date2", newer)]
    records = []
    for label, item in selected:
        dt = item_datetime(item).date().isoformat()
        for band in ("B03", "B08"):
            destination = OUTPUT_DIR / f"{label}_{dt}_{band}.tif"
            records.append(write_crop(item, band, destination))

    # Validate CRS, dimensions, affine transforms, and band compatibility before reporting success
    print("\nValidating downloaded rasters for spatial consistency and grid compatibility...")
    validate_downloaded_rasters(records)

    manifest = {
        "study_id": "mettur-reservoir",
        "data_status": "genuine_public_satellite_data_downloaded_and_verified",
        "source_catalog": STAC_SEARCH,
        "collection": COLLECTION,
        "study_bbox_wgs84": list(STUDY_BBOX),
        "cloud_note": (
            "Scene-level catalog cloud-cover metadata only. No local cloud mask "
            "was supplied or independently verified; the application does not "
            "perform cloud detection."
        ),
        "observations": records,
        "grid_compatibility": "identical CRS, dimensions, and affine transform verified by downloader",
        "downloaded_at_utc": datetime.now(timezone.utc).isoformat(),
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print("\nSUCCESS: Four real-data band files were downloaded/cropped and their grids match.")
    print(f"Output folder: {OUTPUT_DIR.resolve()}")
    for row in records:
        print(f"  {row['path']} (Valid pixels: {row['valid_pixel_count']}/{row['total_pixel_count']})")
    print(f"Manifest: {MANIFEST_PATH.resolve()}")
    print("\nNext: open the app and select these four files. Check its valid coverage,")
    print("CRS/grid details, warnings, and outputs before presenting any measurements.")
    print("Note: scene cloud cover is not a local cloud-mask validation.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"\nDOWNLOAD/PREPARATION FAILED: {exc}", file=sys.stderr)
        print("No real measurements have been produced. See the error above.", file=sys.stderr)
        raise SystemExit(1)
