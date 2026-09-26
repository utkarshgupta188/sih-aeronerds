"""
Build Pan-India and Multi-City Search Index for Bhumi Adhaar 3D Portal.
Extracts top structures, wards, and underground infrastructure across all 6 pilot cities,
plus the 36 States/UTs of India for universal Bhu-Aadhaar ULPIN resolution.
"""
import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
DATA_DIR = os.path.join(FRONTEND_DIR, "data")

PILOT_SPECS = {
    "bhopal": {
        "parcels": os.path.join(DATA_DIR, "bhopal_cadastral_parcels.geojson"),
        "buildings": os.path.join(DATA_DIR, "bhopal_buildings_3d.geojson"),
        "state_code": "IN-MP-BHP",
        "city_name": "Bhopal, Madhya Pradesh",
        "state_name": "Madhya Pradesh",
        "authority": "MP Bhulekh / Directorate of Land Records",
        "center": [77.4180, 23.2510],
        "zoom": 17.5
    },
    "bengaluru": {
        "parcels": os.path.join(DATA_DIR, "cadastral_parcels_valid.geojson"),
        "buildings": os.path.join(DATA_DIR, "buildings_3d.geojson"),
        "state_code": "IN-KA-BLR",
        "city_name": "Bengaluru Urban, Karnataka",
        "state_name": "Karnataka",
        "authority": "Karnataka Bhoomi / Revenue Dept",
        "center": [77.6200, 12.9300],
        "zoom": 17.5
    },
    "indore": {
        "parcels": os.path.join(DATA_DIR, "indore_cadastral_parcels.geojson"),
        "buildings": os.path.join(DATA_DIR, "indore_buildings_3d.geojson"),
        "state_code": "IN-MP-IND",
        "city_name": "Indore, Madhya Pradesh",
        "state_name": "Madhya Pradesh",
        "authority": "MP Bhulekh / Indore Development Authority",
        "center": [75.8750, 22.7200],
        "zoom": 17.5
    },
    "navi_mumbai": {
        "parcels": os.path.join(DATA_DIR, "navi_mumbai_cadastral_parcels.geojson"),
        "buildings": os.path.join(DATA_DIR, "navi_mumbai_buildings_3d.geojson"),
        "state_code": "IN-MH-NMU",
        "city_name": "Navi Mumbai, Maharashtra",
        "state_name": "Maharashtra",
        "authority": "MahaBhumi / CIDCO Maharashtra",
        "center": [73.0020, 19.0750],
        "zoom": 17.5
    },
    "mumbai_kalyan": {
        "parcels": os.path.join(DATA_DIR, "mumbai_kalyan_cadastral_parcels.geojson"),
        "buildings": os.path.join(DATA_DIR, "mumbai_kalyan_buildings_3d.geojson"),
        "state_code": "IN-MH-KDN",
        "city_name": "Kalyan-Dombivli / Mumbai MMR, Maharashtra",
        "state_name": "Maharashtra",
        "authority": "MahaBhumi / KDMC Land Records",
        "center": [73.1250, 19.2150],
        "zoom": 17.5
    },
    "coimbatore": {
        "parcels": os.path.join(DATA_DIR, "coimbatore_cadastral_parcels.geojson"),
        "buildings": os.path.join(DATA_DIR, "coimbatore_buildings_3d.geojson"),
        "state_code": "IN-TN-CBE",
        "city_name": "Coimbatore, Tamil Nadu",
        "state_name": "Tamil Nadu",
        "authority": "Tamil Nadu e-District / Survey & Settlement",
        "center": [76.9650, 11.0050],
        "zoom": 17.5
    }
}

