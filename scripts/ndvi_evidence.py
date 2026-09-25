"""
BoundaryLens - NDVI Vegetation Evidence & Building-Height Confidence core.

ADDITIVE evidence layer. Pure-Python (numpy only): no rasterio / network imports
here, so every scoring decision is deterministic and unit-testable.

PRINCIPLE (see docs/NDVI_VEGETATION_EVIDENCE.md)
-----------------------------------------------
Copernicus GLO-30 gives *surface* elevation. It does not tell us whether an
elevated surface is a roof or a tree canopy. NDVI is introduced here as an
*independent vegetation-evidence layer* that raises or lowers confidence that the
observed surface elevation / derived building height represents the building
rather than vegetation.

This module DOES NOT classify "building vs tree". The number it produces is an
evidence/confidence score, NOT a calibrated probability of correctness and NOT a
legal certainty. Thresholds below are heuristic and are NOT calibrated against
labelled ground truth for this AOI.
"""

from __future__ import annotations

import numpy as np

METHOD_VERSION = "boundarylens-ndvi-evidence/v1"

# --------------------------------------------------------------------------- #
# Heuristic NDVI thresholds (tunable; NOT validated against ground truth).    #
# Rationale: on Sentinel-2 surface reflectance, dense green canopy / grass    #
# typically returns NDVI >= ~0.4, while dry impervious surfaces, rooftops and #
# bare soil in the Bengaluru AOI sit well below ~0.2-0.3. We therefore treat  #
# 0.40 as "this pixel shows a clear vegetation response" (NOT "this is a      #
# tree") and 0.20 as "vegetation contribution is negligible".                 #
# --------------------------------------------------------------------------- #
NDVI_BARE_THRESHOLD = 0.20
NDVI_VEG_THRESHOLD = 0.40
IQR_REFERENCE = 0.40  # NDVI inter-quartile range treated as a fully mixed surface

# "Vegetation dominates the whole footprint" (-> VEGETATION_DOMINANT / LOW) is a
# strong claim - it says the Copernicus surface elevation here is more likely
# canopy than a roof. It must be judged on the FULL footprint, never on the thin
# eroded core band alone (which clips overhanging trees on narrow / L-shaped
# buildings). Require: the footprint interior itself reads HIGH, most of it is
# vegetated, and its median NDVI is clearly vegetative - not just barely over
# the 0.40 "vegetation present" line.
NDVI_DOMINANT_MEDIAN = 0.45
DOMINANT_VEG_FRACTION = 0.80

# Data-quality gates.
MIN_VALID_PIXELS = 3
NODATA_FRACTION_MAX = 0.60          # above this -> NOT_DETERMINABLE
NODATA_FRACTION_OK = 0.20           # at/below this -> data_quality_flag OK

# Plausibility guard on the *derived* height (metres). This never changes the
# stored height; it only weakens the elevation sub-score when the value is
# physically implausible for this urban AOI (possible vegetation contamination).
HEIGHT_PLAUSIBLE_MIN = 3.0
HEIGHT_PLAUSIBLE_MAX = 120.0
HEIGHT_TALL_FLAG = 60.0            # "unusually tall": cannot be HIGH unless veg is clearly LOW

# Weighted linear combination of sub-scores (each in [0, 1]); weights sum to 1.
WEIGHTS = {
    "ndvi": 0.40,        # vegetation evidence (robust footprint NDVI)
    "footprint": 0.15,   # existing 2D building-footprint / parcel match evidence
    "elevation": 0.15,   # existing elevation / height evidence plausibility
    "quality": 0.20,     # NDVI data quality (valid vs NoData inside footprint)
    "consistency": 0.10,  # spatial consistency of NDVI within the footprint
}

# Category thresholds on the 0..1 evidence score.
SCORE_HIGH = 0.70
SCORE_LOW = 0.40

_VEG_LABELS = {
    "LOW_VEGETATION": "Low vegetation",
    "MIXED_VEGETATION": "Mixed vegetation",
    "STRONG_VEGETATION": "Strong vegetation",
    "NOT_DETERMINABLE": "Not determinable",
    "NOT_COMPUTED": "Not available",
    # spatial patterns (see evaluate_building_spatial)
    "SURROUNDING_VEGETATION": "Surrounding vegetation",
    "EDGE_VEGETATION": "Edge vegetation",
    "INTERNAL_VEGETATION": "Internal vegetation",
    "VEGETATION_DOMINANT": "Vegetation dominant within footprint",
    "RESOLUTION_LIMITED": "Resolution limited",
    "NODATA": "No valid NDVI data",
}

