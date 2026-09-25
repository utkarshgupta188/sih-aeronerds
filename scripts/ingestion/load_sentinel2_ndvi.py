"""
Ingestion (ADDITIVE) - Sentinel-2 NDVI for the project's existing AOI.

Produces a single-band NDVI GeoTIFF covering exactly the configured AOI, for use
by ``scripts/11_ndvi_vegetation_evidence.py`` as an independent vegetation
evidence layer on top of the Copernicus GLO-30 surface elevation.

Source
------
Sentinel-2 L2A surface reflectance (Copernicus programme), read as Cloud
Optimized GeoTIFFs from the public AWS Open Data mirror, discovered through the
Element84 "earth-search" STAC API. No credentials required.

  STAC:     https://earth-search.aws.element84.com/v1
  Data:     s3://sentinel-cogs  (AWS Open Data, us-west-2), anonymous HTTPS
  Bands:    B04 (red, 10 m), B08 (nir, 10 m), SCL (scene classification, 20 m)
  NDVI:     (B08 - B04) / (B08 + B04)
  Licence:  Free and open. "Contains modified Copernicus Sentinel data".
            https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice

CRS / AOI conventions
---------------------
The AOI bbox and ``crs_source`` / ``crs_processing`` come from
``config/regions/<region>.json`` - unchanged. Sentinel-2 tiles over the
Bengaluru AOI are natively in EPSG:32643, which is already the project's
``crs_processing``; the NDVI raster is therefore written in the scene's native
UTM CRS at 10 m and is NOT resampled here. Building footprints are reprojected to
this CRS at sampling time (same approach as ``scripts/05_match_parcels_buildings.py``).

Honesty
-------
If the scene cannot be obtained (offline, STAC empty, read error, missing
libraries) this script does NOT fabricate a raster. It writes
``data/interim/ndvi_status.json`` with ``ndvi_available: false`` and a reason,
then exits 0 so the rest of the pipeline continues. Phase 11 then marks every
building ``NDVI_UNAVAILABLE`` with a null confidence score.
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_active_config  # sys.path adjusted above

STAC_URL = "https://earth-search.aws.element84.com/v1/search"
STAC_COLLECTION = "sentinel-2-l2a"

# Defaults (used when the region config has no "ndvi" dataset block).
DEFAULT_DATETIME = "2023-11-01T00:00:00Z/2024-04-30T23:59:59Z"  # Bengaluru dry season, low cloud
DEFAULT_CLOUD_LT = 15.0

OUT_RASTER = os.path.join("data", "raw", "ndvi_s2_aoi.tif")
STATUS_PATH = os.path.join("data", "interim", "ndvi_status.json")
NDVI_NODATA = -9999.0

# SCL classes to discard (mask to NoData). Keep 2,4,5,6,7.
SCL_MASK_CLASSES = {0, 1, 3, 8, 9, 10, 11}
SCL_MASK_MEANING = {
    0: "no_data", 1: "saturated_or_defective", 3: "cloud_shadow",
    8: "cloud_medium_probability", 9: "cloud_high_probability",
    10: "thin_cirrus", 11: "snow_or_ice",
}


def _write_status(available, **extra):
    os.makedirs(os.path.dirname(STATUS_PATH), exist_ok=True)
    payload = {"ndvi_available": bool(available),
               "generated_utc": datetime.now(timezone.utc).isoformat()}
    payload.update(extra)
    with open(STATUS_PATH, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)
    return payload


def _fail(reason):
    print(f"[NDVI UNAVAILABLE] {reason}")
    _write_status(False, reason=reason)
    print(f"Wrote {STATUS_PATH}. Pipeline continues; Phase 11 will mark buildings NDVI_UNAVAILABLE.")
    sys.exit(0)


def _search_stac(bbox, datetime_range, cloud_lt, requests):
    base = {
        "collections": [STAC_COLLECTION],
        "bbox": list(bbox),
        "datetime": datetime_range,
        "limit": 10,
        "sortby": [{"field": "properties.eo:cloud_cover", "direction": "asc"}],
    }
    attempts = [
        dict(base, query={"eo:cloud_cover": {"lt": cloud_lt}}),
        dict(base),  # fallback: no cloud filter, still cloud-sorted
    ]
    last_err = None
    for body in attempts:
        try:
            resp = requests.post(STAC_URL, json=body, timeout=60)
            resp.raise_for_status()
            feats = resp.json().get("features", [])
            if feats:
                return feats[0]
        except Exception as exc:  # noqa: BLE001
            last_err = exc
    if last_err:
        raise last_err
    return None


def _asset_href(assets, *names):
    for name in names:
        if name in assets and assets[name].get("href"):
            return assets[name]["href"]
    return None


def _clip_window(win, width, height):
    """Clip a floating-point Window to a dataset's [0, width] x [0, height]."""
    from rasterio.windows import Window

    col_off = max(0, math.floor(win.col_off))
    row_off = max(0, math.floor(win.row_off))
    col_end = min(int(width), math.ceil(win.col_off + win.width))
    row_end = min(int(height), math.ceil(win.row_off + win.height))
    return Window(col_off, row_off, max(0, col_end - col_off), max(0, row_end - row_off))