# Pan-India 36 States & Union Territories Reference Directory
PAN_INDIA_STATES = [
    {"code": "IN-AN", "lgd": "35", "name": "Andaman and Nicobar Islands", "hi": "अंडमान और निकोबार", "portal": "RevPortal A&N", "center": [92.7350, 11.6670]},
    {"code": "IN-AP", "lgd": "28", "name": "Andhra Pradesh", "hi": "आंध्र प्रदेश", "portal": "Meebhoomi Andhra Pradesh", "center": [80.6480, 16.5062]},
    {"code": "IN-AR", "lgd": "12", "name": "Arunachal Pradesh", "hi": "अरुणाचल प्रदेश", "portal": "Arunachal Land Portal", "center": [93.6053, 27.0844]},
    {"code": "IN-AS", "lgd": "18", "name": "Assam", "hi": "असम", "portal": "Dharitree Assam", "center": [91.7362, 26.1445]},
    {"code": "IN-BR", "lgd": "10", "name": "Bihar", "hi": "बिहार", "portal": "Bihar Bhumi / Revenue Dept", "center": [85.1376, 25.5941]},
    {"code": "IN-CH", "lgd": "04", "name": "Chandigarh", "hi": "चंडीगढ़", "portal": "Chandigarh Land Administration", "center": [76.7794, 30.7333]},
    {"code": "IN-CT", "lgd": "22", "name": "Chhattisgarh", "hi": "छत्तीसगढ़", "portal": "Bhuiyan Chhattisgarh", "center": [81.6296, 21.2514]},
    {"code": "IN-DN", "lgd": "26", "name": "Dadra and Nagar Haveli and Daman and Diu", "hi": "दादरा और नगर हवेली", "portal": "Daman Diu Land Records", "center": [72.8397, 20.4283]},
    {"code": "IN-DL", "lgd": "07", "name": "Delhi (NCT)", "hi": "दिल्ली", "portal": "Delhi Bhulekh / Revenue GIS", "center": [77.2090, 28.6139]},
    {"code": "IN-GA", "lgd": "30", "name": "Goa", "hi": "गोवा", "portal": "Goa Land Records / Form I & XIV", "center": [73.8180, 15.2993]},
    {"code": "IN-GJ", "lgd": "24", "name": "Gujarat", "hi": "गुजरात", "portal": "AnyRoR Gujarat", "center": [72.5714, 23.0225]},
    {"code": "IN-HR", "lgd": "06", "name": "Haryana", "hi": "हरियाणा", "portal": "Jamabandi Haryana", "center": [76.9635, 29.0588]},
    {"code": "IN-HP", "lgd": "02", "name": "Himachal Pradesh", "hi": "हिमाचल प्रदेश", "portal": "Himbhoomi / LRC HP", "center": [77.1734, 31.1048]},
    {"code": "IN-JK", "lgd": "01", "name": "Jammu and Kashmir", "hi": "जम्मू और कश्मीर", "portal": "J&K Land Records / Aapki Zameen", "center": [74.7973, 34.0837]},
    {"code": "IN-JH", "lgd": "20", "name": "Jharkhand", "hi": "झारखंड", "portal": "Jharbhoomi Jharkhand", "center": [85.3096, 23.3441]},
    {"code": "IN-KA", "lgd": "29", "name": "Karnataka", "hi": "कर्नाटक", "portal": "Bhoomi Karnataka", "center": [77.5946, 12.9716]},
    {"code": "IN-KL", "lgd": "32", "name": "Kerala", "hi": "केरल", "portal": "e-Rekha Kerala", "center": [76.9366, 8.5241]},
    {"code": "IN-LA", "lgd": "37", "name": "Ladakh", "hi": "लद्दाख", "portal": "Ladakh Revenue Desk", "center": [77.5771, 34.1526]},
    {"code": "IN-LD", "lgd": "31", "name": "Lakshadweep", "hi": "लक्षद्वीप", "portal": "Lakshadweep Administration", "center": [72.6369, 10.5667]},
    {"code": "IN-MP", "lgd": "23", "name": "Madhya Pradesh", "hi": "मध्य प्रदेश", "portal": "MP Bhulekh / Bhu-Abhilekh", "center": [77.4126, 23.2599]},
    {"code": "IN-MH", "lgd": "27", "name": "Maharashtra", "hi": "महाराष्ट्र", "portal": "MahaBhumi / Mahabhulekh", "center": [72.8777, 19.0760]},
    {"code": "IN-MN", "lgd": "14", "name": "Manipur", "hi": "मणिपुर", "portal": "Loucha Pathap Manipur", "center": [93.9368, 24.8170]},
    {"code": "IN-ML", "lgd": "17", "name": "Meghalaya", "hi": "मेघालय", "portal": "Meghalaya Land Records", "center": [91.8933, 25.5788]},
    {"code": "IN-MZ", "lgd": "15", "name": "Mizoram", "hi": "मिजोरम", "portal": "Mizoram Land Revenue", "center": [92.7176, 23.1645]},
    {"code": "IN-NL", "lgd": "13", "name": "Nagaland", "hi": "नागालैंड", "portal": "Nagaland Land Revenue Portal", "center": [94.1166, 25.6751]},
    {"code": "IN-OD", "lgd": "21", "name": "Odisha", "hi": "ओडिशा", "portal": "Bhulekh Odisha", "center": [85.8245, 20.2961]},
    {"code": "IN-PY", "lgd": "34", "name": "Puducherry", "hi": "पुदुचेरी", "portal": "Nilamagal Puducherry", "center": [79.8083, 11.9416]},
    {"code": "IN-PB", "lgd": "03", "name": "Punjab", "hi": "पंजाब", "portal": "PLRS Punjab Land Records Society", "center": [75.8573, 30.9010]},
    {"code": "IN-RJ", "lgd": "08", "name": "Rajasthan", "hi": "राजस्थान", "portal": "Apna Khata / E-Dharti Rajasthan", "center": [75.7873, 26.9124]},
    {"code": "IN-SK", "lgd": "11", "name": "Sikkim", "hi": "सिक्किम", "portal": "Sikkim Land Revenue", "center": [88.6138, 27.3314]},
    {"code": "IN-TN", "lgd": "33", "name": "Tamil Nadu", "hi": "तमिलनाडु", "portal": "e-Services TN / Patta Chitta", "center": [80.2707, 13.0827]},
    {"code": "IN-TG", "lgd": "36", "name": "Telangana", "hi": "तेलंगाना", "portal": "Dharani Portal Telangana", "center": [78.4867, 17.3850]},
    {"code": "IN-TR", "lgd": "16", "name": "Tripura", "hi": "त्रिपुरा", "portal": "Jami Tripura", "center": [91.2868, 23.8315]},
    {"code": "IN-UP", "lgd": "09", "name": "Uttar Pradesh", "hi": "उत्तर प्रदेश", "portal": "UP Bhulekh / Bor UP", "center": [80.9462, 26.8467]},
    {"code": "IN-UK", "lgd": "05", "name": "Uttarakhand", "hi": "उत्तराखंड", "portal": "Devbhoomi Uttarakhand", "center": [78.0322, 30.3165]},
    {"code": "IN-WB", "lgd": "19", "name": "West Bengal", "hi": "पश्चिम बंगाल", "portal": "BanglarBhumi West Bengal", "center": [88.3639, 22.5726]}
]