# --------------------------------------------------------------------------- #
# Spatially-resolved evaluation (evaluate_building_spatial) - ADDITIVE.       #
#                                                                            #
# The flat evaluate_building() above samples one region and can mistake      #
# vegetation *around* a real building for vegetation-derived height. The      #
# spatial path instead compares four zones -                                 #
#   core      : footprint eroded ~1 pixel  (the building surface / roof)     #
#   interior  : the full footprint                                           #
#   edge      : a ~1-pixel band straddling the footprint boundary            #
#   ring      : an outer context band ~5-30 m outside the footprint          #
# - and asks WHERE the vegetation is, not merely whether it is present.      #
# Vegetation confined to the edge/ring is SURROUNDING context and must NOT   #
# by itself lower building-height confidence.                                #
# --------------------------------------------------------------------------- #
SPATIAL_WEIGHTS = {
    "ndvi_surface": 0.34,   # NDVI of the building SURFACE (core if usable, else interior)
    "spatial": 0.16,        # where the vegetation sits (pattern-derived)
    "footprint": 0.15,      # existing 2D footprint / parcel-match evidence
    "elevation": 0.15,      # existing height plausibility x height_confidence
    "quality": 0.10,        # interior NDVI data quality (valid vs NoData)
    "consistency": 0.10,    # spatial consistency of interior NDVI
}

# Contribution of each pattern to the "spatial" sub-score (in [0, 1]).
_SPATIAL_PATTERN_SCORE = {
    "LOW_VEGETATION": 1.00,
    "SURROUNDING_VEGETATION": 0.90,
    "EDGE_VEGETATION": 0.60,
    "MIXED_VEGETATION": 0.50,
    "INTERNAL_VEGETATION": 0.40,
    "VEGETATION_DOMINANT": 0.10,
}

# A zone is comparable to one 10 m pixel at ~100 m2; below this a footprint has
# no room for a reliable eroded core.
_MIN_CORE_FOOTPRINT_RATIO = 1.5  # footprint_area / pixel_area

_VERTICAL_STATUS = {
    "HIGH": "SUPPORTED",
    "MEDIUM": "PROVISIONAL",
    "LOW": "VEGETATION_POSSIBLE",
    "NOT_DETERMINABLE": "NOT_DETERMINABLE",
}

_FOOTPRINT_BASE = {
    "CONTAINED": 1.0,
    "MAJORITY": 0.70,
    "BOUNDARY_OVERLAP": 0.40,
    "CONFLICT": 0.40,
    "NO_PARCEL": 0.30,
}

_HEIGHT_CONF_FACTOR = {"HIGH": 1.0, "MEDIUM": 0.70, "LOW": 0.40}


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, float(x)))


def _is_missing_height(h) -> bool:
    return h in (None, "", "NOT_DETERMINABLE", "null")


# --------------------------------------------------------------------------- #
# Robust footprint statistics                                                 #
# --------------------------------------------------------------------------- #
def footprint_ndvi_stats(values, n_intersecting: int) -> dict:
    """Robust NDVI statistics for one building footprint.

    Parameters
    ----------
    values : iterable of float
        VALID NDVI samples (NoData / out-of-range already removed) taken from
        pixels whose cell centre falls inside the footprint (edge-eroded where
        the footprint is large enough - see script 11).
    n_intersecting : int
        Total pixels intersecting the footprint (valid + NoData). Used to make
        the NoData fraction explicit rather than silently dropping it.

    Using the median / percentiles (not a single pixel) prevents one vegetated
    edge pixel from dominating the result, and ``vegetation_fraction`` makes
    partial vegetation coverage explicit.
    """
    arr = np.asarray(list(values), dtype="float64")
    arr = arr[np.isfinite(arr)]
    arr = arr[(arr >= -1.0) & (arr <= 1.0)]
    n_valid = int(arr.size)
    n_total = int(max(n_intersecting, n_valid))
    nodata_fraction = 0.0 if n_total == 0 else 1.0 - (n_valid / n_total)

    if n_valid == 0:
        return {
            "n_total": n_total,
            "n_valid": 0,
            "nodata_fraction": 1.0,
            "ndvi_median": None,
            "ndvi_p25": None,
            "ndvi_p75": None,
            "ndvi_iqr": None,
            "vegetation_fraction": None,
        }

    p25, p50, p75 = (float(v) for v in np.percentile(arr, [25, 50, 75]))
    veg_fraction = float(np.mean(arr >= NDVI_VEG_THRESHOLD))
    return {
        "n_total": n_total,
        "n_valid": n_valid,
        "nodata_fraction": round(nodata_fraction, 4),
        "ndvi_median": round(p50, 4),
        "ndvi_p25": round(p25, 4),
        "ndvi_p75": round(p75, 4),
        "ndvi_iqr": round(p75 - p25, 4),
        "vegetation_fraction": round(veg_fraction, 4),
    }


# --------------------------------------------------------------------------- #
# Vegetation-evidence category (NOT a building classifier)                    #
# --------------------------------------------------------------------------- #
def classify_vegetation_evidence(stats: dict) -> str:
    if not stats or not stats.get("n_valid"):
        return "NOT_DETERMINABLE"
    med = stats["ndvi_median"]
    vf = stats["vegetation_fraction"]
    if med >= NDVI_VEG_THRESHOLD or vf >= 0.60:
        return "STRONG_VEGETATION"
    if med < NDVI_BARE_THRESHOLD and vf < 0.15:
        return "LOW_VEGETATION"
    return "MIXED_VEGETATION"


