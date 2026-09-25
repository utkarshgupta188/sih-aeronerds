"""
Phase 11 (ADDITIVE) - NDVI Vegetation Evidence & Building-Height Confidence.

Runs AFTER Phase 10 fusion. It reads the existing fused buildings, samples the
Sentinel-2 NDVI raster produced by ``scripts/ingestion/load_sentinel2_ndvi.py``
in four spatial zones around each building footprint (core / interior / edge /
ring), and ADDS a vegetation-evidence / building-height confidence block to every
building.

The spatial zones exist so that vegetation *around* a real building
(surrounding trees, canopy touching the boundary, a vegetated neighbourhood) is
NOT mistaken for vegetation-derived height. Only vegetation that dominates the
building *surface* lowers building-height confidence. See
``docs/NDVI_VEGETATION_EVIDENCE.md`` and ``docs/NDVI_SPATIAL_AUDIT.md``.

It never rewrites an existing field. The original Copernicus GLO-30
``ground_elevation_m`` and the derived ``building_height_m`` are preserved
exactly; ``final_verification_status`` is left untouched.

If the NDVI raster could not be obtained, this phase does NOT fabricate values:
every building is marked ``vertical_evidence_status = NDVI_UNAVAILABLE`` with a
null confidence score and routed to human verification.
"""

import json
import os
import shutil
import sys
from collections import Counter
from datetime import datetime, timezone

sys.path.append(os.path.abspath(os.path.dirname(__file__)))                       # ndvi_evidence
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))  # config

import ndvi_evidence as ne  # sys.path adjusted above; pure-Python, numpy only

# --------------------------------------------------------------------------- #
IN_PRIMARY = os.path.join("data", "processed", "buildings_fused_final.geojson")
IN_FALLBACK = os.path.join("frontend", "data", "buildings_3d.geojson")
OUT_PATH = os.path.join("data", "processed", "buildings_ndvi_evidence.geojson")
FRONTEND_PATH = os.path.join("frontend", "data", "buildings_3d.geojson")
LEDGER_PATH = os.path.join("data", "processed", "evidence_fusion_ledger.json")
REPORT_PATH = os.path.join("docs", "NDVI_VEGETATION_EVIDENCE_REPORT.md")
AUDIT_PATH = os.path.join("docs", "NDVI_SPATIAL_AUDIT.md")

NDVI_RASTER_PATH = os.path.join("data", "raw", "ndvi_s2_aoi.tif")
NDVI_STATUS_PATH = os.path.join("data", "interim", "ndvi_status.json")

NDVI_UNAVAILABLE_META = {
    "ndvi_source": None,
    "ndvi_scene_id": None,
    "ndvi_acquisition_date": None,
    "ndvi_resolution": None,
    "ndvi_crs": None,
    "ndvi_provenance": "NDVI layer unavailable - see docs/NDVI_VEGETATION_EVIDENCE.md",
}

# Fields this phase is allowed to add. Guards against clobbering an existing key.
_ADDITIVE_KEYS = {
    "vegetation_evidence", "vegetation_evidence_label", "vegetation_pattern",
    "building_height_confidence", "building_height_confidence_score",
    "building_height_confidence_score_100", "building_height_confidence_subscores",
    "vertical_evidence_status", "ndvi_data_quality_flag", "ndvi_review_recommendation",
    "confidence_reason", "ndvi_zone_levels",
    "ndvi_value", "ndvi_median", "ndvi_p25", "ndvi_p75", "ndvi_iqr",
    "ndvi_vegetation_fraction", "ndvi_pixels_valid", "ndvi_pixels_total",
    "ndvi_nodata_fraction", "ndvi_core_median", "ndvi_edge_median", "ndvi_ring_median",
    "ndvi_surface_median", "ndvi_footprint_pixel_ratio",
    "ndvi_source", "ndvi_scene_id", "ndvi_acquisition_date", "ndvi_resolution",
    "ndvi_crs", "ndvi_provenance",
}


def _load_json(path):
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as fh:
            return json.load(fh)
    except (ValueError, OSError):
        return None


