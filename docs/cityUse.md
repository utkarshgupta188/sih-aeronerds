# BOUNDARYLENS — SIH26011 MASTER AGENT START PROMPT

You are starting the autonomous engineering loop for our SIH26011 project.

## PROJECT

Project name: BoundaryLens

Problem: 3D ULPIN and vertical property mapping.

Prototype geography:

**Bengaluru Urban District, Karnataka, India**

However, do NOT process the entire district initially.

Select a small, representative Area of Interest (AOI) inside Bengaluru Urban where the required datasets overlap.

The prototype must demonstrate:

Cadastral parcel
→ Building
→ Floor / vertical evidence
→ 3D property volume
→ topology validation
→ confidence/provenance
→ human verification
→ proposed vertical ULPIN linkage

The system must NOT claim that it issues, modifies or legally replaces an official Government ULPIN.

---

# ABSOLUTE DATA REQUIREMENT

Every dataset used for the prototype must be:

1. Free to download.
2. Legally usable under its stated licence/terms.
3. Accessible without payment.
4. Accessible without private/commercial subscription.
5. Documented with source, licence, date and coverage.
6. Actually downloadable by the team.

Do NOT assume that a dataset is free merely because a government portal displays it.

If a dataset requires:

* payment,
* commercial licensing,
* private subscription,
* government-only access,
* offline departmental permission,
* an unavailable API,
* or an access request that we cannot independently complete,

do NOT include it in the mandatory pipeline.

Mark it:

DATASET_BLOCKED

and continue looking for a genuinely free alternative.

---

# PRIMARY DATA SOURCES TO INVESTIGATE

## 1. Cadastral

Primary candidate:

Bengaluru Urban Cadastral Maps

Source:
https://data.opencity.in/dataset/bengaluru-cadastral-maps

Reported source:
KSRSAC / Bangalore Development Authority ecosystem.

Reported formats:
KML/KMZ.

Reported licence:
Public Domain.

The agent MUST independently verify:

* actual download works
* file is accessible
* geometry exists
* spatial extent
* coordinate reference system
* parcel/survey attributes
* licence
* whether the dataset actually covers the intended AOI

Do NOT assume the web page alone proves the file is downloadable.

---

# 2. DEM

Primary candidate:

Bhuvan / CartoDEM

https://bhuvan-app3.nrsc.gov.in/data/download/index.php

Alternative:

Copernicus DEM GLO-90/GLO-30 where access and licence requirements are satisfied.

Important:

DEM = terrain/ground elevation.

Do not call DEM a DSM.

---

# 3. DSM

Primary candidate:

Copernicus DEM GLO-30 Public.

Official information:
https://dataspace.copernicus.eu/explore-data/data-collections/copernicus-contributing-missions/collections-description/COP-DEM

The Copernicus documentation identifies GLO-30 as a Digital Surface Model and states that the public GLO-30/GLO-90 products are available free under the relevant licence.

Verify current download access before implementation.

Do NOT use Delhi's high-resolution Survey of India DSM unless it is independently verified as freely downloadable to us.

Do not make high-resolution DSM a dependency.

---

# 4. Building footprints

Use:

Microsoft Global ML Building Footprints

https://github.com/microsoft/GlobalMLBuildingFootprints

The dataset is freely available under CDLA Permissive 2.0.

Also investigate:

Google Open Buildings

Use only the current official distribution and licensing terms.

Also use:

OpenStreetMap

https://www.openstreetmap.org/

---

# 5. Floor evidence

Use OpenStreetMap where available:

building:levels
height
building:part

OSM documentation:

https://wiki.openstreetmap.org/wiki/Key:building:levels

IMPORTANT:

OSM floor information is NOT a government cadastral record.

It is evidence only.

If a building has no reliable floor information:

return

NOT_DETERMINABLE

Do NOT estimate floor count merely from building height.

---

# DATA-FUSION PRINCIPLE

Never silently merge conflicting datasets.

Example:

OSM:
4 floors

Other source:
5 floors

AI:
uncertain

Correct output:

CONFLICT

not:

5

Create an evidence table containing:

entity_id
source
attribute
value
timestamp
geometry
quality
licence
confidence
status

---

# DEM / DSM RULE

The system may calculate:

DSM - DEM

to obtain an above-ground surface-height signal.

But:

height ≠ exact floor count.

Never automatically convert:

15 metres

into:

5 floors

