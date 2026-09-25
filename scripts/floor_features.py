"""
Shared geometry feature extraction for the floor-count model.

Pure-Python (math only). The SAME function is used to build the OSM training
labels, evaluate on held-out buildings, and score the AOI buildings in Phase 12,
so features are identical everywhere.
"""

from __future__ import annotations

import math

FEATURE_COLUMNS = [
    "area_m2", "perimeter_m", "compactness", "rectangularity", "elongation",
    "long_side_m", "short_side_m", "n_vertices", "has_name",
    "height_tag_m", "has_height_tag",
    "dsm_height_m", "has_dsm_height",
    "type_residential", "type_commercial", "type_civic", "type_industrial", "type_other",
]


def dsm_height_at(dsm_src, lon, lat, np=None):
    """Coarse above-ground height from a Copernicus GLO-30 DSM window around a
    point: max in a ~90 m box minus the 10th percentile in a ~390 m ring (local
    ground proxy). Returns metres or None. 30 m / ~4 m LE90 - a bulk signal only.
    """
    if dsm_src is None:
        return None
    if np is None:
        import numpy as np
    try:
        row, col = dsm_src.index(lon, lat)
    except Exception:  # noqa: BLE001
        return None
    h_px, w_px = dsm_src.height, dsm_src.width
    nd = dsm_src.nodata if dsm_src.nodata is not None else -1e30

    def _win(rad):
        r0, r1 = max(0, row - rad), min(h_px, row + rad + 1)
        c0, c1 = max(0, col - rad), min(w_px, col + rad + 1)
        if r1 <= r0 or c1 <= c0:
            return None
        a = dsm_src.read(1, window=((r0, r1), (c0, c1))).astype("float64")
        a = a[np.isfinite(a) & (a != nd)]
        return a if a.size else None

    near = _win(1)   # ~3x3 px  (footprint + immediate surrounds -> roof/top)
    ring = _win(6)   # ~13x13 px (local ground)
    if near is None or ring is None or ring.size < 5:
        return None
    h = float(np.max(near) - np.percentile(ring, 10))
    if not np.isfinite(h) or h < -3 or h > 400:
        return None
    return max(0.0, h)

_RESIDENTIAL = {"residential", "apartments", "house", "detached", "terrace",
                "semidetached_house", "dormitory", "bungalow", "hut"}
_COMMERCIAL = {"commercial", "retail", "office", "supermarket", "hotel", "kiosk", "shop", "mall"}
_CIVIC = {"school", "college", "university", "hospital", "government", "civic", "public",
          "church", "temple", "mosque", "place_of_worship", "hall"}
_INDUSTRIAL = {"industrial", "warehouse", "factory", "manufacture"}


def type_bucket(building_type, tags=None):
    b = str(building_type or "yes").lower()
    tags = tags or {}
    if b in _RESIDENTIAL:
        return "residential"
    if b in _COMMERCIAL or tags.get("shop") or tags.get("office"):
        return "commercial"
    if b in _CIVIC or tags.get("amenity") in {"school", "college", "hospital", "place_of_worship"}:
        return "civic"
    if b in _INDUSTRIAL:
        return "industrial"
    return "other"


def _equirect_ring(lonlat_ring):
    """[[lon,lat],...] -> [(x_m,y_m),...] via local equirectangular projection."""
    pts = [p for p in lonlat_ring if p is not None and len(p) >= 2]
    if len(pts) >= 2 and pts[0] == pts[-1]:
        pts = pts[:-1]
    if len(pts) < 3:
        return None
    lat0 = sum(p[1] for p in pts) / len(pts)
    k = math.cos(math.radians(lat0))
    return [(p[0] * 111320.0 * k, p[1] * 110540.0) for p in pts]


def _area_perim(ring):
    a = p = 0.0
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        a += x1 * y2 - x2 * y1
        p += math.hypot(x2 - x1, y2 - y1)
    return abs(a) / 2.0, p


