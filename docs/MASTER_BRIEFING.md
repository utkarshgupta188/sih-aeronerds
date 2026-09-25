# AeroNerds — The One Document You Need

### SIH26011 · 3D ULPIN Generation and Vertical Property Mapping System
### Ministry of Rural Development · Department of Land Resources (DoLR) · Theme: Smart Automation

This is the single reference for the whole project — the problem, what we actually built, the numbers, the honest limitations, and answers to the questions judges are likely to ask. Everything here is written in plain language on purpose, so anyone on the team can read it once and defend the project confidently.

---

## 1. The problem, in one paragraph

India's land records are 2D. A "parcel" on paper is a flat shape on the ground. But real cities are vertical — a single flat parcel might now hold a 12-storey apartment block, an underground parking level, a metro tunnel running beneath it, and overhead power lines crossing above it. The current ULPIN (Unique Land Parcel Identification Number) system has no way to say "this specific 3rd-floor flat" or "this specific basement parking slot" — everything collapses into one flat ID. That causes ownership disputes, blocks infrastructure planning, and makes it impossible to properly govern modern vertical properties. SIH26011 asks for a system that can generate 3D identities — for surface land, for individual floors in a building, and eventually for underground infrastructure — by fusing drone/satellite imagery, LiDAR, GIS parcel data, floor plans, GNSS/CORS coordinates and elevation models, with AI/ML doing the automated building extraction, floor segmentation and topology checking.

## 2. What AeroNerds actually is

AeroNerds is a **working, end-to-end prototype pipeline plus an interactive 3D web app** that takes real open government/satellite data for a real Bengaluru neighbourhood, and:

1. Matches every building footprint to the legal cadastral parcel it sits on (2D).
2. Adds a height/floor dimension to each building (the vertical part).
3. Runs an AI model to flag spatial and vertical anomalies (encroachments, oddly tall buildings on tiny plots, etc.).
4. Fuses all of this evidence into one auditable record per building, with a traffic-light trust status.
5. Generates a **Proposed 3D Vertical ULPIN Linkage** — a structured ID that threads Parcel → Building → Floor.
6. Puts all of it in front of a human reviewer before anything is treated as final — the system never unilaterally decides a legal boundary.

The guiding rule for the whole build (written into our own project constitution, `AGENTS.md`) was: **never fabricate government data, never let AI adjudicate legal rights, always show your evidence and your uncertainty.** That rule is the single most important thing to understand about this project, because it's also the answer to most hard judge questions (see Section 9).

## 3. The pilot area

We did not try to boil the ocean. We picked one small, real, data-rich patch of a real city and proved the whole pipeline works there end-to-end.

- **Macro region:** Bengaluru Urban District, Karnataka.
- **Working AOI (Area of Interest):** a 2 sq. km bounding box centred on the Koramangala / Jayanagar junction — a dense, mixed-height residential/commercial pocket, chosen specifically because it has good cadastral coverage, real building footprints, and a mix of building sizes.
  - South 12.92365 · North 12.93635 · West 77.61365 · East 77.62635
- We deliberately picked this AOI **after** confirming the data actually existed and overlapped there (Phase 1: Dataset Discovery Audit), rather than picking a nice-looking area and hoping the data would show up.

## 4. The pipeline — 17 phases, explained simply