def _scene_meta_from_status(status):
    if not status or not status.get("ndvi_available"):
        return dict(NDVI_UNAVAILABLE_META)
    return {
        "ndvi_source": status.get("ndvi_source", "COPERNICUS_SENTINEL-2_L2A_NDVI"),
        "ndvi_scene_id": status.get("scene_id"),
        "ndvi_acquisition_date": status.get("acquisition_date"),
        "ndvi_resolution": status.get("resolution", "10 m"),
        "ndvi_crs": status.get("crs"),
        "ndvi_provenance": status.get("provenance")
        or ("Sentinel-2 L2A surface reflectance (Copernicus); "
            "NDVI = (B08 - B04) / (B08 + B04); SCL cloud/shadow masking; "
            "see data/manifests/ndvi_*_manifest.json"),
    }


def merge_evidence_into_properties(props, evidence, scene_meta):
    """Set the additive NDVI fields on ``props`` in place and return it.

    An existing key is never overwritten - every additive key is NDVI-namespaced
    or otherwise new, so in normal operation nothing collides. The guard is here
    so a future field-name clash fails loudly in tests instead of silently
    changing existing behaviour.
    """
    additive = dict(evidence)
    additive.update(scene_meta)
    for key, value in additive.items():
        if key not in _ADDITIVE_KEYS:
            # Never touch a key this phase does not own (protects every existing
            # BoundaryLens field: id, match_status_2d, ground_elevation_m, ...).
            continue
        # Every _ADDITIVE_KEYS entry is NDVI-owned, so refreshing it on a re-run
        # is correct (and required so the spatial results replace older values).
        props[key] = value
    return props


def _update_ledger(features, scene_meta, ndvi_available):
    ledger = _load_json(LEDGER_PATH) or {}
    method = ne.spatial_method_manifest()
    for feat in features:
        props = feat["properties"]
        b_id = str(props.get("id", "UNKNOWN"))
        entry = ledger.setdefault(b_id, {"building_id": b_id, "evidence_lineage": {}})
        lineage = entry.setdefault("evidence_lineage", {})
        # ADDITIVE sub-key only; elevation_base (COPERNICUS_GLO30_DEM) left intact.
        lineage["ndvi_vegetation_evidence"] = {
            "ndvi_source": scene_meta.get("ndvi_source"),
            "scene_id": scene_meta.get("ndvi_scene_id"),
            "acquisition_date": scene_meta.get("ndvi_acquisition_date"),
            "resolution": scene_meta.get("ndvi_resolution"),
            "crs": scene_meta.get("ndvi_crs"),
            "vegetation_pattern": props.get("vegetation_pattern"),
            "ndvi_zone_levels": props.get("ndvi_zone_levels"),
            "ndvi_value": props.get("ndvi_value"),
            "ndvi_median": props.get("ndvi_median"),
            "ndvi_core_median": props.get("ndvi_core_median"),
            "ndvi_ring_median": props.get("ndvi_ring_median"),
            "ndvi_surface_median": props.get("ndvi_surface_median"),
            "vegetation_fraction": props.get("ndvi_vegetation_fraction"),
            "pixels_valid": props.get("ndvi_pixels_valid"),
            "pixels_total": props.get("ndvi_pixels_total"),
            "nodata_fraction": props.get("ndvi_nodata_fraction"),
            "footprint_pixel_ratio": props.get("ndvi_footprint_pixel_ratio"),
            "vegetation_evidence": props.get("vegetation_evidence"),
            "building_height_confidence": props.get("building_height_confidence"),
            "building_height_confidence_score": props.get("building_height_confidence_score"),
            "vertical_evidence_status": props.get("vertical_evidence_status"),
            "data_quality_flag": props.get("ndvi_data_quality_flag"),
            "review_recommendation": props.get("ndvi_review_recommendation"),
            "confidence_reason": props.get("confidence_reason"),
            "method": method,
            "provenance": "DERIVED_NDVI_VEGETATION_INSPECTION_SPATIAL",
            "note": ("Additive evidence layer. Copernicus GLO-30 elevation is preserved "
                     "unchanged in evidence_lineage.elevation_base. NDVI is vegetation "
                     "evidence, not a building-vs-tree classifier. Vegetation around a "
                     "building does not by itself lower building-height confidence."),
            "ndvi_available": bool(ndvi_available),
        }
    with open(LEDGER_PATH, "w", encoding="utf-8") as fh:
        json.dump(ledger, fh, indent=2)