unless a validated floor-height model and appropriate labelled data support that inference.

If the evidence is insufficient:

NOT_DETERMINABLE

---

# AI REQUIREMENTS

Implement at least THREE AI/ML components.

## MODEL 1 — BUILDING SEGMENTATION

Use:

U-Net or Mask R-CNN.

Purpose:

imagery
→ building mask
→ building footprint

Use this as an automated building-extraction component.

It must be evaluated against a held-out validation set.

Report:

precision
recall
F1
IoU

Do not fabricate metrics.

---

## MODEL 2 — ATTRIBUTE MODEL

Use:

XGBoost or Random Forest.

Purpose:

predict a clearly defined building attribute.

Possible target:

floor count / floor-related class

BUT ONLY if genuinely labelled floor data exists.

If labelled floor data is unavailable:

STOP this task.

Do NOT manufacture labels.

Instead choose another defensible labelled attribute or document the limitation.

---

## MODEL 3 — ANOMALY DETECTION

Use:

Isolation Forest.

Purpose:

detect unusual disagreement between sources.

Example:

OSM floor count = 4
Government/source record = 5
height evidence inconsistent

→ anomaly/conflict flag

The model must NOT decide which source is legally correct.

---

# DETERMINISTIC GEOMETRIC ENGINE

Use:

GeoPandas
Shapely
Rasterio
GDAL
PyProj
PostGIS

Use deterministic geometry for:

* CRS transformation
* parcel validity
* building containment
* parcel/building intersection
* floor containment
* 3D overlap
* gaps
* invalid geometry
* duplicate geometry

Do NOT replace deterministic topology checks with AI.

---

# 3D RECONSTRUCTION

MVP:

parcel
+
building footprint
+
ground elevation
+
supported height evidence

→ 3D building volume

If floor evidence exists:

building
→ floor volumes

If floor evidence does not exist:

building volume only

Do not invent floors.

Use:

Open3D
trimesh

for 3D geometry processing where needed.

---

# TOPOLOGY VALIDATION

Validate:

Parcel
↓
Building
↓
Floor
↓
Unit/vertical volume

Detect:

* building outside parcel
* unexpected parcel/building overlap
* floor outside building
* overlapping floor volumes
* invalid meshes
* self-intersections
* duplicate volumes
* gaps

Create intentionally invalid test fixtures and verify that the engine catches them.

---

# CONFIDENCE

Every derived result must contain:

confidence:
HIGH / MEDIUM / LOW / NOT_DETERMINABLE

Also record:

source
model
processing step
validation result

Do not assign arbitrary percentages.

If numerical confidence is used, define and validate its calibration.

---

# PROVENANCE

For every final 3D object, a reviewer must be able to answer:

Where did this geometry come from?

Which dataset?

Which version?

What processing was performed?

Which AI model was used?

What evidence supports the floor count?

Were there conflicts?

Was human verification performed?

---

# HUMAN VERIFICATION

The AI must NEVER:

* adjudicate ownership
* decide legal rights
* modify official land records
* declare a disputed property legally valid
* issue an official ULPIN

Provide a review workflow:

APPROVE
CORRECT
REJECT
MARK_UNRESOLVED

Every reviewer action must be logged.

---

# VERTICAL ULPIN

The final prototype should demonstrate:

Existing parcel / ULPIN reference
↓
Building ID
↓
Floor ID
↓
Unit / volumetric property ID

Call this:

PROPOSED VERTICAL ULPIN LINKAGE

Do NOT call it:

official ULPIN generation

unless an authoritative government specification explicitly supports that claim.

---

# TECH STACK

Frontend:

React
TypeScript
MapLibre GL JS
CesiumJS

Backend:

Python
FastAPI
Pydantic

Database:

PostgreSQL
PostGIS

Geospatial:

GeoPandas
Shapely
Rasterio
GDAL
PyProj
PDAL
Open3D

ML:

PyTorch
scikit-learn
XGBoost

3D:

Open3D
trimesh
CesiumJS

Testing:

pytest
Playwright

Code quality:

Ruff
mypy/pyright

---

# MAPS

Use:

OpenStreetMap
+
MapLibre GL JS

For 3D:

CesiumJS

Do NOT scrape Google Maps.

Do NOT scrape Google Street View.

Do NOT use proprietary basemap tiles without checking licence.

OSM attribution must be preserved.

---

# REPOSITORY STRUCTURE

