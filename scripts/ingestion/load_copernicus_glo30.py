"""
Ingestion (ADDITIVE) - Copernicus GLO-30 DSM for the floor model.

Copernicus DEM GLO-30 is a Digital SURFACE Model (30 m) - it includes buildings
and canopy. From it we derive a coarse **above-ground height** per building:

    height ~= (max GLO-30 inside the footprint)
              - (10th-percentile GLO-30 in a 150 m ring around the footprint)   # local ground proxy

This is a documented derivation from ONE real, open dataset (no second DEM, no
synthetic values). It is coarse (30 m pixels, ~4 m LE90) - it separates low-rise
from mid- from high-rise, not 2 vs 3 floors - and the model learns how noisy it
is. Used only as a *feature*; never as ``height / floor_height`` = floors.

Source : Copernicus DEM GLO-30, ESA / (c) Copernicus, free & open, via the AWS
         Open Data mirror (anonymous HTTPS, COG).
Output : data/raw/glo30_dsm.tif   (clipped to the training + AOI bbox)
         data/manifests/glo30_dsm_manifest.json
"""

import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
from config.config_loader import get_active_config

AWS_BASE = "https://copernicus-dem-30m.s3.amazonaws.com"
OUT_TIF = os.path.join("data", "raw", "glo30_dsm.tif")
MANIFEST = os.path.join("data", "manifests", "glo30_dsm_manifest.json")

# Region we need covered: greater-Bengaluru training box + the demo AOI.
COVER_BBOX = (77.45, 12.80, 77.82, 13.12)   # (W, S, E, N)


def _tile_name(lat_deg, lon_deg):
    ns = f"N{lat_deg:02d}" if lat_deg >= 0 else f"S{abs(lat_deg):02d}"
    ew = f"E{lon_deg:03d}" if lon_deg >= 0 else f"W{abs(lon_deg):03d}"
    stem = f"Copernicus_DSM_COG_10_{ns}_00_{ew}_00_DEM"
    return f"{AWS_BASE}/{stem}/{stem}.tif"


def _needed_tiles(bbox):
    w, s, e, n = bbox
    tiles = []
    for lat in range(math.floor(s), math.floor(n) + 1):
        for lon in range(math.floor(w), math.floor(e) + 1):
            tiles.append(_tile_name(lat, lon))
    return tiles


def main():
    print("=========================================")
    print("  Copernicus GLO-30 DSM ingestion        ")
    print("=========================================\n")

    if os.path.exists(OUT_TIF):
        print(f"  {OUT_TIF} already exists - skipping.")
        return

    try:
        import numpy as np
        import rasterio
        from rasterio.merge import merge
    except ImportError as exc:
        print(f"[UNAVAILABLE] geospatial libs missing ({exc}). Floor model will run "
              "without the DSM-height feature.")
        _write_manifest(available=False, reason=str(exc))
        return

    tiles = _needed_tiles(COVER_BBOX)
    print(f"  need {len(tiles)} GLO-30 tile(s): {[t.rsplit('/', 1)[-1] for t in tiles]}")
    gdal_env = {"AWS_NO_SIGN_REQUEST": "YES", "GDAL_DISABLE_READDIR_ON_OPEN": "EMPTY_DIR",
                "CPL_VSIL_CURL_ALLOWED_EXTENSIONS": ".tif", "GDAL_HTTP_MAX_RETRY": "3"}
    try:
        with rasterio.Env(**gdal_env):
            srcs = []
            for url in tiles:
                try:
                    srcs.append(rasterio.open(url))
                    print(f"    opened {url.rsplit('/', 1)[-1]}")
                except Exception as exc:  # noqa: BLE001
                    print(f"    skip {url.rsplit('/', 1)[-1]} ({exc})")
            if not srcs:
                raise RuntimeError("no GLO-30 tiles could be opened")
            w, s, e, n = COVER_BBOX
            mosaic, transform = merge(srcs, bounds=(w, s, e, n))
            meta = srcs[0].meta.copy()
            nodata = srcs[0].nodata
            for sc in srcs:
                sc.close()
        meta.update(driver="GTiff", height=mosaic.shape[1], width=mosaic.shape[2],
                    transform=transform, compress="deflate", predictor=3, count=1)
        os.makedirs(os.path.dirname(OUT_TIF), exist_ok=True)
        with rasterio.open(OUT_TIF, "w", **meta) as dst:
            dst.write(mosaic[0], 1)
        arr = mosaic[0]
        valid = arr[np.isfinite(arr) & (arr != (nodata if nodata is not None else -9999))]
        print(f"  wrote {OUT_TIF}  ({mosaic.shape[2]}x{mosaic.shape[1]} px, "
              f"elev {valid.min():.0f}-{valid.max():.0f} m)")
        _write_manifest(available=True, size=[int(mosaic.shape[2]), int(mosaic.shape[1])],
                        elev_range=[float(valid.min()), float(valid.max())],
                        crs=str(meta.get("crs")))
        print(f"  wrote {MANIFEST}")
    except Exception as exc:  # noqa: BLE001
        print(f"[UNAVAILABLE] GLO-30 fetch failed ({exc}). Floor model will run "
              "without the DSM-height feature.")
        _write_manifest(available=False, reason=str(exc))


def _write_manifest(**kw):
    cfg = get_active_config()
    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    payload = {
        "dataset_id": "copernicus_glo30_dsm_bengaluru",
        "source": "Copernicus DEM GLO-30 (ESA / (c) Copernicus) via AWS Open Data",
        "url": AWS_BASE,
        "licence": "Free and open - (c) Copernicus / ESA; "
                   "https://spacedata.copernicus.eu/collections/copernicus-digital-elevation-model",
        "type": "Digital Surface Model, ~30 m, EPSG:4326",
        "use": "derive a coarse above-ground building height feature "
               "(footprint max minus local-ring 10th percentile); feature only",
        "cover_bbox_wsen": list(COVER_BBOX),
        "demo_aoi_bbox_epsg4326": list(cfg["bbox"]),
        "retrieved_utc": datetime.now(timezone.utc).isoformat(),
        "local_path": OUT_TIF,
        "known_limitations": [
            "30 m pixels: individual small buildings are under-resolved",
            "~4 m vertical LE90: separates low/mid/high-rise, not 2 vs 3 floors",
            "DSM includes vegetation - use with NDVI vegetation flags",
        ],
    }
    payload.update(kw)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump(payload, fh, indent=2)


if __name__ == "__main__":
    main()