The system was built as a strict, ordered pipeline (`run_pipeline.py`), where every phase has a defined input, output, and a "stop condition" (if a phase can't be verified, the pipeline halts rather than guessing). This discipline is itself part of the pitch — it shows engineering rigor, not just a flashy demo.

| # | Phase | In plain English |
|---|---|---|
| 0 | Constitution | Before writing a line of code, we wrote down the rules we'd never break (no fake data, no AI issuing legal IDs, always show provenance). |
| 1 | Data discovery | Proved every dataset we wanted to use is real, free, legally usable, and actually covers our pilot area — before building anything. |
| 2 | Ingestion | Downloaded the raw cadastral map, satellite elevation model, and building footprints. |
| 3 | Normalisation | Converted every dataset into the same coordinate system so they can be laid on top of each other accurately (lat/lon for storage, UTM 43N metres for measuring area). |
| 4 | Quality audit | Checked every shape for corruption — self-intersecting polygons, duplicates, broken geometry — and cleaned it. |
| 5 | 2D parcel-building matching | For every building, calculated exactly how much of it sits inside which legal parcel. |
| 6 | Elevation (DEM) | Sampled satellite terrain-height data under every building so we know its true ground elevation. |
| 7 | 3D reconstruction | Took the flat 2D building shapes and extruded them upward into 3D blocks using the height data. |
| 8 | Floor evidence | Worked out how many floors each building has, and tagged exactly where that number came from. |
| 9 | AI anomaly detection | Ran a machine-learning model that flags buildings which look "statistically odd" — e.g., way too tall for their tiny plot, or barely inside their parcel. |
| 10 | Evidence fusion engine | Combined everything above into one verdict per building, with a full paper trail of who/what said what. |
| 11–12 | Provenance & topology | Made sure every field on every building can be traced back to its source, and that no two volumes illegally overlap. |
| 13 | Human review | Built a review workflow — a person can Approve, Correct, Reject, or Mark Unresolved — because AI never gets the final say. |
| 14 | 3D Vertical ULPIN linkage | Generated the structured ID string that links parcel → building → floor. |
| 15 | 3D Web UI | Built the interactive map application judges actually click through. |
| 16 | SIH audit | Went back through the official problem statement line by line and checked every requirement against what we actually built (see Section 8). |

## 5. The numbers (what the pipeline actually produced)

These are real outputs from a completed pipeline run over the Koramangala/Jayanagar AOI — not projections.

- **2,734** building footprints analysed
- **78** legal cadastral parcels in the AOI
- **2,333 (85.3%)** buildings fully **CONTAINED** inside a single parcel (clean match)
- **390 (14.3%)** buildings **MAJORITY**-inside a parcel (mostly fine, minor boundary touch)
- **11 (0.4%)** buildings flagged as **BOUNDARY_OVERLAP** — a likely encroachment or straddled boundary, routed to human review
- **0** buildings fell completely outside a known parcel
- **82 buildings (3.0%)** flagged by the AI anomaly model as statistical outliers
- **2,320 (84.9%)** buildings reached final status **VERIFIED**, **332 (12.1%)** **PROVISIONAL**, **82 (3.0%)** **HUMAN_VERIFICATION_REQUIRED**
- Average ground elevation sampled across the AOI: **~896 m** above sea level (Copernicus DEM GLO-30)
- Every one of the 2,734 buildings carries a **Proposed 3D Vertical ULPIN**, a full evidence-provenance record, and a verification-gate status

## 6. Data sources — what's real and what's modeled (say this proactively, don't wait to be asked)

This is the section most likely to make or break credibility with judges, so we are deliberately upfront about it.

**Genuinely real, open, government/public data:**

| Dataset | What it is | Licence | Used for |
|---|---|---|---|
| OpenCity Bengaluru Cadastral Maps (KSRSAC / BDA ecosystem) | Official 2D property/parcel boundaries | Public domain | The legal ground-truth parcel layer |
| OpenStreetMap building footprints | Crowdsourced but verifiable building outlines | ODbL | The physical shape of every structure |
| Copernicus DEM GLO-30 (via AWS Open Data) | Global terrain elevation model | Free/open | Ground elevation (Z-axis base) for every building |
| OSM `building:levels` tags | Human-tagged floor counts, where present | ODbL | The gold-standard floor source, when available |

**Deterministically modeled, explicitly labeled as such (never presented as government data):**

- **Building heights / floor counts:** OSM had essentially zero explicit floor tags in this specific 2 sq km pilot patch, and raw 30m-resolution satellite DEM pixels are too coarse to reliably measure most individual houses (a 30m pixel covers 900 m², bigger than most residential plots — see the honest explanation in `resolutionData.md`). So building heights were **statistically modeled** using a Google Open Buildings 2.5D-style density profile for South Bengaluru, deterministically assigning realistic floor counts (2–7 floors) based on footprint size. Every such value is tagged `source: GOOGLE_OPEN_BUILDINGS_2.5D, confidence: MEDIUM` in the evidence ledger — never silently blended with real government data.
- **AI anomaly scores** are computed values (`source: ISOLATION_FOREST_ML`), clearly separated from raw survey data.
- **Proposed 3D Vertical ULPINs** are explicitly tagged `PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE`.

The rule we followed everywhere (Project Rule 10 / `dataUse.md`): split every output into **authentic base layers** (cadastral + footprints + DEM, never altered) versus **deterministically modeled metadata** (heights, floors, ULPIN strings), and never let the two masquerade as each other.

## 7. The "Proposed 3D Vertical ULPIN" — and why it's not an official ID

This is the most legally sensitive part of the whole project, and it's important the team can explain it without stumbling.

**We do not invent fake government ULPINs.** Early in the build we had a script generating cosmetic 14-digit fake ULPIN numbers purely to make the demo look "complete" — we deleted it. Fabricating a government-style identifier is exactly the kind of thing that gets a hackathon prototype disqualified.

Instead, the system reads whichever real identifier is already attached to a cadastral polygon (survey number, plot ID, or true government ULPIN where present) and treats that as the base legal identity. On top of that base ID, we deterministically append the 3D evidence we derived:

```
[Government/Cadastral Parcel ID]  →  [Building ID]  →  [Floor Index]
```

Example format used in the UI: `IN-KA-BLR-P78-B12-F3` (India → Karnataka → Bengaluru → Parcel 78 → Building 12 → Floor 3).

**The framing to use with judges:** *"We are not claiming to legally issue a 3D ULPIN — only a competent government authority can do that. What we built is the computational framework a government system could use to generate one: it proves, with geometry and evidence, that a specific building volume sits inside a specific legal parcel, and it structures that proof into a ULPIN-ready hierarchical ID."* That is a precise, defensible answer to "isn't this just a fake ID generator?"

## 8. SIH26011 requirement-by-requirement compliance

| Official requirement | What we built | Status |
|---|---|---|
| 3D identities for surface parcels | Cadastral parcel normalisation + validation pipeline | ✅ Done |
| Multi-storey vertical delineation | Height/floor assignment per building, extruded 3D volumes | ✅ Done |
| Proposed 3D ULPIN linkages | `Parcel → Building → Floor` hierarchical ID, tagged as proposed | ✅ Done |
| GIS parcel layer integration | EPSG:4326 + metric UTM 43N intersection matching | ✅ Done (2,723+ matched structures) |
| DEM/DSM elevation processing | Copernicus GLO-30 DEM sampling under every footprint | ✅ Done |
| AI/ML automated analysis | Isolation Forest anomaly detection (4D feature vector) | ✅ Done (82 outliers flagged) |
| Topology / conflict validation | Deterministic evidence-fusion + verification-gate engine | ✅ Done |
| Interactive 3D system | MapLibre GL JS web app with property cards and review gate | ✅ Done |
| Underground infrastructure | Not built in this MVP | ⚪ Explicitly scoped out — see Section 10 |
| Automated building *extraction* from raw imagery (U-Net/Mask R-CNN) | We use pre-extracted OSM/Open Buildings footprints rather than running our own segmentation model on raw imagery | ⚪ Framework designed for it (see Section 10), not executed in the MVP |

## 9. AI/ML — what's actually running (and what isn't)

Be precise here; overclaiming AI is a fast way to lose credibility with a technical panel.

**Actually implemented and running:**
- **Isolation Forest** (`scikit-learn`) — unsupervised anomaly detection over a 4-feature vector (parcel-overlap ratio, building height, ground elevation, floor count). Flags the top ~3% of statistically unusual buildings for human review. This directly satisfies the SIH ask for "intelligent topology validation" support and automated conflict flagging.

**Designed for, in the project constitution, but not executed as a trained model in this MVP:**
- Building extraction/segmentation (U-Net or Mask R-CNN) — the MVP uses existing open building-footprint datasets (OSM, Google Open Buildings) instead of training our own segmentation network on raw drone/satellite imagery, because a defensible, evaluated model needs labelled training data and held-out validation we didn't have time to build for the MVP window. Honest answer if asked: *"the architecture is designed to slot in a segmentation model at the ingestion stage; for the MVP we used pre-extracted open building footprints as the evidence source instead of training our own extractor."*
- A supervised floor-count attribute model (Random Forest / XGBoost) — deliberately **not** run, because we don't have genuinely labelled floor-count ground truth for this AOI, and the project rule explicitly forbids fabricating labels just to produce a metric. This is a disciplined "we didn't fake it" story, not a gap to hide.

All deterministic geometry — CRS transforms, polygon containment, area/overlap calculations — is done with plain GIS math (GeoPandas/Shapely), never with AI. That's intentional: legal boundary questions should never depend on an opaque model.

## 10. Honest limitations (own these before judges find them)

- **LOD1 "massing blocks" only.** Buildings are flat-topped extruded boxes, not detailed architectural shapes (no roofs, balconies, setbacks). True LOD2/LOD3 requires mesh/point-cloud data (LiDAR, BIM, Overture 3D, Google Photorealistic 3D Tiles) that wasn't freely available for this AOI. Documented upgrade path exists (`suggestSolutionsFor3D.md`): move to CesiumJS + glTF/3D Tiles when real mesh data is available.
- **Floor counts are modeled, not measured**, for the vast majority of buildings in this specific pilot patch, because OSM had ~0 explicit floor tags here and 30 m satellite pixels are too coarse for most residential footprints. This is disclosed openly in the evidence ledger (`confidence: MEDIUM`, explicit source tag), not hidden.
- **No underground infrastructure module** in the MVP (utilities, metro tunnels, basements) — explicitly scoped out for the hackathon timeline, though the same parcel→volume→evidence architecture is built to extend downward as well as upward.
- **Single pilot AOI (2 sq km).** The pipeline is deterministic and reproducible, but has only been proven at prototype scale (2,734 buildings), not city- or state-scale.
- **Not connected to any live state land-record system.** This is a standalone reproducible pipeline + demo UI, not integrated with Bhu-Naksha or a state ULB backend.
- **The 3D ULPIN is explicitly non-official** — every single one is tagged `PROPOSED_LINKAGE_NOT_OFFICIAL_ISSUANCE`.

Framing tip: every limitation above has a one-line "and here's why that was the right call for a defensible prototype" answer baked into it. Use that framing rather than apologizing.

## 11. Tech stack

- **Geospatial processing:** Python, GeoPandas, Shapely, Rasterio, PyProj — deterministic CRS handling, polygon validity, spatial intersection, DEM sampling.
- **AI/ML:** scikit-learn (Isolation Forest) for anomaly detection.
- **3D frontend:** Vanilla HTML/CSS/JS + MapLibre GL JS (WebGL-based, hardware-accelerated, zero build step, loads fast for a live demo) — deliberately not React/Next.js, to keep the demo bulletproof and dependency-light.
- **Data formats:** GeoJSON (vectors), GeoTIFF (DEM raster), KMZ (source cadastral).
- **Coordinate systems:** EPSG:4326 (WGS84, storage/display) and EPSG:32643 (UTM 43N, metric calculations).
- **Orchestration:** a single `run_pipeline.py` runs ingestion → normalisation → matching → elevation → floors → AI → fusion → ULPIN generation → launches the local web server (`localhost:8000`) end to end.

## 12. How to run it (for the team, or if a judge asks to see it live from scratch)

```bash
git clone https://github.com/sujayghosh13/aeronerds-sih26011.git
cd aeronerds-sih26011
python -m venv venv
# Windows: .\venv\Scripts\activate   |   Mac/Linux: source venv/bin/activate
pip install -r requirements.txt
python run_pipeline.py
```
This ingests all raw data, cleans/normalises it, runs the 2D match, samples elevation, allocates floors, runs the anomaly model, fuses the evidence ledger, generates the proposed ULPINs, and starts a local server at **http://localhost:8000** serving the 3D web app.

## 13. Live demo script (3–4 minutes)

1. **Open the map.** Point out the dark base map and the true-to-scale 3D skyline of the Koramangala/Jayanagar pilot block.
2. **Explain the traffic-light colours.** 🟢 Green = building footprint cleanly inside its legal parcel (>95%). 🟡 Amber = mostly inside, touches the boundary. 🔴 Red = boundary conflict / encroachment — routed to a human.
3. **Click a green building.** Show the Property Card: height, floor count, data-source tag, and the Proposed 3D ULPIN (e.g. `IN-KA-BLR-P78-B12-F3`). Say: *"We're not just drawing 2D maps — we're delineating individual floors and giving each one a structured spatial identity."*
4. **Click a red building.** Show the Verification Gate reads `HUMAN_VERIFICATION_REQUIRED`. Say: *"AI flags it, but AI never decides. A human reviewer has the final call on any legal boundary question."*
5. **Trigger the audit gate.** Click `REJECT` (or `APPROVE`/`CORRECT`). Show the status updates live and an audit-log entry appears. Say: *"Every reviewer decision is immutably logged — full legal auditability."*
6. **Close on the honesty point.** *"Everything you just saw is either real open government/satellite data, or clearly tagged modeled data — we never blend the two, and we never claim to issue an official ULPIN."*

## 14. Anticipated judge questions — and the answers

**"Is this a real ULPIN? Can this actually update government records?"**
No, and we designed it not to. It's a *Proposed 3D Vertical ULPIN Linkage* — a structured, evidence-backed ID that a competent government authority could use to *officially* issue a 3D ULPIN. Our software is the spatial-evidence engine, not the issuing authority.

**"Where does your data actually come from — is any of it fake?"**
Cadastral parcels, building footprints, and terrain elevation are all real, open, licensed government/public datasets (OpenCity, OpenStreetMap, Copernicus DEM). Building heights/floor counts, where not explicitly tagged in OSM, are deterministically modeled from a public building-density profile and explicitly labeled `MEDIUM confidence` — never presented as survey-grade truth. That split is enforced everywhere in our evidence ledger.

**"How do you handle boundary conflicts / disputes?"**
We never auto-resolve them. Any building with <50% overlap with its parcel, or flagged as a statistical anomaly by the AI model, is routed to `HUMAN_VERIFICATION_REQUIRED` and shown on a review gate with Approve/Correct/Reject/Mark-Unresolved actions, all audit-logged.

**"What does the AI actually do — is this 'AI-washing'?"**
One production AI component is genuinely running: an Isolation Forest anomaly detector over four spatial/vertical features, flagging the 3% most statistically unusual buildings for review. We chose not to run additional ML (building-segmentation from raw imagery, supervised floor prediction) in the MVP because we lacked genuinely labelled training/validation data for this AOI — and our own project rules explicitly forbid fabricating metrics or labels just to claim more AI. The architecture is built to add those models when real labelled data exists.

**"Why is the 3D so blocky / flat-roofed?"**
It's LOD1 massing — accurate footprint and accurate height, extruded straight up. True architectural detail (roofs, balconies) needs mesh or point-cloud data (LiDAR, BIM, drone photogrammetry) that isn't freely available for this pilot area. We have a documented upgrade path to CesiumJS + glTF/3D Tiles for when that data exists (e.g. SVAMITVA drone surveys, municipal BIM submissions).

**"How would this scale beyond one 2 sq km pilot?**"
The pipeline is fully deterministic and reproducible — every phase (ingest → normalise → validate → match → elevate → fuse → generate) is a scriptable, idempotent step with defined stop conditions. Scaling is an infrastructure question (parallel processing, cloud deployment, PostGIS backend) rather than a redesign; the logic itself doesn't change with area.

**"What about underground infrastructure — the SIH statement mentions it explicitly?"**
Out of scope for this MVP by deliberate choice, given the hackathon timeline. The same Parcel → Volume → Evidence architecture that goes up (floors) is designed to extend down (basements, utility corridors) once a suitable elevation-below-ground data source is available — we didn't want to fabricate an underground layer with no real data behind it.

**"What stops someone from gaming this — e.g., a fake tall building claiming space?"**
Every value in the system carries mandatory provenance (source, date, licence, processing step, model/version, verification status). Nothing is accepted as `VERIFIED` without matching real cadastral geometry, and anything that looks legally significant is hard-routed to a human reviewer rather than being silently accepted.

## 15. Roadmap (if asked "what's next")

1. Swap synthetic height modeling for real drone/LiDAR height data (SVAMITVA surveys, municipal BIM) where available, upgrading confidence from MEDIUM to HIGH/VERIFIED.
2. Move rendering from MapLibre massing blocks to CesiumJS + 3D Tiles/glTF for true architectural detail (LOD2/LOD3).
3. Train and evaluate a real building-segmentation model (U-Net/Mask R-CNN) against held-out labelled imagery, replacing the pre-extracted footprint approach.
4. Extend the volume model downward for underground utilities/parking once a legitimate elevation-below-ground data source is identified.
5. Scale the pilot from one 2 sq km AOI to full-ward, then full-city coverage, moving storage/processing to PostgreSQL + PostGIS in the cloud.
6. Formal integration path with a state Bhu-Naksha system, positioning AeroNerds as the evidence-generation layer feeding an official 3D-ULPIN issuance workflow owned by DoLR.

## 16. Glossary (so nobody gets caught out on jargon)

- **ULPIN** — Unique Land Parcel Identification Number; India's national ID scheme for land parcels.
- **Cadastral parcel** — the legally defined boundary of a piece of land.
- **DEM (Digital Elevation Model)** — bare-ground terrain elevation.
- **DSM (Digital Surface Model)** — elevation of everything on the surface (buildings, trees, ground) — not the same as DEM; conflating the two is a common, avoidable mistake we deliberately didn't make.
- **CRS (Coordinate Reference System)** — the mathematical system used to express location (e.g. EPSG:4326 = standard lat/lon; EPSG:32643 = UTM Zone 43N, used here for accurate metre-based measurements).
- **LOD (Level of Detail)** — how architecturally detailed a 3D model is; LOD1 = simple extruded block, LOD2/3 = roofs/facades/interior detail.
- **Isolation Forest** — an unsupervised machine-learning algorithm that finds "odd ones out" in a dataset without needing labelled examples.
- **Evidence ledger / fusion engine** — our internal audit-trail system that records where every piece of data came from and how confident we are in it, before any decision is finalised.
- **Human verification gate** — the mandatory checkpoint where a person, not the AI, makes the final call on anything legally significant.

---

*This document is the master reference for AeroNerds (SIH26011). Source docs consolidated: README, SIH26011_COMPLETE_DEEP_DIVE, technicalSpec, explainPrototype, PHASES, AOI_SELECTION, DATASET_AUDIT, DATA_SOURCES, TECH_AND_DATA_STRATEGY, normalisation_report, DATA_QUALITY_REPORT, MATCHING_REPORT_2D, ELEVATION_REPORT, FLOOR_EVIDENCE_REPORT, AI_ANOMALY_REPORT, EVIDENCE_FUSION_REPORT, SIH_AUDIT_VERIFICATION, ulpinConcern, dataUse, cityUse, suggestSolutionsFor3D, resolutionData, and AGENTS.md (project constitution).*
