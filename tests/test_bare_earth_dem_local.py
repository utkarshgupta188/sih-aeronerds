"""
Validation for the local bare-earth DEM fallback in
``scripts/ingestion/load_bare_earth_dem.py``.

Only the pure, rasterio-free AOI-overlap helper is exercised here (the full
raster validation needs a real GeoTIFF, which the operator supplies manually).
The existing NDVI / pipeline behaviour is untouched by this module.
"""

import importlib.util
import os

_PATH = os.path.join(os.path.dirname(__file__), "..", "scripts", "ingestion",
                     "load_bare_earth_dem.py")
_spec = importlib.util.spec_from_file_location("load_bare_earth_dem", _PATH)
lbe = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(lbe)

# Existing BoundaryLens pilot AOI (W, S, E, N) - must not change.
AOI = (77.61365, 12.92365, 77.62635, 12.93635)


def test_dem_fully_covering_aoi_overlaps():
    dem = (77.5, 12.8, 77.8, 13.0)  # generous tile around Bengaluru
    assert lbe.bbox_overlaps(dem, AOI) is True


def test_dem_partially_covering_aoi_overlaps():
    dem = (77.620, 12.930, 77.700, 13.000)  # clips the NE corner of the AOI
    assert lbe.bbox_overlaps(dem, AOI) is True


def test_dem_exactly_matching_aoi_overlaps():
    assert lbe.bbox_overlaps(AOI, AOI) is True


def test_dem_elsewhere_in_india_does_not_overlap():
    chennai = (80.20, 13.05, 80.35, 13.20)   # wrong city
    assert lbe.bbox_overlaps(chennai, AOI) is False


def test_dem_far_away_does_not_overlap():
    somewhere_else = (-120.0, 35.0, -119.0, 36.0)
    assert lbe.bbox_overlaps(somewhere_else, AOI) is False


def test_overlap_is_symmetric():
    dem = (77.60, 12.90, 77.63, 12.94)
    assert lbe.bbox_overlaps(dem, AOI) == lbe.bbox_overlaps(AOI, dem)


def test_edge_touching_counts_as_overlap():
    # DEM whose western edge meets the AOI's eastern edge.
    dem = (77.62635, 12.92365, 77.70, 12.93635)
    assert lbe.bbox_overlaps(dem, AOI) is True