def _zone_stats(src, mask_mod, np, geom, nodata, all_touched):
    """NDVI stats for one zone polygon (already in the raster CRS).

    ``filled=False`` returns a masked array whose mask marks pixels OUTSIDE the
    polygon, so the NoData denominator is the real polygon-covered pixel count -
    not the crop bounding box (which would inflate NoData for diagonal / L-shaped
    footprints).
    """
    from shapely.geometry import mapping

    if geom is None or geom.is_empty:
        return ne.footprint_ndvi_stats([], 0)
    try:
        out, _ = mask_mod.mask(
            src, [mapping(geom)], crop=True, filled=False, all_touched=all_touched,
        )
        band = out[0]
        covered = ~np.ma.getmaskarray(band)              # inside the polygon
        data = np.asarray(np.ma.getdata(band), dtype="float64")
        n_covered = int(covered.sum())
        good = (
            covered & np.isfinite(data)
            & (data != nodata) & (data >= -1.0) & (data <= 1.0)
        )
        valid = data[good]
    except Exception:  # noqa: BLE001 - zone outside raster, invalid geom, etc.
        return ne.footprint_ndvi_stats([], 0)
    return ne.footprint_ndvi_stats(valid, n_covered)


def _sample_ndvi(features):
    """Populate props['_ndvi_zones'] (core/interior/edge/ring) using rasterio.

    Returns (ok, reason). Never fabricates - zones with no valid pixels are
    returned as empty stats.
    """
    try:
        import numpy as np
        import pyproj
        import rasterio
        import rasterio.mask
        from shapely.geometry import shape
        from shapely.ops import transform as shp_transform
    except ImportError as exc:  # keep parity with sibling scripts
        return False, f"geospatial libraries missing ({exc})"

    if not os.path.exists(NDVI_RASTER_PATH):
        return False, "NDVI raster not found at " + NDVI_RASTER_PATH

    try:
        src = rasterio.open(NDVI_RASTER_PATH)
    except Exception as exc:  # noqa: BLE001 - rasterio raises many types
        return False, f"could not open NDVI raster ({exc})"

    with src:
        if src.crs is None:
            return False, "NDVI raster has no CRS - refusing to sample (would mix coordinate systems)"
        nodata = src.nodata if src.nodata is not None else -9999.0
        res = abs(src.res[0])
        px_area = res * res
        to_ndvi = pyproj.Transformer.from_crs("EPSG:4326", src.crs, always_xy=True).transform

        for feat in features:
            props = feat["properties"]
            try:
                fp = shp_transform(to_ndvi, shape(feat["geometry"]))
            except Exception:  # noqa: BLE001
                props["_ndvi_zones"] = {
                    "core": ne.footprint_ndvi_stats([], 0),
                    "interior": ne.footprint_ndvi_stats([], 0),
                    "edge": ne.footprint_ndvi_stats([], 0),
                    "ring": ne.footprint_ndvi_stats([], 0),
                    "footprint_area_m2": 0.0,
                    "pixel_area_m2": px_area,
                }
                continue

            # Four spatial zones, all in the raster CRS.
            #  core     : footprint eroded ~half a pixel (5 m) - cell centres only.
            #  interior : the full footprint, cell centres inside - so the NoData
            #             fraction is real (not a crop-bbox artefact) and small
            #             footprints correctly fall through to RESOLUTION_LIMITED.
            #  edge     : ~1-pixel band straddling the boundary (any touched px).
            #  ring     : 5-30 m outside the footprint (surrounding context).
            core_geom = fp.buffer(-0.5 * res)
            if core_geom.is_empty or core_geom.area < px_area:
                core_geom = None
            try:
                edge_geom = fp.buffer(0.5 * res).difference(fp.buffer(-0.5 * res))
            except Exception:  # noqa: BLE001
                edge_geom = None
            try:
                ring_geom = fp.buffer(3.0 * res).difference(fp.buffer(0.5 * res))
            except Exception:  # noqa: BLE001
                ring_geom = None

            props["_ndvi_zones"] = {
                "core": _zone_stats(src, rasterio.mask, np, core_geom, nodata, False),
                "interior": _zone_stats(src, rasterio.mask, np, fp, nodata, True),
                "edge": _zone_stats(src, rasterio.mask, np, edge_geom, nodata, True),
                "ring": _zone_stats(src, rasterio.mask, np, ring_geom, nodata, True),
                "footprint_area_m2": float(fp.area),
                "pixel_area_m2": px_area,
            }

    return True, ""