# --------------------------------------------------------------------------- #
# Sub-scores (each in [0, 1])                                                 #
# --------------------------------------------------------------------------- #
def _score_ndvi(stats: dict) -> float:
    """High when the footprint looks non-vegetated; low when it looks vegetated."""
    med = stats["ndvi_median"]
    vf = stats["vegetation_fraction"]
    span = NDVI_VEG_THRESHOLD - NDVI_BARE_THRESHOLD
    median_component = _clamp((NDVI_VEG_THRESHOLD - med) / span)
    coverage_component = _clamp(1.0 - vf)
    return _clamp(0.5 * median_component + 0.5 * coverage_component)


def _score_footprint(match_status_2d, parcel_overlap_ratio) -> float:
    base = _FOOTPRINT_BASE.get(str(match_status_2d).upper(), 0.30)
    if parcel_overlap_ratio is not None:
        try:
            base = 0.5 * base + 0.5 * _clamp(float(parcel_overlap_ratio))
        except (TypeError, ValueError):
            pass
    return _clamp(base)


def _score_elevation(building_height_m, height_confidence):
    """Returns (score, is_implausibly_tall)."""
    if _is_missing_height(building_height_m):
        plausibility = 0.5
        implausible_tall = False
    else:
        try:
            h = float(building_height_m)
        except (TypeError, ValueError):
            return 0.5, False
        if h < HEIGHT_PLAUSIBLE_MIN:
            plausibility = 0.5
            implausible_tall = False
        elif h <= HEIGHT_PLAUSIBLE_MAX:
            plausibility = 1.0
            implausible_tall = False
        else:
            plausibility = _clamp(
                1.0 - (h - HEIGHT_PLAUSIBLE_MAX) / HEIGHT_PLAUSIBLE_MAX, 0.2, 1.0
            )
            implausible_tall = True
    factor = _HEIGHT_CONF_FACTOR.get(str(height_confidence).upper(), 0.70)
    return _clamp(plausibility * factor), implausible_tall


def _score_quality(stats: dict) -> float:
    return _clamp(1.0 - stats.get("nodata_fraction", 0.0))


def _score_consistency(stats: dict) -> float:
    iqr = stats.get("ndvi_iqr")
    if iqr is None:
        return 0.5
    return _clamp(1.0 - iqr / IQR_REFERENCE)


# --------------------------------------------------------------------------- #
# Result assembly                                                             #
# --------------------------------------------------------------------------- #
def _result(**kw) -> dict:
    stats = kw.get("stats") or {}
    score = kw.get("score")
    return {
        "vegetation_evidence": kw["vegetation_evidence"],
        "vegetation_evidence_label": _VEG_LABELS.get(
            kw["vegetation_evidence"], kw["vegetation_evidence"]
        ),
        "building_height_confidence": kw["category"],
        "building_height_confidence_score": score,
        "building_height_confidence_score_100": (
            None if score is None else round(score * 100)
        ),
        "building_height_confidence_subscores": kw.get("subscores"),
        "vertical_evidence_status": kw["vertical_status"],
        "ndvi_data_quality_flag": kw["quality_flag"],
        "ndvi_review_recommendation": kw["review"],
        "confidence_reason": kw["reason"],
        "ndvi_value": stats.get("ndvi_median"),
        "ndvi_median": stats.get("ndvi_median"),
        "ndvi_p25": stats.get("ndvi_p25"),
        "ndvi_p75": stats.get("ndvi_p75"),
        "ndvi_iqr": stats.get("ndvi_iqr"),
        "ndvi_vegetation_fraction": stats.get("vegetation_fraction"),
        "ndvi_pixels_valid": stats.get("n_valid"),
        "ndvi_pixels_total": stats.get("n_total"),
        "ndvi_nodata_fraction": stats.get("nodata_fraction"),
    }


def _build_reason(category, stats, is_tall) -> str:
    bits = []
    med = stats.get("ndvi_median")
    vf = stats.get("vegetation_fraction")
    if med is not None:
        bits.append(f"footprint NDVI median {med:.2f}")
    if vf is not None:
        bits.append(f"{vf * 100:.0f}% of footprint pixels vegetated (NDVI>={NDVI_VEG_THRESHOLD})")
    nod = stats.get("nodata_fraction")
    if nod:
        bits.append(f"NoData fraction {nod:.2f}")
    if is_tall:
        bits.append("derived height is unusually tall for this AOI")

    if category == "HIGH":
        head = ("Little/no vegetation evidence inside the building footprint and the "
                "elevation-derived height is spatially consistent; evidence supports a built structure")
    elif category == "LOW":
        head = ("Strong vegetation evidence inside the building footprint; the Copernicus "
                "surface elevation here may be vegetation-derived rather than the building")
    elif category == "NOT_DETERMINABLE":
        head = "Insufficient valid NDVI evidence inside the footprint to judge vegetation vs building"
    else:
        head = ("Vegetation and building evidence are mixed (partial canopy overlap, limited "
                "resolution or uncertain pixels)")
    return head + ". " + "; ".join(bits) + "."