def load_sentinel2_ndvi():
    config = get_active_config()
    region = config.get("region_name", "AOI")
    bbox = config["bbox"]  # [lon_min, lat_min, lon_max, lat_max], EPSG:4326
    ndvi_cfg = config.get("datasets", {}).get("ndvi", {}) or {}
    datetime_range = ndvi_cfg.get("datetime", DEFAULT_DATETIME)
    cloud_lt = float(ndvi_cfg.get("max_cloud_cover", DEFAULT_CLOUD_LT))

    print(f"Building Sentinel-2 NDVI for {region} AOI {bbox}")
    print(f"  window={datetime_range}  max_cloud_cover<{cloud_lt}%")

    if os.path.exists(OUT_RASTER):
        print(f"  {OUT_RASTER} already exists - skipping download.")
        _write_status(True, path=OUT_RASTER, note="pre-existing raster reused",
                      ndvi_source="COPERNICUS_SENTINEL-2_L2A_NDVI")
        return

    try:
        import numpy as np
        import rasterio
        import requests
        from rasterio.warp import Resampling, reproject, transform_bounds
        from rasterio.windows import from_bounds as window_from_bounds
    except ImportError as exc:
        _fail(f"required libraries missing ({exc}); run: pip install rasterio numpy requests")

    try:
        item = _search_stac(bbox, datetime_range, cloud_lt, requests)
    except Exception as exc:  # noqa: BLE001
        _fail(f"STAC search failed ({exc})")
    if item is None:
        _fail("STAC search returned no Sentinel-2 L2A scenes for this AOI / window")

    props = item.get("properties", {})
    scene_id = item.get("id")
    acq = props.get("datetime")
    cloud = props.get("eo:cloud_cover")
    assets = item.get("assets", {})
    red_href = _asset_href(assets, "red", "B04", "b04")
    nir_href = _asset_href(assets, "nir", "B08", "b08")
    scl_href = _asset_href(assets, "scl", "SCL")
    if not (red_href and nir_href):
        _fail(f"scene {scene_id} is missing red/nir assets")

    print(f"  scene={scene_id}  acquired={acq}  cloud={cloud}%")

    gdal_env = {
        "AWS_NO_SIGN_REQUEST": "YES",
        "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
        "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif",
        "GDAL_HTTP_MAX_RETRY": "3",
        "GDAL_HTTP_RETRY_DELAY": "1",
    }

    try:
        with rasterio.Env(**gdal_env):
            with rasterio.open(red_href) as red_src:
                dst_crs = red_src.crs
                # AOI bbox -> scene CRS -> integer pixel window on the red (10 m) grid.
                left, bottom, right, top = transform_bounds("EPSG:4326", dst_crs, *bbox)
                win = _clip_window(
                    window_from_bounds(left, bottom, right, top, red_src.transform),
                    red_src.width, red_src.height,
                )
                if win.width < 1 or win.height < 1:
                    _fail(f"AOI does not intersect scene {scene_id}")
                win_transform = red_src.window_transform(win)
                out_h, out_w = int(win.height), int(win.width)
                red = red_src.read(1, window=win).astype("float32")

            # B08 is the same 10 m grid as B04; reproject onto the exact red window
            # to absorb any sub-pixel offset.
            with rasterio.open(nir_href) as nir_src:
                nir_win = _clip_window(
                    window_from_bounds(left, bottom, right, top, nir_src.transform),
                    nir_src.width, nir_src.height,
                )
                nir_raw = nir_src.read(1, window=nir_win).astype("float32")
                nir = np.empty((out_h, out_w), dtype="float32")
                reproject(
                    source=nir_raw, destination=nir,
                    src_transform=nir_src.window_transform(nir_win), src_crs=nir_src.crs,
                    dst_transform=win_transform, dst_crs=dst_crs,
                    resampling=Resampling.bilinear,
                )

            # SCL is 20 m -> resample (nearest) onto the 10 m red window.
            scl = None
            if scl_href:
                with rasterio.open(scl_href) as scl_src:
                    scl_win = _clip_window(
                        window_from_bounds(left, bottom, right, top, scl_src.transform),
                        scl_src.width, scl_src.height,
                    )
                    scl_raw = scl_src.read(1, window=scl_win)
                    scl = np.zeros((out_h, out_w), dtype="uint8")
                    reproject(
                        source=scl_raw, destination=scl,
                        src_transform=scl_src.window_transform(scl_win), src_crs=scl_src.crs,
                        dst_transform=win_transform, dst_crs=dst_crs,
                        resampling=Resampling.nearest,
                    )
    except SystemExit:
        raise
    except Exception as exc:  # noqa: BLE001
        _fail(f"failed reading Sentinel-2 COGs ({exc})")

    # NDVI (scale-invariant to a common DN factor); explicit NoData handling.
    denom = nir + red
    with np.errstate(divide="ignore", invalid="ignore"):
        ndvi = (nir - red) / denom
    invalid = (
        ~np.isfinite(ndvi)
        | (denom == 0)
        | ((red == 0) & (nir == 0))   # L2A band NoData
        | (ndvi < -1.0) | (ndvi > 1.0)
    )
    masked_by_scl = 0
    if scl is not None:
        scl_bad = np.isin(scl, list(SCL_MASK_CLASSES))
        masked_by_scl = int(scl_bad.sum())
        invalid |= scl_bad
    ndvi = ndvi.astype("float32")
    ndvi[invalid] = NDVI_NODATA
    valid_count = int((~invalid).sum())
    total_count = int(ndvi.size)

    if valid_count == 0:
        _fail(f"scene {scene_id} produced no valid NDVI pixels over the AOI (cloud/NoData)")

    os.makedirs(os.path.dirname(OUT_RASTER), exist_ok=True)
    profile = {
        "driver": "GTiff", "dtype": "float32", "count": 1,
        "height": out_h, "width": out_w,
        "crs": dst_crs, "transform": win_transform,
        "nodata": NDVI_NODATA, "compress": "deflate", "predictor": 3,
    }
    with rasterio.open(OUT_RASTER, "w", **profile) as dst:
        dst.write(ndvi, 1)
        dst.update_tags(
            NDVI_FORMULA="(B08 - B04) / (B08 + B04)",
            SOURCE="Sentinel-2 L2A (Copernicus) via earth-search STAC / AWS Open Data",
            SCENE_ID=scene_id, ACQUISITION=str(acq),
        )
    print(f"  wrote {OUT_RASTER}  ({out_w}x{out_h} px, {valid_count}/{total_count} valid)")

    crs_str = dst_crs.to_string() if dst_crs else None
    provenance = (
        "Sentinel-2 L2A surface reflectance (Copernicus). "
        f"NDVI=(B08-B04)/(B08+B04) from scene {scene_id} acquired {acq}. "
        "Cloud/shadow/snow pixels masked via SCL. Native 10 m, "
        f"CRS {crs_str}, no resampling of the NDVI grid. "
        "Contains modified Copernicus Sentinel data."
    )

    manifest = {
        "dataset_id": f"ndvi_{region.lower().replace(' ', '_')}_s2l2a",
        "name": f"{region} Sentinel-2 L2A NDVI (AOI clip)",
        "source": "Copernicus Sentinel-2 L2A via Element84 earth-search STAC / AWS Open Data",
        "stac_endpoint": STAC_URL,
        "stac_collection": STAC_COLLECTION,
        "scene_id": scene_id,
        "acquisition_datetime": acq,
        "eo_cloud_cover_percent": cloud,
        "processing_baseline": props.get("s2:processing_baseline") or props.get("processing:version"),
        "bands_used": {"red": "B04 (10 m)", "nir": "B08 (10 m)", "scene_classification": "SCL (20 m -> resampled nearest to 10 m)"},
        "ndvi_formula": "(B08 - B04) / (B08 + B04)",
        "spatial_resolution_m": 10,
        "native_crs": crs_str,
        "crs_source_convention": config.get("crs_source"),
        "crs_processing_convention": config.get("crs_processing"),
        "aoi_bbox_epsg4326": list(bbox),
        "raster_size_px": [out_w, out_h],
        "nodata_value": NDVI_NODATA,
        "valid_pixels": valid_count,
        "total_pixels": total_count,
        "scl_mask_classes": {str(k): SCL_MASK_MEANING[k] for k in sorted(SCL_MASK_CLASSES)},
        "scl_masked_pixels": masked_by_scl,
        "preprocessing": [
            "STAC search (least cloud) over configured datetime window",
            "windowed read of B04/B08 COGs for the AOI bbox (reprojected to scene CRS)",
            "B08 resampled bilinear to the B04 10 m grid; SCL resampled nearest",
            "NDVI computed on DN; denom==0 and band NoData -> NoData; clamp to [-1,1]",
            "SCL classes {0,1,3,8,9,10,11} -> NoData",
            "written as float32 GeoTIFF, nodata -9999, DEFLATE",
        ],
        "licence": "Free and open - Contains modified Copernicus Sentinel data. "
                   "https://sentinels.copernicus.eu/documents/247904/690755/Sentinel_Data_Legal_Notice",
        "processing_version": "load_sentinel2_ndvi/v1",
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "local_path": OUT_RASTER,
        "known_limitations": [
            "Single-date optical scene: shadows, haze and mixed pixels remain possible.",
            "10 m pixels: small footprints may contain few valid samples.",
            "NDVI indicates vegetation response only; it is NOT a building-vs-tree classifier.",
        ],
    }
    manifest_path = os.path.join(
        "data", "manifests", f"ndvi_{region.lower().replace(' ', '_')}_manifest.json")
    os.makedirs(os.path.dirname(manifest_path), exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as fh:
        json.dump(manifest, fh, indent=2)
    print(f"  wrote {manifest_path}")

    _write_status(
        True,
        path=OUT_RASTER,
        ndvi_source="COPERNICUS_SENTINEL-2_L2A_NDVI",
        scene_id=scene_id,
        acquisition_date=acq,
        crs=crs_str,
        resolution="10 m",
        cloud_cover=cloud,
        manifest=manifest_path,
        provenance=provenance,
    )
    print(f"  wrote {STATUS_PATH}  (ndvi_available: true)")


if __name__ == "__main__":
    load_sentinel2_ndvi()
