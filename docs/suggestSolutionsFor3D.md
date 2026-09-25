# Upgrading to Complete 3D Structures (LOD2 / LOD3)

This document outlines why the current BoundaryLens prototype generates flat-topped "massing blocks" and provides a roadmap for sourcing and implementing fully detailed 3D architectural models.

---

## 1. Why is the Current 3D "Flat"?

The current BoundaryLens prototype implements **LOD1 (Level of Detail 1)** 3D massing. 

**The Limitation:**
1. **Data:** We only have a 2D building footprint (from OpenStreetMap) and a single scalar height value (extracted via our DSM - DEM pipeline). We do not have geometric data for roofs, walls, or architectural features.
2. **Rendering:** MapLibre GL JS uses the `fill-extrusion` layer type. Mathematically, this simply takes a 2D polygon and extrudes it straight up along the Z-axis to a single height. It cannot render pitched roofs, domes, windows, or overhangs.

---

## 2. Solutions: Where to Find True 3D Data

To render complete 3D structures (LOD2/LOD3), we need fundamentally different data types: **Meshes (glTF), Point Clouds (LiDAR), or 3D Tiles.**

Here is where we can source this data for the SIH26011 context:

### A. Open & Global 3D Datasets
* **Overture Maps Foundation (3D Buildings):** Overture is beginning to release 3D building data that includes roof shapes (LOD2) derived from AI and photogrammetry.
* **Google Photorealistic 3D Tiles:** Google provides an API to stream their high-resolution Google Earth 3D mesh directly into web apps (requires an API key).

### B. Indian Government / Authoritative Datasets
* **SVAMITVA Scheme Drone Surveys:** The Survey of India (SoI) has been conducting high-resolution drone mapping of villages. This photogrammetry data can generate highly accurate 3D meshes and point clouds.
* **Bhuvan 3D / NRSC:** ISRO's Bhuvan platform has 3D city models for select tier-1 cities (like Bengaluru and Hyderabad). Getting access requires formal requests through government channels.
* **Smart Cities Mission / Municipal BIM Data:** Local Urban Local Bodies (ULBs) often mandate BIM (Building Information Modeling) submissions for new large-scale commercial developments. These IFC/Revit files contain exact 3D structural data.

### C. Commercial / Synthetic Generation
* **Procedural Generation (Synthetic LOD2):** If we know the roof type (e.g., tagged `roof:shape=gabled` in OSM), we could write a script to mathematically generate a 3D sloped roof mesh on top of the flat footprint. 

---

## 3. Implementation Path: How to Render True 3D

If we obtain true 3D data (e.g., BIM files from a municipality, or 3D Tiles from a drone survey), our tech stack must evolve.

### Step 1: Format Conversion
We cannot use GeoJSON for complex 3D. The data must be converted into **3D Tiles (OGC Standard)** or **glTF/glb** models.
* *Tooling:* Use `Cesium ion` to tile large photogrammetry datasets, or tools like `Blender` and `IfcConvert` to turn BIM files into lightweight web-ready `.gltf` meshes.

### Step 2: Upgrading the Rendering Engine
MapLibre GL JS `fill-extrusion` is insufficient. We must migrate the map frontend to one of the following true WebGL 3D globes:

1. **CesiumJS (Recommended)**
   * *Why:* The industry standard for geospatial 3D. It natively supports 3D Tiles, BIM overlays, and precise geospatial positioning. It is open-source.
   * *Integration:* We would load our 2D Parcels via GeoJSON, and overlay the 3D buildings as a `Cesium3DTileset`.
2. **Three.js + Mapbox/MapLibre**
   * *Why:* Three.js can be integrated into MapLibre as a custom WebGL layer, allowing you to spawn `.gltf` models (like a detailed BIM model of an apartment complex) at specific Longitude/Latitude coordinates.
3. **Mapbox GL JS (v3)**
   * *Why:* Mapbox's newer proprietary versions have built-in support for loading 3D models (`model` layer type). However, it is not strictly open-source like MapLibre.

### Step 3: Linkage (The ULPIN)
The core of SIH26011 remains. Even with a beautiful 3D mesh, the system must link the mesh to the legal entity.
* The 3D Tile or glTF model metadata must include the `building_id`.
* When the user clicks the 3D mesh in CesiumJS, the frontend queries our `evidence_fusion_ledger.json` to prove that the 3D mesh sits entirely inside the legal Cadastral Parcel boundary.