def evaluate_building(
    stats: dict,
    *,
    match_status_2d=None,
    parcel_overlap_ratio=None,
    building_height_m=None,
    height_confidence="MEDIUM",
    ndvi_available: bool = True,
    ndvi_unavailable_reason: str = "",
) -> dict:
    """Full additive evidence dict for one building.

    Never fabricates a value: when NDVI is unavailable or insufficient the score
    is ``None`` and the status makes the gap explicit.
    """
    if not ndvi_available:
        reason = (
            "NDVI vegetation layer could not be computed for this AOI"
            + (f" ({ndvi_unavailable_reason})" if ndvi_unavailable_reason else "")
            + ". Copernicus GLO-30 elevation retained unchanged; building-height "
            "confidence not derived. Vertical height evidence requires human verification."
        )
        return _result(
            vegetation_evidence="NOT_COMPUTED",
            category="NOT_DETERMINABLE",
            score=None,
            vertical_status="NDVI_UNAVAILABLE",
            quality_flag="NDVI_LAYER_UNAVAILABLE",
            review="HUMAN_VERIFICATION_REQUIRED",
            reason=reason,
            stats=stats or {},
        )

    stats = stats or {}
    n_valid = stats.get("n_valid", 0) or 0
    nodata_fraction = stats.get("nodata_fraction", 1.0)
    veg = classify_vegetation_evidence(stats)

    if n_valid < MIN_VALID_PIXELS or nodata_fraction > NODATA_FRACTION_MAX:
        return _result(
            vegetation_evidence=veg if n_valid else "NOT_DETERMINABLE",
            category="NOT_DETERMINABLE",
            score=None,
            vertical_status="NOT_DETERMINABLE",
            quality_flag="INSUFFICIENT_NDVI",
            review="HUMAN_VERIFICATION_REQUIRED",
            reason=(
                f"Insufficient valid NDVI inside the footprint (valid_pixels={n_valid}, "
                f"nodata_fraction={nodata_fraction:.2f}); vegetation-vs-building height "
                "evidence is not determinable. Human verification required."
            ),
            stats=stats,
        )

    elev_score, implausible_tall = _score_elevation(building_height_m, height_confidence)
    try:
        is_tall = implausible_tall or (
            not _is_missing_height(building_height_m)
            and float(building_height_m) > HEIGHT_TALL_FLAG
        )
    except (TypeError, ValueError):
        is_tall = implausible_tall
    subscores = {
        "ndvi": round(_score_ndvi(stats), 4),
        "footprint": round(_score_footprint(match_status_2d, parcel_overlap_ratio), 4),
        "elevation": round(elev_score, 4),
        "quality": round(_score_quality(stats), 4),
        "consistency": round(_score_consistency(stats), 4),
    }
    score = round(_clamp(sum(WEIGHTS[k] * subscores[k] for k in WEIGHTS)), 4)

    quality_flag = "OK" if nodata_fraction <= NODATA_FRACTION_OK else "PARTIAL_NODATA"

    if score >= SCORE_HIGH and veg == "LOW_VEGETATION" and quality_flag == "OK":
        category = "HIGH"
    elif veg == "STRONG_VEGETATION" or score < SCORE_LOW:
        category = "LOW"
    else:
        category = "MEDIUM"

    # "Unusually tall" derived height cannot read as HIGH unless vegetation is
    # clearly low - a tall canopy can masquerade as a tall building.
    if is_tall and category == "HIGH" and veg != "LOW_VEGETATION":
        category = "MEDIUM"

    vertical_status = _VERTICAL_STATUS[category]
    # Item 9: LOW *and* MIXED/MEDIUM vertical confidence -> human verification.
    # Only HIGH clears the gate.
    review = "NONE" if category == "HIGH" else "HUMAN_VERIFICATION_REQUIRED"

    reason = _build_reason(category, stats, is_tall)
    return _result(
        vegetation_evidence=veg,
        category=category,
        score=score,
        subscores=subscores,
        vertical_status=vertical_status,
        quality_flag=quality_flag,
        review=review,
        reason=reason,
        stats=stats,
    )


# --------------------------------------------------------------------------- #
# Spatially-resolved vegetation pattern + evaluation                          #
# --------------------------------------------------------------------------- #
def zone_veg_level(zone_stats) -> str:
    """Coarse vegetation level for one zone: LOW / MIXED / HIGH / NONE.

    NONE means the zone had no valid NDVI pixels (never fabricated).
    """
    if not zone_stats or not zone_stats.get("n_valid"):
        return "NONE"
    med = zone_stats.get("ndvi_median")
    vf = zone_stats.get("vegetation_fraction")
    if med is None:
        return "NONE"
    if med >= NDVI_VEG_THRESHOLD or (vf is not None and vf >= 0.60):
        return "HIGH"
    if med < NDVI_BARE_THRESHOLD and (vf is None or vf < 0.15):
        return "LOW"
    return "MIXED"