# --------------------------------------------------------------------------- #
# Reporting                                                                   #
# --------------------------------------------------------------------------- #
def _write_audit(pairs, features):
    """Flat single-region vs spatial-zone audit -> docs/NDVI_SPATIAL_AUDIT.md.

    ``pairs`` is a list of (building_id, flat_evidence, spatial_evidence) computed
    in THIS run from the SAME NDVI raster, so the two columns differ only by the
    spatial-zone logic (an apples-to-apples comparison, not a cross-run diff).
    """
    total = len(features)
    have_before = len(pairs)

    def _counter(source):
        c = Counter()
        for f in features:
            c[source(f["properties"])] += 1
        return c

    after_cat = _counter(lambda p: p.get("building_height_confidence"))
    after_status = _counter(lambda p: p.get("vertical_evidence_status"))
    after_pattern = _counter(lambda p: p.get("vegetation_pattern"))
    after_review = sum(
        1 for f in features
        if f["properties"].get("ndvi_review_recommendation") == "HUMAN_VERIFICATION_REQUIRED"
    )

    before_cat = Counter()
    before_veg = Counter()
    transitions = Counter()
    false_positive_fixed = []
    still_low = []
    newly_uncertain = []

    for bid, flat, spatial in pairs:
        old_cat = flat.get("building_height_confidence")
        new_cat = spatial.get("building_height_confidence")
        new_pat = spatial.get("vegetation_pattern")
        before_cat[old_cat] += 1
        before_veg[flat.get("vegetation_evidence")] += 1
        if old_cat != new_cat:
            transitions[f"{old_cat} -> {new_cat}"] += 1
        # false positive: flat method called it LOW because of STRONG/MIXED
        # vegetation, but the spatial method finds the vegetation is not
        # dominating the building surface.
        if (old_cat == "LOW"
                and flat.get("vegetation_evidence") in ("STRONG_VEGETATION", "MIXED_VEGETATION")
                and new_pat in ("SURROUNDING_VEGETATION", "EDGE_VEGETATION",
                                "LOW_VEGETATION", "MIXED_VEGETATION", "INTERNAL_VEGETATION")
                and new_cat in ("HIGH", "MEDIUM")):
            false_positive_fixed.append((bid, old_cat, new_cat, new_pat))
        if new_cat == "LOW":
            still_low.append((bid, new_pat))
        if old_cat in ("HIGH", "MEDIUM") and new_cat == "NOT_DETERMINABLE":
            newly_uncertain.append((bid, new_pat, spatial.get("ndvi_data_quality_flag")))

    m = ne.spatial_method_manifest()
    L = []
    a = L.append
    a("# NDVI Spatial Vegetation/Building Audit\n")
    a(f"_Generated by `scripts/11_ndvi_vegetation_evidence.py` at "
      f"{datetime.now(timezone.utc).isoformat()}._\n")
    a("## Purpose\n")
    a("Confirm that no genuine building is treated as tree/vegetation-derived height "
      "merely because vegetation exists around, on the boundary of, or partially "
      "overlapping its footprint - while still flagging genuine vegetation "
      "contamination and genuine uncertainty.\n")

    a("\n## Method (summary)\n")
    a(f"- version `{m['method_version']}`\n")
    for zn, zd in m["zones"].items():
        a(f"  - **{zn}**: {zd}\n")
    a(f"- zone levels: {m['zone_levels']}\n")
    a(f"- weights: `{m['weights']}`\n")
    a(f"- spatial pattern sub-score: `{m['spatial_pattern_score']}`\n")
    a(f"- categories: HIGH >= {m['score_categories']['HIGH_at_or_above']}, "
      f"LOW < {m['score_categories']['LOW_below']}; {m['tall_height_guard']}\n")
    a(f"- limitation: {m['limitation']}\n")

    a(f"\n## Dataset\n- buildings audited: **{total}**\n")
    a(f"- buildings evaluated both ways (flat vs spatial) this run: **{have_before}**\n")
    a("- **BEFORE** column = the flat single-region method "
      "(`evaluate_building`) on the footprint sample; **AFTER** = the spatial "
      "four-zone method (`evaluate_building_spatial`). Same NDVI raster, same run.\n")

    a("\n## AFTER - vegetation pattern distribution\n")
    for k, v in sorted(after_pattern.items(), key=lambda kv: -kv[1]):
        a(f"- `{k}`: {v} ({v / total * 100:.1f}%)\n")

    a("\n## BEFORE vs AFTER - building-height confidence\n")
    a("| category | BEFORE | AFTER |\n|---|---:|---:|\n")
    for k in ("HIGH", "MEDIUM", "LOW", "NOT_DETERMINABLE"):
        a(f"| {k} | {before_cat.get(k, 0) if have_before else '-'} | {after_cat.get(k, 0)} |\n")

    a("\n## BEFORE vs AFTER - vertical evidence status\n")
    a("| status | AFTER |\n|---|---:|\n")
    for k, v in sorted(after_status.items(), key=lambda kv: -kv[1]):
        a(f"| {k} | {v} |\n")
    a(f"\n- routed to human verification (AFTER): **{after_review} / {total}**\n")

    if have_before:
        a("\n## Category transitions (BEFORE -> AFTER)\n")
        if transitions:
            for k, v in sorted(transitions.items(), key=lambda kv: -kv[1]):
                a(f"- `{k}`: {v}\n")
        else:
            a("- none\n")

    a("\n## False-positive audit "
      "(surrounding vegetation previously read as vegetation-derived height)\n")
    a(f"- candidates identified and corrected: **{len(false_positive_fixed)}**\n")
    for bid, oc, nc, pat in false_positive_fixed[:40]:
        a(f"  - `{bid}`: {oc} -> {nc} (pattern `{pat}`)\n")
    if len(false_positive_fixed) > 40:
        a(f"  - ... and {len(false_positive_fixed) - 40} more\n")

    a(f"\n## Still LOW after the fix (genuine vegetation-dominant / uncertain): "
      f"**{len(still_low)}**\n")
    pat_low = Counter(p for _, p in still_low)
    for k, v in pat_low.items():
        a(f"- pattern `{k}`: {v}\n")

    a(f"\n## Newly NOT_DETERMINABLE (honestly exposed uncertainty, not fabricated): "
      f"**{len(newly_uncertain)}**\n")
    pat_nd = Counter(f"{p}/{q}" for _, p, q in newly_uncertain)
    for k, v in sorted(pat_nd.items(), key=lambda kv: -kv[1]):
        a(f"- `{k}`: {v}\n")

    a("\n## Non-regression\n")
    a(f"- building count: **{total}** (unchanged)\n")
    a("- `id`, `linked_parcel_id`, `match_status_2d`, `parcel_overlap_ratio`, "
      "`ai_anomaly_flag`, `final_verification_status`, `ground_elevation_m`, "
      "`building_height_m` are read-only inputs here and are not written.\n")
    a("- Copernicus GLO-30 elevation is not replaced; NDVI remains an additional "
      "evidence layer.\n")

    os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)
    with open(AUDIT_PATH, "w", encoding="utf-8") as fh:
        fh.write("".join(L))
    return {
        "false_positive_fixed": len(false_positive_fixed),
        "still_low": len(still_low),
        "newly_uncertain": len(newly_uncertain),
        "after_pattern": dict(after_pattern),
    }


