# AeroNerds SIH26011 — Live Demonstration Guide
### Team areonerds • Smart India Hackathon 2026

This guide provides the exact 3–5 minute demonstration protocol for presenting the AeroNerds prototype to the SIH evaluating panel.

---

## A. Setup

Ensure the repository and Python environment are prepared on your presentation machine:

```powershell
# Windows (PowerShell)
cd D:\AeroNerds
.\venv\Scripts\Activate.ps1
```

*(If running without activating the virtual environment, you can invoke `python` directly via `.\venv\Scripts\python.exe` or double-click `start_demo.bat`).*

---

## B. Health Check

Before beginning the evaluation session, run the automated health check to confirm all frontend assets and processed spatial layers are intact:

```powershell
python scripts/demo_health_check.py
```

**Expected output:**
```text
==========================================
 AeroNerds SIH26011 Demo Health Check  
==========================================
[PASS] Frontend
[PASS] Building data
[PASS] Parcel data
[PASS] Elevation data
[PASS] Floor evidence
[PASS] AI/evidence data
[PASS] Required dependencies

DEMO READY
```

---

## C. Start Demo

Launch the lightweight, zero-latency presentation server:

```powershell
python run_demo.py
# Alternatively on Windows, double-click: start_demo.bat
```

Open Google Chrome or Microsoft Edge and navigate to:
👉 **[http://localhost:8000/](http://localhost:8000/)**

> **Note**: This mode operates 100% locally and offline. It uses verified, pre-computed outputs and avoids re-training models or calling external rate-limited APIs during judging.

---

## D. What to Click on the Map

1. **Map Navigation**: Left-click + drag to pan; right-click + drag (or scroll wheel) to tilt and rotate the 3D pitch/bearing.
2. **Cadastral Overlay**: The yellow/white dashed boundary lines represent digitized 2D land revenue parcels.
3. **Green Buildings (`CONTAINED`)**: High-confidence structures cleanly enclosed inside a cadastral parcel.
4. **Amber Buildings (`MAJORITY`)**: Structures touching parcel edges or spanning multiple boundaries.
5. **Red Buildings (`BOUNDARY_OVERLAP` / `ANOMALY`)**: Structures crossing legal parcel boundaries, automatically routed for human reviewer adjudication.
6. **Property Card**: Clicking any structure pops open its deterministic attributes in the left sidebar.
7. **View Floor Levels Button**: Clicking this on multi-storey structures opens the stacked 3D floor band visualizer.
8. **Reviewer Audit Buttons**: `APPROVE`, `CORRECT`, `REJECT`, `UNRESOLVED` buttons at the bottom of the property card.
9. **Audit Logs Tab**: Switches to the live registrar audit trail.

---

## E. Suggested 3–5 Minute Demo Flow

| Step | Time | Action | What to Say to the Judges |
| :--- | :--- | :--- | :--- |
| **1. The Problem & Context** | 0:00 – 0:45 | Show the 3D skyline of South Bengaluru | *"Respected judges, current cadastral systems in India are strictly 2D flat parcels. In urban centers, vertical property ownership and multi-storey structures have no unified 3D spatial linkage. AeroNerds creates a deterministic vertical hierarchy linking surface parcels to individual building volumes and floor entities without fabricating government records."* |
| **2. Parcel-Building 2D Linkage** | 0:45 – 1:30 | Click a **Green building** (cleanly contained) | *"Notice the 2D cadastral parcel boundary beneath this building. Our geometric matching engine tests for topological containment. This structure has a `CONTAINED` status with 100% boundary overlap ratio, deterministically linked to Cadastral Parcel 22068."* |
| **3. Ground Elevation & Height** | 1:30 – 2:15 | Point to **Ground Elev** and **Height** in sidebar | *"Under Rule 4 of our AGENTS constitution, we never guess heights. Ground elevation is sampled directly from bare-earth DEM terrain. For above-ground height, when an official OSM level tag exists, it is marked `OSM_VERIFIED`. When unobserved, height follows an empirical urban distribution profile marked `ESTIMATED / PROVISIONAL`."* |
| **4. Floor Evidence & ML Calibration** | 2:15 – 3:00 | Click **View Floor Levels** | *"We trained a spatial-split Random Forest on 12,700+ verified Bangalore floor labels. Rather than dividing height blindly by 3.5m, our model predicts calibrated floor counts. Here, the floor levels are visually delineated and given discrete proposed identifiers."* |
| **5. AI Anomaly & Boundary Conflict** | 3:00 – 3:45 | Click an **Amber or Red building** crossing a parcel line | *"Here, our unsupervised Isolation Forest flagged a boundary overlap anomaly. AI never makes the legal judgment—it routes legally significant conflicts to the Reviewer Gate marked `HUMAN_VERIFICATION_REQUIRED`."* |
| **6. Human Adjudication & Audit Log** | 3:45 – 4:30 | Click `REJECT` or `CORRECT`, then switch to **Audit Logs** tab | *"As the reviewer, I take an action. Notice the status immediately updates to `REVIEWER_REJECTED` and the building color changes. In the Audit Logs tab, the action, timestamp, and parcel reference are immutably recorded for full legal auditability."* |
| **7. Closing & Governance Principle** | 4:30 – 5:00 | Point to the Proposed 3D Linkage disclaimer | *"Finally, our proposed 3D identifiers (e.g. `IN-KA-BLR-P22068-B93697573`) represent vertical spatial linkages for reviewer adjudication. We strictly uphold that legally binding ULPIN issuance remains the sole prerogative of the competent government authority."* |

---

## F. What Each UI Field Means

- **ULPIN / Parcel ID**: The source 2D revenue cadastral parcel ID (from municipal/survey GIS layers).
- **Match Status**:
  - `CONTAINED` (🟢): Building footprint is strictly inside parcel boundaries (>95% area).
  - `MAJORITY` (🟡): Building is mostly inside (50%–95%), touching border.
  - `BOUNDARY_OVERLAP` (🔴): Significant boundary crossing or encroachment.
- **Confidence Score**: Deterministic topological alignment score (100% minus anomaly penalty).
- **Ground Elev (DEM)**: Terrain elevation above sea level in metres, sampled from bare-earth DEM.
- **Height / Floors**: Derived height and floor count, explicitly distinguished as `Observed` (real tag) or `EST.` (model prediction).
- **Data Source**: Provenance source (`OSM_VERIFIED`, `ESTIMATED (Urban Profile Model)`, `CartoDEM`).
- **AI Anomaly Status**: Scored by 4D Isolation Forest (`NORMAL` vs `ANOMALY DETECTED (score)`).
- **NDVI Evidence**: Sentinel-2 L2A vegetation signal assessing whether elevation reflects structure or tree canopy.
- **Proposed 3D Linkage**: The hierarchical vertical identifier (`IN-KA-BLR-P<Parcel>-B<Building>`).
- **Verification Gate**: Reviewer status (`VERIFIED`, `PROVISIONAL`, `HUMAN_VERIFICATION_REQUIRED`, `REVIEWER_APPROVED`, `REVIEWER_REJECTED`).

---

## G. How to Demonstrate Human Verification

1. Click any building with status `HUMAN_VERIFICATION_REQUIRED` (or any amber/red structure).
2. Point out to the judges that the system **refuses** to automate legally sensitive decisions.
3. Under **Reviewer Audit Gate (Rule 8)**, click one of the reviewer buttons:
   - `APPROVE`: Confirms boundary alignment.
   - `CORRECT`: Adjusts or flags for cadastral rectification.
   - `REJECT`: Rejects anomalous alignment or unverified claim.
   - `UNRESOLVED`: Marks for ground survey verification.
4. Click the **Audit Logs** tab at the top of the sidebar.
5. Show the entry with timestamp, action type, and parcel identifier.

---

## H. What Happens When Evidence Conflicts?

AeroNerds adheres to strict deterministic conflict resolution:
- When cadastral parcel and building footprints overlap multiple parcels, the system does **not** silently assign ownership. It tags the feature as `CONFLICT / MAJORITY` and prompts human verification.
- When elevation data suggests height but Sentinel-2 NDVI detects dense canopy (`VEGETATION_DOMINANT`), the building is flagged with `VEGETATION POSSIBLE` and height confidence is downgraded to `LOW`.
- When floor count cannot be determined with statistical confidence, the model returns `NOT_DETERMINABLE` rather than hallucinating an arbitrary floor count.

---

## I. Known Limitations

- **Resolution**: Public global DEMs have a 30-metre pixel resolution. In dense urban fabric, high-precision slab separation requires high-resolution drone LiDAR or municipal architectural BIM submissions.
- **Underground Infrastructure**: Scoped out of this MVP due to the absence of public subterranean GIS datasets. The Parcel → Building → Volume entity architecture is designed to support negative vertical coordinates once utility/metro point clouds are ingested.
- **Legal Authority**: Proposed 3D vertical IDs are spatial linkage proposals for evaluation, not legal land titles.

---

## J. How to Run the Full Pipeline

If a judge requests full end-to-end verification from raw data:

```powershell
python run_pipeline.py
```

This runs all 17 phases sequentially:
1. `scripts/01_select_aoi.py`
2. `scripts/ingestion/load_osm.py`
3. `scripts/ingestion/load_cadastral.py`
4. `scripts/ingestion/load_copernicus_dem.py`
5. `scripts/ingestion/load_bare_earth_dem.py`
6. `scripts/03_normalise_layers.py`
7. `scripts/04_validate_data_quality.py`
8. `scripts/05_match_parcels_buildings.py`
9. `scripts/06_extract_elevation.py`
10. `scripts/08_fetch_real_heights.py`
11. `scripts/08_extract_floor_entities.py`
12. `scripts/09_detect_anomalies_ai.py`
13. `scripts/10_fuse_evidence_engine.py`
14. `scripts/ingestion/load_sentinel2_ndvi.py`
15. `scripts/11_ndvi_vegetation_evidence.py`
16. `scripts/ingestion/load_osm_floor_labels.py`
17. `scripts/ingestion/load_copernicus_glo30.py`
18. `scripts/train_floor_model.py`
19. `scripts/12_estimate_floors.py`
20. Starts web UI on `http://localhost:8000`.