def classify_vegetation_pattern(zones: dict):
    """Return (pattern, surface_stats, detail).

    ``zones`` keys: core, interior, edge, ring (each a footprint_ndvi_stats dict
    or an empty/zero dict), plus footprint_area_m2 and pixel_area_m2.

    ``surface_stats`` is the zone used as the building-surface signal (core when
    it has enough pixels, otherwise interior). Nothing here rewrites geometry or
    height; it only interprets NDVI.
    """
    interior = zones.get("interior") or {}
    core = zones.get("core") or {}
    edge = zones.get("edge") or {}
    ring = zones.get("ring") or {}
    fp_area = float(zones.get("footprint_area_m2") or 0.0)
    px_area = float(zones.get("pixel_area_m2") or 100.0)

    int_valid = int(interior.get("n_valid", 0) or 0)
    int_nodata = float(interior.get("nodata_fraction", 1.0))
    core_valid = int(core.get("n_valid", 0) or 0)
    int_vf = float(interior.get("vegetation_fraction") or 0.0)

    sub_pixel = core_valid < MIN_VALID_PIXELS and fp_area < _MIN_CORE_FOOTPRINT_RATIO * px_area
    detail = {
        "core_level": zone_veg_level(core),
        "interior_level": zone_veg_level(interior),
        "edge_level": zone_veg_level(edge),
        "ring_level": zone_veg_level(ring),
        "core_pixels": core_valid,
        "interior_pixels": int_valid,
        "footprint_area_m2": round(fp_area, 1),
        "footprint_pixel_ratio": round(fp_area / px_area, 2) if px_area else None,
        "sub_pixel": bool(sub_pixel),
        "core_median": core.get("ndvi_median"),
        "interior_median": interior.get("ndvi_median"),
        "edge_median": edge.get("ndvi_median"),
        "ring_median": ring.get("ndvi_median"),
    }

    # ---- data-quality / resolution gates (never fabricate) ----
    if int_valid == 0:
        return "NODATA", interior, detail
    if int_valid < MIN_VALID_PIXELS or int_nodata > NODATA_FRACTION_MAX:
        return "RESOLUTION_LIMITED", interior, detail
    if sub_pixel and int_valid < 4:
        # Footprint ~<= one pixel with no core - genuinely unresolvable. We
        # cannot see a roof either way, so do NOT assert "vegetation-dominant";
        # return resolution-limited and let a reviewer decide.
        return "RESOLUTION_LIMITED", interior, detail

    # ---- spatial pattern: we have a usable building-surface signal ----
    surface = core if core_valid >= MIN_VALID_PIXELS else interior
    surface_level = zone_veg_level(surface)
    ring_level = detail["ring_level"]
    edge_level = detail["edge_level"]
    context_vegetated = ring_level in ("HIGH", "MIXED") or edge_level in ("HIGH", "MIXED")
    ring_clear = ring_level in ("LOW", "NONE")

    if surface_level == "LOW":
        # Building surface (roof/core) reads clear. Decide where any remaining
        # vegetation sits: creeping into the footprint interior, only outside,
        # or nowhere.
        if detail["interior_level"] in ("MIXED", "HIGH"):
            if context_vegetated:
                return "EDGE_VEGETATION", surface, detail
            return "INTERNAL_VEGETATION", surface, detail
        if context_vegetated:
            return "SURROUNDING_VEGETATION", surface, detail
        return "LOW_VEGETATION", surface, detail

    if surface_level == "MIXED":
        if detail["core_level"] == "LOW" and context_vegetated:
            return "EDGE_VEGETATION", surface, detail
        if ring_clear:
            return "INTERNAL_VEGETATION", surface, detail
        return "MIXED_VEGETATION", surface, detail

    # surface_level == "HIGH"
    if ring_clear:
        # Vegetation inside the footprint but not around it: courtyard / garden /
        # green roof / footprint mismatch - NOT automatically a tree.
        return "INTERNAL_VEGETATION", surface, detail

    int_med = interior.get("ndvi_median") or 0.0
    footprint_dominated = (
        detail["interior_level"] == "HIGH"   # the whole footprint, not just the core
        and int_vf >= DOMINANT_VEG_FRACTION  # <=20% of it could be roof
        and int_med >= NDVI_DOMINANT_MEDIAN  # and it reads clearly vegetative
    )
    if footprint_dominated and not sub_pixel:
        return "VEGETATION_DOMINANT", surface, detail
    # A high core / edge reading but the footprint still holds non-vegetated
    # (roof) pixels, or it is too small to be sure -> mixed, needs a reviewer.
    return "MIXED_VEGETATION", surface, detail