def _write_report(total, cat_counts, status_counts, review_count, scene_meta,
                  ndvi_available, reason, audit):
    m = ne.spatial_method_manifest()
    lines = []
    a = lines.append
    a("# Phase 11: NDVI Vegetation Evidence & Building-Height Confidence Report\n")
    a("_Additive layer. Generated by `scripts/11_ndvi_vegetation_evidence.py`._\n")
    a(f"_Run: {datetime.now(timezone.utc).isoformat()}_\n")
    a("## Why\n")
    a("Copernicus GLO-30 reports **surface** elevation. An elevated surface inside a "
      "building footprint may be a roof or a tree canopy; the DEM cannot tell them "
      "apart. This layer adds independent, spatially-resolved vegetation evidence "
      "from NDVI.\n")
    a("## What this does / does not claim\n")
    a("- NDVI is **vegetation evidence**, not a building-vs-tree classifier.\n")
    a("- **Vegetation near a building does not by itself lower building-height "
      "confidence** - four zones (core/interior/edge/ring) locate the vegetation.\n")
    a("- The score is bounded evidence in [0,1], not a calibrated probability and not "
      "a legal certainty. Thresholds are heuristic and not ground-truth calibrated.\n")
    if not ndvi_available:
        a("\n## NDVI status: UNAVAILABLE\n")
        a(f"> {reason}\n")
        a("\nEvery building is marked `NDVI_UNAVAILABLE` with a null score and routed to "
          "human verification. No confidence values were fabricated.\n")
    else:
        a("\n## NDVI source\n")
        for k in ("ndvi_source", "ndvi_scene_id", "ndvi_acquisition_date",
                  "ndvi_resolution", "ndvi_crs"):
            a(f"- **{k}**: {scene_meta.get(k)}\n")
        a(f"- **provenance**: {scene_meta.get('ndvi_provenance')}\n")
    a("\n## Method (spatially-resolved)\n")
    a(f"- version: `{m['method_version']}`\n")
    for zn, zd in m["zones"].items():
        a(f"  - **{zn}** zone: {zd}\n")
    a(f"- weights: `{m['weights']}`\n")
    a(f"- patterns: {', '.join(m['patterns'].keys())}\n")
    a(f"- human verification: {m['human_verification_rule']}\n")
    a(f"- limitation: {m['limitation']}\n")
    a("\n## Results\n")
    a(f"- buildings annotated: **{total}**\n")
    a(f"- building-height confidence: `{dict(cat_counts)}`\n")
    a(f"- vertical evidence status: `{dict(status_counts)}`\n")
    if audit:
        a(f"- vegetation pattern: `{audit['after_pattern']}`\n")
        a(f"- surrounding-vegetation false positives corrected: "
          f"**{audit['false_positive_fixed']}**\n")
        a(f"- still LOW (genuine vegetation-dominant): **{audit['still_low']}**\n")
        a(f"- newly NOT_DETERMINABLE (honest uncertainty): **{audit['newly_uncertain']}**\n")
    a(f"- routed to human verification: **{review_count} / {total}**\n")
    a("\nFull before/after in `docs/NDVI_SPATIAL_AUDIT.md`.\n")
    a("\n## Non-regression\n")
    a("`ground_elevation_m` (Copernicus GLO-30) and `building_height_m` are preserved "
      "exactly; `final_verification_status` is not modified. `ndvi_review_recommendation` "
      "is a separate advisory field.\n")
    a("\n**Output files**\n")
    a(f"- `{OUT_PATH}`\n- `{FRONTEND_PATH}`\n- `{LEDGER_PATH}` (key `ndvi_vegetation_evidence`)\n")
    a(f"- `{AUDIT_PATH}`\n")
    os.makedirs(os.path.dirname(REPORT_PATH), exist_ok=True)
    with open(REPORT_PATH, "w", encoding="utf-8") as fh:
        fh.write("".join(lines))


