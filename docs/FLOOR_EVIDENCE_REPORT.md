# Phase 8: Floor Evidence Extraction Report

This report documents the extraction of 3D multi-storey floor entities linking physical structures to cadastral parcels in Bengaluru Urban.

## 1. Summary Statistics
- **Total Buildings Analyzed**: 2734
- **Total Discrete Floor Entities Extracted**: 8891
- **Average Floors per Building**: 3.25

## 2. Floor Count Distribution
| Floor Count | Building Count | Percentage |
| :--- | :--- | :--- |
| **2 Floors** (7.0m) | 589 | 21.5% |
| **3 Floors** (10.5m) | 867 | 31.7% |
| **4 Floors** (14.0m) | 1278 | 46.7% |

## 3. Data Provenance & Evidence Hierarchy (Rule 3)
| Source | Count | Confidence | Provenance Description |
| :--- | :--- | :--- | :--- |
| `GOOGLE_OPEN_BUILDINGS_2.5D` | 2734 | `MEDIUM` | Satellite ML height estimation (Google Open Buildings 2.5D) |

**Output Artefacts**:
- Floor Entities Database: `data/processed/floor_entities.json`
- Updated 3D Web UI Dataset: `frontend/data/buildings_3d.geojson`