Use:

/apps
/services
/geospatial
/ml
/data
/scripts
/tests
/docs
/.agents
/.claude

Data:

data/raw
data/interim
data/processed
data/manifests
data/provenance

Never commit large raw datasets to Git.

Never commit:

API keys
passwords
tokens
private records
credentials

Use Git LFS or external storage where appropriate.

---

# AGENT LOOP

Execute the project in phases.

PHASE 0
Project constitution

PHASE 1
Dataset discovery

PHASE 2
Dataset download and manifest

PHASE 3
CRS/schema normalization

PHASE 4
Data-quality validation

PHASE 5
Parcel-building matching

PHASE 6
DEM/DSM processing

PHASE 7
Building extraction AI

PHASE 8
Floor evidence and attribute AI

PHASE 9
3D reconstruction

PHASE 10
Data fusion and conflict detection

PHASE 11
3D topology validation

PHASE 12
Confidence and provenance

PHASE 13
Human verification

PHASE 14
Proposed vertical ULPIN linkage

PHASE 15
2D/3D interface

PHASE 16
SIH adversarial review

PHASE 17
Final demo

---

# MOST IMPORTANT RULE

DO NOT START IMPLEMENTING AI.

First prove that the datasets are available.

The FIRST task is:

## DATASET DISCOVERY AUDIT

For Bengaluru Urban, find and verify:

1. Cadastral parcel data
2. DEM
3. DSM
4. Building footprints
5. OSM building data
6. Floor/height attributes
7. AOI boundary
8. Any optional imagery
9. Any optional point-cloud/BIM source

For each dataset produce:

NAME
SOURCE
OFFICIAL URL
DOWNLOAD URL
FORMAT
SIZE
CRS
SPATIAL COVERAGE
RESOLUTION
LICENCE
FREE TO DOWNLOAD? YES/NO
AUTHENTICATION REQUIRED?
PAYMENT REQUIRED?
GOVERNMENT-ONLY?
ATTRIBUTES
LIMITATIONS
DATE
HASH
LOCAL FILE PATH

---

# DATASET GATE

Do not proceed until the following minimum set is verified:

REQUIRED:

✓ Bengaluru cadastral geometry
✓ free DEM
✓ free DSM
✓ free building footprints
✓ free OSM data
✓ free floor/height evidence for at least SOME buildings
✓ AOI boundary

If any required item fails:

STOP.

Do not invent a substitute.

Search for another genuinely free source.

If no legitimate free source exists:

report:

BLOCKED — NO FREE DATA SOURCE

and explain exactly which requirement failed.

---

# AOI SELECTION

After verifying the datasets, find the smallest Bengaluru Urban AOI where:

cadastral coverage
AND
building footprints
AND
DSM
AND
DEM
AND
OSM floor/height evidence

overlap.

Prefer an AOI with:

* many buildings
* multiple building types
* several multi-storey buildings
* at least some OSM floor tags
* clean cadastral boundaries
* minimal missing geometry
* manageable download size

Do NOT select the AOI first and force datasets into it.

Select the AOI AFTER checking dataset intersection.

---

# VERIFICATION

At the end of Phase 1, produce:

docs/DATASET_AUDIT.md

and:

data/manifests/dataset_manifest.csv

and:

docs/AOI_SELECTION.md

The audit must clearly state:

PASS
or
BLOCKED

Do not proceed to Phase 2 unless:

PASS

---

# STOP CONDITIONS

Immediately stop if:

* data is not actually downloadable
* licence is unclear
* source is paid
* access is government-only
* CRS is unknown
* data does not cover Bengaluru Urban
* dataset is not what it claims to be
* DEM is being treated as DSM
* floor count would need to be guessed
* AI labels do not exist
* model evaluation cannot be performed
* legal ownership would be inferred
* official ULPIN would be falsely claimed
* test failure is unexplained

When stopped, explain:

WHAT FAILED
WHY IT FAILED
WHAT WAS VERIFIED
WHAT ALTERNATIVES WERE CHECKED
WHAT DECISION IS REQUIRED

---

# FIRST COMMAND

Start with:

## PHASE 1 — DATASET DISCOVERY AUDIT

Do not write application code yet.

Do not build the frontend yet.

Do not train an AI model yet.

Do not invent missing data.

First prove that Bengaluru Urban is genuinely the best free-data prototype district.

Return the complete dataset audit before proceeding.