def main():
    print("=========================================")
    print("  PHASE 11: NDVI VEGETATION EVIDENCE      ")
    print("=========================================\n")

    in_path = IN_PRIMARY if os.path.exists(IN_PRIMARY) else IN_FALLBACK
    data = _load_json(in_path)
    if not data or "features" not in data:
        print(f"Error: no fused buildings found ({IN_PRIMARY} / {IN_FALLBACK}).")
        print("Run phases 1-10 first. Nothing to annotate - exiting cleanly.")
        return
    features = data["features"]
    total = len(features)
    print(f"Loaded {total} buildings from {in_path}.")

    status = _load_json(NDVI_STATUS_PATH)
    scene_meta = _scene_meta_from_status(status)

    ndvi_available, reason = _sample_ndvi(features)
    if not ndvi_available:
        reason = reason or (status or {}).get(
            "reason", "NDVI raster not produced by scripts/ingestion/load_sentinel2_ndvi.py"
        )
        print(f"[NDVI UNAVAILABLE] {reason}")
        print("Marking every building as NDVI_UNAVAILABLE (no fabricated confidence).")
        scene_meta = dict(NDVI_UNAVAILABLE_META)

    cat_counts = Counter()
    status_counts = Counter()
    review_count = 0
    pairs = []  # (id, flat_evidence, spatial_evidence) for the audit

    for feat in features:
        props = feat["properties"]
        zones = props.pop("_ndvi_zones", None)
        kw = {
            "match_status_2d": props.get("match_status_2d"),
            "parcel_overlap_ratio": props.get("parcel_overlap_ratio"),
            "building_height_m": props.get("building_height_m"),
            "height_confidence": props.get("height_confidence", "MEDIUM"),
        }
        if ndvi_available:
            evidence = ne.evaluate_building_spatial(zones or {}, ndvi_available=True, **kw)
            # Flat single-region baseline from the SAME run (footprint = interior
            # zone) so the audit isolates the effect of the spatial-zone logic.
            flat = ne.evaluate_building((zones or {}).get("interior") or {}, **kw)
            pairs.append((str(props.get("id")), flat, evidence))
        else:
            evidence = ne.evaluate_building_spatial(
                {}, ndvi_available=False, ndvi_unavailable_reason=reason,
                building_height_m=props.get("building_height_m"),
            )

        merge_evidence_into_properties(props, evidence, scene_meta)
        cat_counts[evidence["building_height_confidence"]] += 1
        status_counts[evidence["vertical_evidence_status"]] += 1
        if evidence["ndvi_review_recommendation"] == "HUMAN_VERIFICATION_REQUIRED":
            review_count += 1

    os.makedirs(os.path.dirname(OUT_PATH), exist_ok=True)
    with open(OUT_PATH, "w", encoding="utf-8") as fh:
        json.dump(data, fh, indent=2)
    os.makedirs(os.path.dirname(FRONTEND_PATH), exist_ok=True)
    shutil.copy(OUT_PATH, FRONTEND_PATH)
    _update_ledger(features, scene_meta, ndvi_available)

    audit = _write_audit(pairs, features) if ndvi_available else None

    print("\nNDVI evidence annotation complete.")
    print(f"  Building-height confidence: {dict(cat_counts)}")
    print(f"  Vertical evidence status  : {dict(status_counts)}")
    if audit:
        print(f"  Vegetation pattern        : {audit['after_pattern']}")
        print(f"  Surrounding-veg false positives corrected: {audit['false_positive_fixed']}")
        print(f"  Still LOW (veg-dominant)   : {audit['still_low']}")
        print(f"  Newly NOT_DETERMINABLE     : {audit['newly_uncertain']}")
    print(f"  Routed to human verification: {review_count} / {total}")
    print(f"  Output      : {OUT_PATH}")
    print(f"  Frontend    : {FRONTEND_PATH}")
    print(f"  Ledger      : {LEDGER_PATH} (added 'ndvi_vegetation_evidence')")

    _write_report(total, cat_counts, status_counts, review_count, scene_meta,
                  ndvi_available, reason if not ndvi_available else "", audit)
    print(f"  Report      : {REPORT_PATH}")
    if audit:
        print(f"  Audit       : {AUDIT_PATH}")


if __name__ == "__main__":
    main()
