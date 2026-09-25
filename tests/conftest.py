import os
import sys

# Make ``scripts/`` importable so tests can pull in the pure-Python NDVI core
# without needing the geospatial stack (rasterio / shapely / pyproj).
_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
_SCRIPTS = os.path.join(_ROOT, "scripts")
for _p in (_ROOT, _SCRIPTS):
    if _p not in sys.path:
        sys.path.insert(0, _p)