def _spatial_result(**kw) -> dict:
    surface = kw.get("surface") or {}
    interior = (kw.get("zones") or {}).get("interior") or {}
    detail = kw.get("detail") or {}
    score = kw.get("score")
    pattern = kw["pattern"]
    return {
        "vegetation_evidence": pattern,
        "vegetation_evidence_label": _VEG_LABELS.get(pattern, pattern),
        "vegetation_pattern": pattern,
        "building_height_confidence": kw["category"],
        "building_height_confidence_score": score,
        "building_height_confidence_score_100": (
            None if score is None else round(score * 100)
        ),
        "building_height_confidence_subscores": kw.get("subscores"),
        "vertical_evidence_status": kw["vertical_status"],
        "ndvi_data_quality_flag": kw["quality_flag"],
        "ndvi_review_recommendation": kw["review"],
        "confidence_reason": kw["reason"],
        "ndvi_zone_levels": {
            "core": detail.get("core_level"),
            "interior": detail.get("interior_level"),
            "edge": detail.get("edge_level"),
            "ring": detail.get("ring_level"),
        },
        # interior == "footprint" statistics keep the same field meaning as before
        "ndvi_value": interior.get("ndvi_median"),
        "ndvi_median": interior.get("ndvi_median"),
        "ndvi_p25": interior.get("ndvi_p25"),
        "ndvi_p75": interior.get("ndvi_p75"),
        "ndvi_iqr": interior.get("ndvi_iqr"),
        "ndvi_vegetation_fraction": interior.get("vegetation_fraction"),
        "ndvi_pixels_valid": interior.get("n_valid"),
        "ndvi_pixels_total": interior.get("n_total"),
        "ndvi_nodata_fraction": interior.get("nodata_fraction"),
        "ndvi_core_median": detail.get("core_median"),
        "ndvi_edge_median": detail.get("edge_median"),
        "ndvi_ring_median": detail.get("ring_median"),
        "ndvi_surface_median": surface.get("ndvi_median"),
        "ndvi_footprint_pixel_ratio": detail.get("footprint_pixel_ratio"),
    }


def _build_spatial_reason(pattern, detail, is_tall) -> str:
    z = (f"core={detail.get('core_level')}, interior={detail.get('interior_level')}, "
         f"edge={detail.get('edge_level')}, ring={detail.get('ring_level')}")
    heads = {
        "LOW_VEGETATION": (
            "Low vegetation across the building footprint and its surroundings; "
            "evidence supports a built structure"),
        "SURROUNDING_VEGETATION": (
            "Vegetation is concentrated outside the building footprint; the building "
            "surface shows low vegetation. Surrounding trees do not indicate "
            "vegetation-derived height"),
        "EDGE_VEGETATION": (
            "Vegetation is concentrated at the footprint boundary while the building "
            "core is clearer; evidence is mixed"),
        "INTERNAL_VEGETATION": (
            "Vegetation appears inside the footprint but not in the surrounding ring "
            "(courtyard, garden, green roof or footprint mismatch); not automatically "
            "tree-derived"),
        "MIXED_VEGETATION": (
            "Vegetation and building evidence are mixed within the footprint"),
        "VEGETATION_DOMINANT": (
            "Vegetation dominates the building-surface NDVI as well as the surroundings; "
            "the Copernicus surface elevation here may be vegetation-derived"),
        "RESOLUTION_LIMITED": (
            f"Building footprint (~{detail.get('footprint_area_m2')} m2, "
            f"{detail.get('interior_pixels')} valid NDVI pixel(s)) is comparable to or "
            f"smaller than the 10 m NDVI pixel; a reliable building-core sample cannot "
            f"be formed. Evidence is resolution-limited"),
        "NODATA": (
            "No valid NDVI pixels inside the building footprint"),
        "NOT_DETERMINABLE": (
            "Insufficient valid NDVI evidence inside the footprint"),
        "NOT_COMPUTED": (
            "NDVI vegetation layer could not be computed for this AOI"),
    }
    head = heads.get(pattern, "Vegetation evidence assessed")
    tail = f" [zones: {z}]"
    if is_tall:
        tail += "; derived height is unusually tall for this AOI"
    return head + "." + tail + "."