def _min_rect_dims(ring):
    best = None
    n = len(ring)
    for i in range(n):
        x1, y1 = ring[i]
        x2, y2 = ring[(i + 1) % n]
        ang = math.atan2(y2 - y1, x2 - x1)
        ca, sa = math.cos(-ang), math.sin(-ang)
        xs = [px * ca - py * sa for px, py in ring]
        ys = [px * sa + py * ca for px, py in ring]
        w, h = max(xs) - min(xs), max(ys) - min(ys)
        area = w * h
        if best is None or area < best[0]:
            best = (area, max(w, h), min(w, h))
    return best[1], best[2]


def geom_features(lonlat_ring, *, building_type=None, has_name=False,
                  height_tag_m=None, dsm_height_m=None, tags=None):
    """Return a feature dict (FEATURE_COLUMNS) or None if the footprint is unusable."""
    ring = _equirect_ring(lonlat_ring)
    if ring is None:
        return None
    area, perim = _area_perim(ring)
    if area < 8 or perim <= 0:
        return None
    long_s, short_s = _min_rect_dims(ring)
    rect_area = max(long_s * short_s, 1e-6)
    tb = type_bucket(building_type, tags)
    ht = None
    try:
        ht = float(height_tag_m) if height_tag_m not in (None, "", "None") else None
        if ht is not None and (not math.isfinite(ht) or ht <= 0 or ht > 400):
            ht = None
    except (TypeError, ValueError):
        ht = None
    dh = None
    try:
        dh = float(dsm_height_m) if dsm_height_m not in (None, "", "None") else None
        if dh is not None and (not math.isfinite(dh) or dh < 0 or dh > 400):
            dh = None
    except (TypeError, ValueError):
        dh = None
    return {
        "area_m2": round(area, 2),
        "perimeter_m": round(perim, 2),
        "compactness": round(4 * math.pi * area / (perim * perim), 5),
        "rectangularity": round(min(area / rect_area, 1.0), 5),
        "elongation": round(short_s / long_s, 5) if long_s else 0.0,
        "long_side_m": round(long_s, 2),
        "short_side_m": round(short_s, 2),
        "n_vertices": max(3, len(ring)),
        "has_name": 1 if has_name else 0,
        "height_tag_m": round(ht, 2) if ht is not None else 0.0,
        "has_height_tag": 1 if ht is not None else 0,
        "dsm_height_m": round(dh, 2) if dh is not None else 0.0,
        "has_dsm_height": 1 if dh is not None else 0,
        "type_residential": 1 if tb == "residential" else 0,
        "type_commercial": 1 if tb == "commercial" else 0,
        "type_civic": 1 if tb == "civic" else 0,
        "type_industrial": 1 if tb == "industrial" else 0,
        "type_other": 1 if tb == "other" else 0,
    }


def features_from_geojson_polygon(geometry, props, dsm_src=None):
    """Feature dict for a BoundaryLens building feature (EPSG:4326 Polygon).

    If ``dsm_src`` (an open rasterio GLO-30 dataset) is given, a coarse
    above-ground DSM height feature is added.
    """
    if not geometry or geometry.get("type") not in ("Polygon", "MultiPolygon"):
        return None
    if geometry["type"] == "Polygon":
        ring = geometry["coordinates"][0]
    else:  # take the largest ring
        rings = [poly[0] for poly in geometry["coordinates"]]
        ring = max(rings, key=len)
    ht = props.get("height_m")  # real OSM height tag if present (NOT the Google bucket)
    dh = None
    if dsm_src is not None and ring:
        lon = sum(p[0] for p in ring) / len(ring)
        lat = sum(p[1] for p in ring) / len(ring)
        dh = dsm_height_at(dsm_src, lon, lat)
    return geom_features(
        ring,
        building_type=props.get("building_type"),
        has_name=bool(props.get("name")),
        height_tag_m=ht,
        dsm_height_m=dh,
    )
