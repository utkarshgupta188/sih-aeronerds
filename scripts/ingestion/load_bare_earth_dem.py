import json
import os
import shutil
import sys
from datetime import datetime, timezone

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_active_config

# Preferred LOCAL bare-earth DEM (manually supplied). If this file exists and is
# valid for the AOI it is used as-is and OpenTopography is NOT contacted.
LOCAL_DEM_PATH = os.path.join("data", "raw", "dem", "bare_earth_dem.tif")
# Path every downstream phase already expects - unchanged.
OUT_PATH = os.path.join("data", "raw", "bare_earth_dem.tif")
LOCAL_MANIFEST_PATH = os.path.join("data", "manifests", "bare_earth_dem_local_manifest.json")


def bbox_overlaps(a, b):
    """True if two (west, south, east, north) boxes overlap. Pure, testable."""
    aw, as_, ae, an = a
    bw, bs, be, bn = b
    return not (ae < bw or aw > be or an < bs or as_ > bn)


def _validate_local_dem(path, aoi_bbox):
    """Validate the local DEM against the existing AOI.

    Returns (status, info, message) where status is:
      "ok"    - validated, safe to use
      "wrong" - readable but does NOT overlap the AOI (wrong dataset) -> hard fail
      "bad"   - unreadable / empty / missing metadata -> may fall back
    ``info`` carries only metadata actually read from the file (never fabricated).
    """
    lon_min, lat_min, lon_max, lat_max = aoi_bbox
    aoi_lonlat = (lon_min, lat_min, lon_max, lat_max)

    try:
        import numpy as np
        import rasterio
        from rasterio.warp import transform_bounds
    except ImportError:
        # Cannot validate here, but rasterio is required later anyway. Accept the
        # file so the pipeline proceeds; record that validation was deferred.
        size = os.path.getsize(path) if os.path.exists(path) else 0
        if size <= 0:
            return "bad", {}, "local DEM file is empty (0 bytes)"
        return "ok", {
            "validated": False,
            "validation_note": "rasterio unavailable at ingestion; deferred to Phase 3/6",
            "file_size_bytes": size,
        }, "rasterio not installed - accepted local DEM without full validation"

    try:
        with rasterio.open(path) as src:
            if src.count < 1:
                return "bad", {}, "no raster band found"
            if src.crs is None:
                return "bad", {}, "raster has no CRS"

            res = src.res
            bounds = src.bounds
            nodata = src.nodata

            # DEM footprint expressed in EPSG:4326 for the AOI overlap test.
            try:
                dem_ll = transform_bounds(src.crs, "EPSG:4326", *bounds, densify_pts=21)
            except Exception as exc:  # noqa: BLE001
                return "bad", {}, f"CRS could not be transformed to EPSG:4326 ({exc})"

            info = {
                "validated": True,
                "driver": src.driver,
                "crs": str(src.crs),
                "width": src.width,
                "height": src.height,
                "resolution": [abs(res[0]), abs(res[1])],
                "bounds_native": [bounds.left, bounds.bottom, bounds.right, bounds.top],
                "bounds_epsg4326": [dem_ll[0], dem_ll[1], dem_ll[2], dem_ll[3]],
                "nodata": None if nodata is None else float(nodata),
                "dtype": src.dtypes[0],
            }

            if not bbox_overlaps(dem_ll, aoi_lonlat):
                return "wrong", info, (
                    "local DEM does not overlap the Bengaluru AOI - wrong geographic "
                    f"dataset supplied.\n    DEM bounds (EPSG:4326): {dem_ll}\n"
                    f"    Required AOI (W,S,E,N): {aoi_lonlat}"
                )

            # Reject a completely empty / all-NoData raster (decimated read).
            oh = min(512, src.height)
            ow = min(512, src.width)
            sample = src.read(1, out_shape=(1, oh, ow)).astype("float64")
            if nodata is not None:
                sample = sample[sample != nodata]
            sample = sample[np.isfinite(sample)]
            if sample.size == 0:
                return "bad", info, "raster is entirely empty / NoData"
            info["sample_min"] = float(sample.min())
            info["sample_max"] = float(sample.max())
            if info["sample_min"] == info["sample_max"]:
                return "bad", info, (
                    f"raster is constant ({info['sample_min']}) - not a usable DEM"
                )

        return "ok", info, "validated"
    except rasterio.errors.RasterioIOError as exc:
        return "bad", {}, f"not readable by rasterio ({exc})"
    except Exception as exc:  # noqa: BLE001
        return "bad", {}, f"validation error ({exc})"