def evaluate_building_spatial(
    zones: dict,
    *,
    match_status_2d=None,
    parcel_overlap_ratio=None,
    building_height_m=None,
    height_confidence="MEDIUM",
    ndvi_available: bool = True,
    ndvi_unavailable_reason: str = "",
) -> dict:
    """Spatially-resolved additive evidence dict for one building.

    Vegetation near a building does not by itself lower building-height
    confidence - only vegetation that dominates the building *surface* does.
    Never fabricates: unavailable / insufficient evidence yields a ``None`` score
    and an explicit NOT_DETERMINABLE / NDVI_UNAVAILABLE status.
    """
    if not ndvi_available:
        reason = (
            "NDVI vegetation layer could not be computed for this AOI"
            + (f" ({ndvi_unavailable_reason})" if ndvi_unavailable_reason else "")
            + ". Copernicus GLO-30 elevation retained unchanged; building-height "
            "confidence not derived. Vertical height evidence requires human verification."
        )
        return _spatial_result(
            pattern="NOT_COMPUTED", category="NOT_DETERMINABLE", score=None,
            vertical_status="NDVI_UNAVAILABLE", quality_flag="NDVI_LAYER_UNAVAILABLE",
            review="HUMAN_VERIFICATION_REQUIRED", reason=reason,
            surface={}, detail={}, zones=zones or {},
        )

    zones = zones or {}
    pattern, surface, detail = classify_vegetation_pattern(zones)
    interior = zones.get("interior") or {}
    nodata_fraction = float(interior.get("nodata_fraction", 1.0))

    if pattern in ("NODATA", "NOT_DETERMINABLE"):
        return _spatial_result(
            pattern="NOT_DETERMINABLE", category="NOT_DETERMINABLE", score=None,
            vertical_status="NOT_DETERMINABLE", quality_flag="INSUFFICIENT_NDVI",
            review="HUMAN_VERIFICATION_REQUIRED",
            reason=_build_spatial_reason(pattern, detail, False),
            surface=surface, detail=detail, zones=zones,
        )

    if pattern == "RESOLUTION_LIMITED":
        return _spatial_result(
            pattern="RESOLUTION_LIMITED", category="NOT_DETERMINABLE", score=None,
            vertical_status="NOT_DETERMINABLE", quality_flag="RESOLUTION_LIMITED",
            review="HUMAN_VERIFICATION_REQUIRED",
            reason=_build_spatial_reason(pattern, detail, False),
            surface=surface, detail=detail, zones=zones,
        )

    elev_score, implausible_tall = _score_elevation(building_height_m, height_confidence)
    try:
        is_tall = implausible_tall or (
            not _is_missing_height(building_height_m)
            and float(building_height_m) > HEIGHT_TALL_FLAG
        )
    except (TypeError, ValueError):
        is_tall = implausible_tall

    surface_stats = surface or interior
    subscores = {
        "ndvi_surface": round(_score_ndvi(surface_stats), 4),
        "spatial": round(_SPATIAL_PATTERN_SCORE.get(pattern, 0.5), 4),
        "footprint": round(_score_footprint(match_status_2d, parcel_overlap_ratio), 4),
        "elevation": round(elev_score, 4),
        "quality": round(_score_quality(interior), 4),
        "consistency": round(_score_consistency(interior), 4),
    }
    score = round(_clamp(sum(SPATIAL_WEIGHTS[k] * subscores[k] for k in SPATIAL_WEIGHTS)), 4)
    quality_flag = "OK" if nodata_fraction <= NODATA_FRACTION_OK else "PARTIAL_NODATA"

    if pattern in ("LOW_VEGETATION", "SURROUNDING_VEGETATION"):
        category = "HIGH" if (score >= SCORE_HIGH and quality_flag == "OK") else "MEDIUM"
    elif pattern in ("EDGE_VEGETATION", "MIXED_VEGETATION", "INTERNAL_VEGETATION"):
        category = "MEDIUM" if score >= SCORE_LOW else "LOW"
    elif pattern == "VEGETATION_DOMINANT":
        category = "LOW"
    else:
        category = "MEDIUM"

    # Tall-height guard: bites ONLY when the building surface evidence is itself
    # vegetated / ambiguous. Never "tall + vegetation nearby = tree".
    surface_vegetated = pattern in (
        "EDGE_VEGETATION", "MIXED_VEGETATION", "INTERNAL_VEGETATION", "VEGETATION_DOMINANT"
    )
    if is_tall and surface_vegetated and category == "HIGH":
        category = "MEDIUM"

    # A footprint at/below one 10 m pixel with no reliable core cannot support a
    # HIGH confidence even when the pattern looks clean - the roof is unresolved.
    if detail.get("sub_pixel") and category == "HIGH":
        category = "MEDIUM"

    vertical_status = _VERTICAL_STATUS[category]
    review = "NONE" if category == "HIGH" else "HUMAN_VERIFICATION_REQUIRED"
    reason = _build_spatial_reason(pattern, detail, is_tall)
    return _spatial_result(
        pattern=pattern, category=category, score=score, subscores=subscores,
        vertical_status=vertical_status, quality_flag=quality_flag, review=review,
        reason=reason, surface=surface_stats, detail=detail, zones=zones,
    )


