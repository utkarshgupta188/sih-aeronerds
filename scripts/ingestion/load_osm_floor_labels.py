"""
Ingestion (ADDITIVE) - REAL OSM building:levels training labels for Bengaluru.

Pulls every building in a large Bengaluru bounding box that carries a real
``building:levels`` tag, from the OpenStreetMap Overpass API (data (c) OSM
contributors, ODbL). ~12.8k buildings as of 2026-09.

These are used as a **real-world labelled reference source** for a supervised
floor-count model - NOT municipal legal approval, NOT ground truth. Provenance,
distribution and cleaning are documented in the manifest and
``docs/FLOOR_MODEL_REPORT.md``.

The demonstration AOI bbox is EXCLUDED from the pull, so the AOI's own labelled
buildings stay an independent evaluation set (no train/test leakage).

Output:
  data/interim/osm_floor_labels.csv         one row per labelled building
  data/manifests/osm_floor_labels_manifest.json
"""

import csv
import json
import math
import os
import sys
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
from floor_features import dsm_height_at

from config.config_loader import get_active_config

GLO30_TIF = os.path.join("data", "raw", "glo30_dsm.tif")

OVERPASS_ENDPOINTS = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
    "https://maps.mail.ru/osm/tools/overpass/api/interpreter",
]
UA = {"User-Agent": "BoundaryLens-SIH/1.0 (floor-label research)"}

# Greater Bengaluru training box (S,W,N,E). ~30 x 30 km around the AOI.
TRAIN_BBOX = (12.82, 77.48, 13.10, 77.78)

OUT_CSV = os.path.join("data", "interim", "osm_floor_labels.csv")
MANIFEST = os.path.join("data", "manifests", "osm_floor_labels_manifest.json")

_RESIDENTIAL = {"residential", "apartments", "house", "detached", "terrace",
                "semidetached_house", "dormitory", "bungalow", "hut"}
_COMMERCIAL = {"commercial", "retail", "office", "supermarket", "hotel", "kiosk",
               "shop", "mall"}
_CIVIC = {"school", "college", "university", "hospital", "government", "civic",
          "public", "church", "temple", "mosque", "place_of_worship", "hall"}
_INDUSTRIAL = {"industrial", "warehouse", "factory", "manufacture"}


def _fetch(bbox):
    import requests

    s, w, n, e = bbox
    query = (
        f"[out:json][timeout:240];"
        f'(way["building"]["building:levels"]({s},{w},{n},{e}););'
        f"out geom tags;"
    )
    last = None
    for url in OVERPASS_ENDPOINTS:
        try:
            print(f"  Overpass: {url}")
            r = requests.post(url, data={"data": query}, headers=UA, timeout=280)
            if r.status_code == 200:
                return r.json()
            last = f"HTTP {r.status_code}"
            print(f"    -> {last}")
        except Exception as exc:  # noqa: BLE001
            last = str(exc)
            print(f"    -> {last}")
    raise RuntimeError(f"all Overpass endpoints failed ({last})")


def _utm_ring(geom):
    """geom = list of {lat,lon}. Returns metric (x,y) ring via local equirect proj."""
    if not geom or len(geom) < 3:
        return None
    lat0 = sum(p["lat"] for p in geom) / len(geom)
    k = math.cos(math.radians(lat0))
    return [((p["lon"]) * 111320.0 * k, (p["lat"]) * 110540.0) for p in geom]


def _poly_area_perim(ring):
    a = 0.0
    p = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
        p += math.hypot(x2 - x1, y2 - y1)
    return abs(a) / 2.0, p


def _min_rot_rect_dims(ring):
    """Rotating-calipers-lite: min-area bounding box over edge orientations."""
    best = None
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        ang = math.atan2(y2 - y1, x2 - x1)
        ca, sa = math.cos(-ang), math.sin(-ang)
        xs = [px * ca - py * sa for px, py in ring]
        ys = [px * sa + py * ca for px, py in ring]
        w = max(xs) - min(xs)
        h = max(ys) - min(ys)
        area = w * h
        if best is None or area < best[0]:
            best = (area, max(w, h), min(w, h))
    return best[1], best[2]  # long, short


def _levels(v):
    try:
        f = float(str(v).split(";")[0].strip())
    except (TypeError, ValueError):
        return None
    if not math.isfinite(f) or f < 1 or f > 60 or abs(f - round(f)) > 1e-6:
        return None
    return round(f)


def _height(tags):
    for key in ("height", "building:height"):
        v = tags.get(key)
        if v is None:
            continue
        try:
            return float(str(v).lower().replace("m", "").split(";")[0].strip())
        except (TypeError, ValueError):
            pass
    return None


def _type_bucket(tags):
    b = str(tags.get("building", "yes")).lower()
    if b in _RESIDENTIAL:
        return "residential"
    if b in _COMMERCIAL or tags.get("shop") or tags.get("office"):
        return "commercial"
    if b in _CIVIC or tags.get("amenity") in {"school", "college", "hospital", "place_of_worship"}:
        return "civic"
    if b in _INDUSTRIAL:
        return "industrial"
    return "other"


