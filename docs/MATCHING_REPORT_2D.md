# Phase 5: Parcel/Building 2D Matching Report

This report summarizes the deterministic 2D topological linkage between OpenCity cadastral parcels and OSM building footprints within the 2 sq km Bengaluru Urban AOI.

## Matching Rules Applied
Geometries were projected to the region's configured processing CRS for highly accurate metric area intersection calculations.
- **CONTAINED**: Building footprint is >95% inside a single parcel.
- **MAJORITY**: Building footprint is 50%-95% inside a single parcel.
- **BOUNDARY_OVERLAP (CONFLICT)**: Building footprint intersects a parcel, but <50% of its area is inside it (likely crossing a boundary). Marked for human verification.
- **NO_PARCEL**: Building footprint falls entirely outside any known cadastral parcel.

---

## Results Summary

- **Total Buildings Analyzed**: 2734
- **Total Parcels Available**: 78

### Linkage Distribution

| Match Status | Count | Percentage |
| :--- | :--- | :--- |
| **CONTAINED** | 2333 | 85.3% |
| **MAJORITY** | 390 | 14.3% |
| **BOUNDARY_OVERLAP** | 11 | 0.4% |
| **NO_PARCEL** | 0 | 0.0% |

**Output File**: `data/processed/buildings_linked_2d.geojson`