def _write_local_manifest(info, local_path):
    os.makedirs(os.path.dirname(LOCAL_MANIFEST_PATH), exist_ok=True)
    manifest = {
        "dataset_id": "bare_earth_dem_local",
        "dem_source": "LOCAL_BARE_EARTH_DEM",
        "dem_path": local_path.replace("\\", "/"),
        "used_as": OUT_PATH.replace("\\", "/"),
        "filename": os.path.basename(local_path),
        "supplied_by": "manual (operator-provided GeoTIFF)",
        "authoritative": False,
        "note": (
            "Local bare-earth / terrain DEM supplied for reproducible local execution. "
            "Used as the ground/terrain reference only. It does NOT replace the "
            "Copernicus GLO-30 surface elevation or the NDVI vegetation-evidence layer."
        ),
        "aoi_epsg4326_wsen": list(get_active_config()["bbox"]),
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        **info,
    }
    with open(LOCAL_MANIFEST_PATH, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"  Provenance written: {LOCAL_MANIFEST_PATH}")


def _try_local_dem(config):
    """Returns True if the local DEM was accepted and staged to OUT_PATH."""
    os.makedirs(os.path.dirname(LOCAL_DEM_PATH), exist_ok=True)
    aoi_bbox = config["bbox"]  # [lon_min, lat_min, lon_max, lat_max]

    if not os.path.exists(LOCAL_DEM_PATH):
        print("[LOCAL DEM MISSING]")
        print(f"  Expected at: {os.path.abspath(LOCAL_DEM_PATH)}")
        print("  Place a bare-earth DEM GeoTIFF covering the Bengaluru AOI "
              "(W,S,E,N = 77.61365, 12.92365, 77.62635, 12.93635) there to skip "
              "the OpenTopography API-key requirement.")
        print("  Falling back to the existing OpenTopography download mechanism...")
        return False

    print(f"[LOCAL DEM FOUND] {LOCAL_DEM_PATH}")
    status, info, message = _validate_local_dem(LOCAL_DEM_PATH, aoi_bbox)

    if status == "wrong":
        print(f"[LOCAL DEM REJECTED] {message}")
        print("DEM STATUS: INVALID / WRONG GEOGRAPHY")
        sys.exit(1)

    if status == "bad":
        print(f"[LOCAL DEM INVALID] {message}")
        print("  Falling back to the existing OpenTopography download mechanism...")
        return False

    # status == "ok"
    print(f"  Validation: {message}")
    for key in ("crs", "resolution", "bounds_epsg4326", "nodata", "width", "height"):
        if key in info:
            print(f"    {key}: {info[key]}")
    shutil.copyfile(LOCAL_DEM_PATH, OUT_PATH)
    print(f"  Staged local DEM -> {OUT_PATH}")
    print("  dem_source = LOCAL_BARE_EARTH_DEM")
    print("  OpenTopography: NOT CONTACTED (local DEM used).")
    _write_local_manifest(info, LOCAL_DEM_PATH)
    return True


def load_bare_earth_dem():
    config = get_active_config()
    print(f"Resolving Bare-Earth DEM for {config['region_name']}...")

    bbox = config["bbox"]
    lon_min, lat_min, lon_max, lat_max = bbox
    out_path = OUT_PATH
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    if os.path.exists(out_path):
        print(f"File {out_path} already exists. Skipping download.")
        return

    # 1) Prefer a manually supplied local DEM - no API key, fully reproducible.
    if _try_local_dem(config):
        return

    # 2) Existing OpenTopography mechanism (unchanged) as the fallback.
    api_key = os.environ.get("OPEN_TOPOGRAPHY_API", "")
    url = f"https://portal.opentopography.org/API/globaldem?demtype=SRTMGL1&south={lat_min}&north={lat_max}&west={lon_min}&east={lon_max}&outputFormat=GTiff"
    if api_key:
        url += f"&API_Key={api_key}"

    try:
        import requests

        print("Fetching SRTM 30m from OpenTopography...")
        r = requests.get(url, stream=True, timeout=30)

        if r.status_code == 200:
            with open(out_path, "wb") as f:
                for chunk in r.iter_content(chunk_size=8192):
                    f.write(chunk)
            print(f"Successfully downloaded Bare-Earth DEM to {out_path}")

            # Basic validation
            try:
                import rasterio
                with rasterio.open(out_path) as src:
                    print(f"Validation: CRS={src.crs}, Resolution={src.res}, Bounds={src.bounds}")
            except ImportError:
                print("rasterio not installed, skipping validation.")
        else:
            print(f"Failed to download. OpenTopography returned status code {r.status_code}")
            print(f"Response text: {r.text}")
            print("DEM STATUS: INVALID / UNSUPPORTED")
            print("STOP HEIGHT DERIVATION. Required DEM source could not be obtained.")
            print(f"HINT: supply a local DEM at {os.path.abspath(LOCAL_DEM_PATH)} "
                  "to run without an OpenTopography API key.")
            sys.exit(1)

    except SystemExit:
        raise
    except Exception as e:
        print(f"Failed to download DEM automatically: {e}")
        print("DEM STATUS: INVALID / UNSUPPORTED")
        print("STOP HEIGHT DERIVATION.")
        print(f"HINT: supply a local DEM at {os.path.abspath(LOCAL_DEM_PATH)} "
              "to run without an OpenTopography API key.")
        sys.exit(1)


if __name__ == "__main__":
    load_bare_earth_dem()