def get_feature_centroid(geom):
    if not geom or "coordinates" not in geom:
        return None
    coords = geom["coordinates"]
    pts = []
    gtype = geom.get("type", "")
    if gtype == "Polygon":
        pts = coords[0]
    elif gtype == "MultiPolygon":
        pts = coords[0][0]
    elif gtype == "LineString":
        pts = coords
    if not pts:
        return None
    sx = sum(p[0] for p in pts)
    sy = sum(p[1] for p in pts)
    return [round(sx / len(pts), 5), round(sy / len(pts), 5)]

def build_index():
    catalog_items = []

    # 1. Official Ground-Truth Showcase Items
    showcase = [
        {
            "ulpin": "IN-MP-BHP-P104-B3-FL4",
            "full_ulpin": "IN-MP-BHP-P104-B3-FL4-U402",
            "numeric_ulpin": "23012004001043",
            "title": "Khasra #104/B (Lotus Heights 3D)",
            "sub": "Flat 402, 4th Floor &bull; Ward 42, Bhopal &bull; Owner: Smt. Priya Sharma",
            "city_key": "bhopal",
            "city_name": "Bhopal (MP)",
            "building_id": "osm_way_375220424",
            "parcel_id": "bhopal_ward_42",
            "type": "ulpin",
            "coordinates": [77.4185, 23.2515],
            "floors": "G+5 (RCC)",
            "category": "3D_CADASTRAL_TITLE"
        },
        {
            "ulpin": "IN-KA-BLR-P22068-B101",
            "full_ulpin": "IN-KA-BLR-P22068-B101-FL3",
            "numeric_ulpin": "29012004022068",
            "title": "Survey Plot #22068 (Bengaluru Tech Corridor)",
            "sub": "3rd Floor &bull; Ward 150, Koramangala &bull; Bhoomi Linked &bull; 100% Contained",
            "city_key": "bengaluru",
            "city_name": "Bengaluru (KA)",
            "building_id": "osm_way_93697573",
            "parcel_id": "cadastral_parcel_22068",
            "type": "ulpin",
            "coordinates": [77.6200, 12.9300],
            "floors": "G+4 (Commercial)",
            "category": "3D_CADASTRAL_TITLE"
        },
        {
            "ulpin": "IN-MP-IND-P61-B2001",
            "full_ulpin": "IN-MP-IND-P61-B2001-FL2",
            "numeric_ulpin": "23012004000611",
            "title": "Khasra #61/A (Indore Business Square)",
            "sub": "2nd Floor &bull; Ward 61, Indore &bull; MP Bhulekh Verified &bull; Zero Encroachment",
            "city_key": "indore",
            "city_name": "Indore (MP)",
            "building_id": "bldg_indore_2001",
            "parcel_id": "indore_ward_61",
            "type": "ulpin",
            "coordinates": [75.8750, 22.7200],
            "floors": "G+3 (Mixed Use)",
            "category": "3D_CADASTRAL_TITLE"
        },
        {
            "ulpin": "IN-MH-NMU-P65-B2001",
            "full_ulpin": "IN-MH-NMU-P65-B2001-FL6",
            "numeric_ulpin": "27012004000651",
            "title": "Plot #65 (Navi Mumbai Seawoods Grand Central)",
            "sub": "6th Floor &bull; Ward 65, Nerul &bull; MahaBhumi / CIDCO Approved FSI 2.50",
            "city_key": "navi_mumbai",
            "city_name": "Navi Mumbai (MH)",
            "building_id": "bldg_navi_mumbai_2001",
            "parcel_id": "navi_mumbai_ward_65",
            "type": "ulpin",
            "coordinates": [73.0020, 19.0750],
            "floors": "G+7 (Corporate)",
            "category": "3D_CADASTRAL_TITLE"
        },
        {
            "ulpin": "IN-MH-KDN-P110-B2001",
            "full_ulpin": "IN-MH-KDN-P110-B2001-FL4",
            "numeric_ulpin": "27012004001101",
            "title": "CTS Plot #110 (Kalyan Regency Heights)",
            "sub": "4th Floor &bull; Ward 110, Dombivli East &bull; MahaBhumi CTS Cadastre Verified",
            "city_key": "mumbai_kalyan",
            "city_name": "Kalyan-Dombivli / Mumbai (MH)",
            "building_id": "bldg_mumbai_kalyan_2001",
            "parcel_id": "mumbai_kalyan_ward_110",
            "type": "ulpin",
            "coordinates": [73.1250, 19.2150],
            "floors": "G+5 (Residential)",
            "category": "3D_CADASTRAL_TITLE"
        },
        {
            "ulpin": "IN-TN-CBE-P80-B2001",
            "full_ulpin": "IN-TN-CBE-P80-B2001-FL3",
            "numeric_ulpin": "33012004000801",
            "title": "Town Survey #80/2 (Coimbatore Textile Plaza)",
            "sub": "3rd Floor &bull; Ward 80, Gandhipuram &bull; TN e-District Delineated",
            "city_key": "coimbatore",
            "city_name": "Coimbatore (TN)",
            "building_id": "bldg_coimbatore_2001",
            "parcel_id": "coimbatore_ward_80",
            "type": "ulpin",
            "coordinates": [76.9650, 11.0050],
            "floors": "G+4 (Commercial)",
            "category": "3D_CADASTRAL_TITLE"
        }
    ]
    catalog_items.extend(showcase)

    # 2. Add Underground Infrastructure Items
    ug_path = os.path.join(DATA_DIR, "underground_utilities.geojson")
    if os.path.exists(ug_path):
        with open(ug_path, "r", encoding="utf-8") as f:
            ug_data = json.load(f)
        for feat in ug_data.get("features", []):
            p = feat.get("properties", {})
            u_id = p.get("id")
            sub_ulpin = p.get("proposed_subsurface_ulpin")
            asset_name = p.get("asset_name")
            asset_type = p.get("asset_type")
            depth = p.get("depth_below_ground_m", 5.0)
            jurisdiction = p.get("jurisdiction", "Municipal Infra Authority")
            c = get_feature_centroid(feat.get("geometry"))
            # Determine city key
            ckey = "bhopal"
            if "blr" in str(sub_ulpin).lower() or "bengaluru" in str(asset_name).lower():
                ckey = "bengaluru"
            elif "ind" in str(sub_ulpin).lower() or "indore" in str(asset_name).lower():
                ckey = "indore"
            elif "nmu" in str(sub_ulpin).lower() or "navi_mumbai" in str(asset_name).lower():
                ckey = "navi_mumbai"
            elif "kdn" in str(sub_ulpin).lower() or "kalyan" in str(asset_name).lower():
                ckey = "mumbai_kalyan"
            elif "cbe" in str(sub_ulpin).lower() or "coimbatore" in str(asset_name).lower():
                ckey = "coimbatore"

            catalog_items.append({
                "ulpin": sub_ulpin,
                "full_ulpin": sub_ulpin,
                "numeric_ulpin": "IN-SUB-" + str(u_id).upper(),
                "title": f"Subsurface Corridor: {asset_name}",
                "sub": f"{asset_type} &bull; Depth: -{depth}m MSL &bull; {jurisdiction}",
                "city_key": ckey,
                "city_name": PILOT_SPECS[ckey]["city_name"],
                "building_id": u_id,
                "parcel_id": p.get("parent_parcel_id", "ROW_PARCEL"),
                "type": "subsurface",
                "coordinates": c or PILOT_SPECS[ckey]["center"],
                "floors": f"Subsurface Depth: -{depth}m",
                "category": "UNDERGROUND_INFRASTRUCTURE"
            })

    # 3. Sample 20 representative buildings from each of the 6 pilot cities
    for ckey, spec in PILOT_SPECS.items():
        bpath = spec["buildings"]
        if not os.path.exists(bpath):
            continue
        with open(bpath, "r", encoding="utf-8") as f:
            bdata = json.load(f)

        step = max(1, len(bdata.get("features", [])) // 25)
        for idx in range(0, min(len(bdata.get("features", [])), 25 * step), step):
            feat = bdata["features"][idx]
            p = feat.get("properties", {})
            b_id = str(p.get("id", ""))
            parcel_id = str(p.get("linked_parcel_id", ""))
            b_num = re.sub(r"\D", "", b_id) or str(idx + 1)
            p_num = re.sub(r"\D", "", parcel_id) or "01"
            ulpin = f"{spec['state_code']}-P{p_num}-B{b_num}"
            name = p.get("name") or f"Cadastral Structure #{b_id}"
            levels = p.get("building_levels") or p.get("derived_floors") or 3
            height = p.get("height_m") or p.get("building_height_m") or 10.5
            c = get_feature_centroid(feat.get("geometry")) or spec["center"]

            catalog_items.append({
                "ulpin": ulpin,
                "full_ulpin": f"{ulpin}-FL{levels}",
                "numeric_ulpin": f"{spec['state_code'].replace('-', '')}{p_num.zfill(4)}{b_num.zfill(4)}",
                "title": f"{name} ({spec['city_name'].split(',')[0]})",
                "sub": f"Khasra/Parcel: {parcel_id} &bull; Floors: G+{levels} ({height}m) &bull; {spec['authority'].split('/')[0]}",
                "city_key": ckey,
                "city_name": spec["city_name"],
                "building_id": b_id,
                "parcel_id": parcel_id,
                "type": "geojson",
                "coordinates": c,
                "floors": f"G+{levels} Floors",
                "category": "3D_BUILDING_PARCEL"
            })

    output_payload = {
        "metadata": {
            "total_items": len(catalog_items),
            "pilot_cities": list(PILOT_SPECS.keys()),
            "pan_india_states_count": len(PAN_INDIA_STATES)
        },
        "pilot_records": catalog_items,
        "pan_india_states": PAN_INDIA_STATES
    }

    out_file = os.path.join(DATA_DIR, "pan_india_catalog.json")
    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(output_payload, f, indent=2, ensure_ascii=False)
    print(f"Generated {out_file} with {len(catalog_items)} indexed items and {len(PAN_INDIA_STATES)} states.")

if __name__ == "__main__":
    build_index()