def _feature_row(el, aoi_bbox):
    tags = el.get("tags", {})
    lvl = _levels(tags.get("building:levels"))
    if lvl is None:
        return None
    geom = el.get("geometry")
    ring_ll = [{"lat": g["lat"], "lon": g["lon"]} for g in (geom or []) if "lat" in g]
    if len(ring_ll) < 4:
        return None
    lat = sum(p["lat"] for p in ring_ll) / len(ring_ll)
    lon = sum(p["lon"] for p in ring_ll) / len(ring_ll)
    lon_min, lat_min, lon_max, lat_max = aoi_bbox
    if lon_min <= lon <= lon_max and lat_min <= lat <= lat_max:
        return None  # exclude the demo AOI - keep it as an independent eval set

    ring = _utm_ring(ring_ll)
    if ring is None:
        return None
    area, perim = _poly_area_perim(ring)
    if area < 8 or perim <= 0:
        return None
    long_s, short_s = _min_rot_rect_dims(ring)
    rect_area = max(long_s * short_s, 1e-6)
    return {
        "osm_id": el.get("id"),
        "lat": round(lat, 6),
        "lon": round(lon, 6),
        "levels": lvl,
        "height_tag": _height(tags) or "",
        "building_type": _type_bucket(tags),
        "area_m2": round(area, 1),
        "perimeter_m": round(perim, 1),
        "compactness": round(4 * math.pi * area / (perim * perim), 4),   # Polsby-Popper
        "rectangularity": round(min(area / rect_area, 1.0), 4),
        "elongation": round(short_s / long_s, 4) if long_s else 0.0,
        "long_side_m": round(long_s, 1),
        "short_side_m": round(short_s, 1),
        "n_vertices": len(ring_ll) - 1,
        "has_name": 1 if tags.get("name") else 0,
    }


def main():
    print("=========================================")
    print("  OSM building:levels label ingestion    ")
    print("=========================================\n")
    cfg = get_active_config()
    aoi = cfg["bbox"]

    try:
        raw = _fetch(TRAIN_BBOX)
    except Exception as exc:  # noqa: BLE001
        print(f"[UNAVAILABLE] {exc}")
        print("Floor model cannot be trained without real labels. Phase 12 will "
              "mark buildings NOT_DETERMINABLE.")
        os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
        with open(MANIFEST, "w", encoding="utf-8") as fh:
            json.dump({"available": False, "reason": str(exc),
                       "generated_utc": datetime.now(timezone.utc).isoformat()}, fh, indent=2)
        return

    els = raw.get("elements", [])
    print(f"  fetched {len(els)} OSM ways with a building:levels tag")
    rows = []
    for el in els:
        row = _feature_row(el, aoi)
        if row:
            rows.append(row)
    print(f"  usable labelled buildings after cleaning (AOI excluded): {len(rows)}")

    # coarse above-ground DSM height feature (Copernicus GLO-30), if available
    dsm_ok = 0
    if os.path.exists(GLO30_TIF):
        try:
            import numpy as np
            import rasterio
            with rasterio.open(GLO30_TIF) as dsm:
                for r in rows:
                    h = dsm_height_at(dsm, r["lon"], r["lat"], np)
                    r["dsm_height_m"] = round(h, 1) if h is not None else ""
                    dsm_ok += 1 if h is not None else 0
            print(f"  DSM height sampled for {dsm_ok}/{len(rows)} buildings (GLO-30)")
        except Exception as exc:  # noqa: BLE001
            print(f"  [WARN] DSM sampling failed ({exc}); training without dsm_height_m")
            for r in rows:
                r.setdefault("dsm_height_m", "")
    else:
        print(f"  {GLO30_TIF} not found - run scripts/ingestion/load_copernicus_glo30.py "
              "for the DSM-height feature. Training will proceed without it.")
        for r in rows:
            r.setdefault("dsm_height_m", "")

    dist = {}
    for r in rows:
        dist[r["levels"]] = dist.get(r["levels"], 0) + 1
    print(f"  floor-count distribution: {dict(sorted(dist.items()))}")

    os.makedirs(os.path.dirname(OUT_CSV), exist_ok=True)
    fields = list(rows[0].keys()) if rows else []
    with open(OUT_CSV, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)
    print(f"  wrote {OUT_CSV}")

    os.makedirs(os.path.dirname(MANIFEST), exist_ok=True)
    with open(MANIFEST, "w", encoding="utf-8") as fh:
        json.dump({
            "available": True,
            "dataset_id": "osm_building_levels_bengaluru",
            "source": "OpenStreetMap via Overpass API",
            "endpoint": OVERPASS_ENDPOINTS[0],
            "licence": "ODbL - (c) OpenStreetMap contributors",
            "label_field": "building:levels",
            "label_type": "crowd-sourced structured tag (Tier-2) - NOT municipal legal approval",
            "train_bbox_swne": list(TRAIN_BBOX),
            "demo_aoi_bbox_excluded": list(aoi),
            "raw_ways": len(els),
            "usable_labels": len(rows),
            "floor_distribution": {str(k): v for k, v in sorted(dist.items())},
            "cleaning": [
                "building:levels must parse to an integer in [1, 60]",
                ">= 4 geometry vertices, area >= 8 m^2",
                ("buildings whose centroid falls inside the demo AOI are dropped "
                 "(kept as an independent evaluation set)"),
            ],
            "features_derived": ["area_m2", "perimeter_m", "compactness (Polsby-Popper)",
                                 "rectangularity", "elongation", "long_side_m", "short_side_m",
                                 "n_vertices", "building_type bucket", "has_name",
                                 "height_tag (OSM, where present)"],
            "geometry_projection": "local equirectangular (metres); adequate for shape features",
            "retrieved_utc": datetime.now(timezone.utc).isoformat(),
            "local_path": OUT_CSV,
            "known_limitations": [
                "crowd-sourced: some tags are wrong or approximate",
                "coverage biased toward mapped / named / larger buildings",
                "no interior architectural data",
            ],
        }, fh, indent=2)
    print(f"  wrote {MANIFEST}")


if __name__ == "__main__":
    main()