def spatial_method_manifest() -> dict:
    """Machine-readable description of the spatially-resolved method."""
    return {
        "method_version": METHOD_VERSION + "+spatial",
        "principle": (
            "Vegetation NEAR a building does not mean the building height came from a "
            "tree. Four NDVI zones (core / interior / edge / ring) are compared to "
            "locate vegetation; only vegetation dominating the building SURFACE lowers "
            "building-height confidence. Output is a bounded evidence score, NOT a "
            "calibrated probability and NOT a legal certainty; thresholds are heuristic "
            "and not calibrated to labelled ground truth."
        ),
        "zones": {
            "core": "footprint eroded by ~1 pixel (10 m) - the building surface / roof",
            "interior": "the full building footprint",
            "edge": "~1-pixel band straddling the footprint boundary",
            "ring": "outer context band ~5-30 m outside the footprint",
        },
        "zone_levels": "LOW (median<0.20 & veg-fraction<0.15) / MIXED / HIGH (median>=0.40 or veg-fraction>=0.60) / NONE (no valid pixels)",
        "patterns": {
            "LOW_VEGETATION": "surface low, surroundings low -> HIGH when score & quality allow",
            "SURROUNDING_VEGETATION": "surface low, edge/ring vegetated -> confidence NOT reduced by surrounding trees",
            "EDGE_VEGETATION": "core clear, boundary vegetated, evidence mixed -> MEDIUM + human verification",
            "INTERNAL_VEGETATION": "vegetation inside footprint but not around it -> MEDIUM + human verification (not auto-tree)",
            "MIXED_VEGETATION": "footprint holds both vegetation and non-vegetated (roof) pixels -> MEDIUM + human verification",
            "VEGETATION_DOMINANT": (
                "the FULL footprint interior reads HIGH with vegetation_fraction >= "
                f"{DOMINANT_VEG_FRACTION} and median NDVI >= {NDVI_DOMINANT_MEDIAN}, AND the "
                "surroundings are vegetated, AND the footprint is larger than one pixel "
                "-> LOW / VEGETATION_POSSIBLE (elevation more likely canopy than roof)"
            ),
            "RESOLUTION_LIMITED": "footprint ~<= one 10 m pixel, no reliable core -> NOT_DETERMINABLE + human verification (never asserted as canopy)",
            "NODATA / NOT_DETERMINABLE": "no valid NDVI inside footprint -> NOT_DETERMINABLE + human verification",
        },
        "weights": dict(SPATIAL_WEIGHTS),
        "spatial_pattern_score": dict(_SPATIAL_PATTERN_SCORE),
        "ndvi_thresholds": {
            "bare": NDVI_BARE_THRESHOLD, "vegetation": NDVI_VEG_THRESHOLD,
            "dominant_median": NDVI_DOMINANT_MEDIAN, "dominant_veg_fraction": DOMINANT_VEG_FRACTION,
        },
        "score_categories": {"HIGH_at_or_above": SCORE_HIGH, "LOW_below": SCORE_LOW},
        "min_core_footprint_ratio": _MIN_CORE_FOOTPRINT_RATIO,
        "tall_height_guard": (
            "an unusually tall derived height only downgrades confidence when the "
            "building SURFACE NDVI is itself vegetated / ambiguous"
        ),
        "human_verification_rule": "HIGH clears the gate; everything else -> HUMAN_VERIFICATION_REQUIRED",
        "limitation": (
            "Sentinel-2 NDVI is ~10 m: some buildings are inherently unresolvable and "
            "are returned as RESOLUTION_LIMITED / NOT_DETERMINABLE rather than guessed."
        ),
    }


def method_manifest() -> dict:
    """Machine-readable description of the scoring method (for reports / ledger)."""
    return {
        "method_version": METHOD_VERSION,
        "description": (
            "Weighted linear combination of bounded sub-scores. Output is an "
            "evidence/confidence score in [0,1], NOT a calibrated probability of "
            "correctness and NOT a legal certainty. NDVI is used as vegetation "
            "evidence, not as a building-vs-tree classifier."
        ),
        "ndvi_thresholds": {
            "bare": NDVI_BARE_THRESHOLD,
            "vegetation": NDVI_VEG_THRESHOLD,
            "iqr_reference": IQR_REFERENCE,
            "note": "Heuristic, tunable, NOT calibrated against labelled ground truth for this AOI.",
        },
        "data_quality_gates": {
            "min_valid_pixels": MIN_VALID_PIXELS,
            "nodata_fraction_not_determinable_above": NODATA_FRACTION_MAX,
            "nodata_fraction_ok_at_or_below": NODATA_FRACTION_OK,
        },
        "height_guard": {
            "plausible_min_m": HEIGHT_PLAUSIBLE_MIN,
            "plausible_max_m": HEIGHT_PLAUSIBLE_MAX,
            "tall_flag_m": HEIGHT_TALL_FLAG,
            "note": "Only weakens the elevation sub-score; never rewrites the stored height.",
        },
        "weights": dict(WEIGHTS),
        "score_categories": {
            "HIGH_at_or_above": SCORE_HIGH,
            "LOW_below": SCORE_LOW,
            "HIGH_also_requires": "vegetation_evidence == LOW_VEGETATION and data_quality_flag == OK",
        },
        "vertical_status_map": dict(_VERTICAL_STATUS),
        "human_verification_rule": "HIGH clears the gate; LOW / MEDIUM / NOT_DETERMINABLE -> HUMAN_VERIFICATION_REQUIRED",
    }
