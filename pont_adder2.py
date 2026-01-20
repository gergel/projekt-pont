import os
import time
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
MAIN_DB_ID = "1e7c9afdd53b809bbbe3d6aafae6fdc6"
CUTTERS_DB_ID = "e23876f7f17b4fcbac6352b63303c7c8"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type":  "application/json"
}

# ----------------------------------------------------
#  Helper:  név átalakítás
# ----------------------------------------------------
def normalize_main_name(name_raw:  str) -> str:
    """
    MAIN DB:  @John Doe  →  John Doe  → Doe John (surname first)
    SPECIÁLIS:  Diána Dombi → Dombi Dia
    """
    if not name_raw:
        return ""

    if name_raw.startswith("@"):
        name_raw = name_raw[1:]

    name_clean = name_raw.strip()
    
    # SPECIÁLIS ESET: Diána Dombi → Dombi Dia
    if "diána" in name_clean.lower() and "dombi" in name_clean.lower():
        return "Dombi Dia"

    parts = name_clean.split()

    if len(parts) == 1:
        return parts[0]

    first = parts[0]
    last = " ".join(parts[1:])
    return f"{last} {first}".strip()


# ----------------------------------------------------
# Lekérjük a CUTTERS DB lookup táblát
# ----------------------------------------------------
def load_cutters_lookup():
    url = f"https://api.notion.com/v1/databases/{CUTTERS_DB_ID}/query"
    lookup = {}
    cursor = None
    has_more = True

    while has_more:
        payload = {}
        if cursor:
            payload["start_cursor"] = cursor

        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()

        for row in data.get("results", []):
            try:
                full_name = row["properties"]["Full Name"]["title"][0]["plain_text"]. strip()
                lookup[full_name. lower()] = row["id"]
            except: 
                continue

        cursor = data.get("next_cursor")
        has_more = data.get("has_more", False)

    return lookup


# ----------------------------------------------------
# MAIN DB lekérése – csak azok ahol még nincs kapcsolat! 
# ----------------------------------------------------
def load_main_entries_without_relation():
    """
    Csak olyan MAIN DB sorokat ad vissza,
    ahol a 'Vágó' relation jelenleg ÜRES. 
    """
    url = f"https://api.notion.com/v1/databases/{MAIN_DB_ID}/query"

    all_rows = []
    cursor = None
    has_more = True

    while has_more:
        payload = {
            "filter": {
                "property": "Vágó",
                "relation": { "is_empty": True }
            }
        }

        if cursor:
            payload["start_cursor"] = cursor

        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()

        if "results" not in data:
            print("❌ Lekérési hiba:", data)
            break

        all_rows.extend(data["results"])

        cursor = data.get("next_cursor")
        has_more = data.get("has_more", False)

    return all_rows


# ----------------------------------------------------
# Relation frissítése
# ----------------------------------------------------
def update_relation(page_id, cutter_page_id):
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {
        "properties": {
            "Vágó": {
                "relation": [{"id": cutter_page_id}]
            }
        }
    }
    res = requests.patch(url, headers=HEADERS, json=payload)
    return res.status_code == 200


# ----------------------------------------------------
# MAIN LOGIC
# ----------------------------------------------------
def main():
    print("🔁 Vágó kapcsolatok frissítése (csak új elemek)...")

    cutters = load_cutters_lookup()
    print(f"📄 Összes vágó betöltve: {len(cutters)} db")

    main_entries = load_main_entries_without_relation()
    print(f"📄 MAIN DB — Kapcsolat nélküli elemek: {len(main_entries)} db")

    linked = 0
    missing = 0

    for row in main_entries:
        page_id = row["id"]

        try:
            raw_name = row["properties"]["Name"]["title"][0]["plain_text"]
        except:
            print(f"⚠️ Nincs Name mező:  {page_id}")
            continue

        normalized = normalize_main_name(raw_name)
        normalized_key = normalized.lower()

        if normalized_key in cutters:
            cutter_id = cutters[normalized_key]
            if update_relation(page_id, cutter_id):
                linked += 1
                print(f"✅ {raw_name}  →  {normalized} – kapcsolat frissítve!")
            else:
                print(f"❌ Nem sikerült frissíteni:  {raw_name}")
        else:
            missing += 1
            print(f"❗ Nincs egyezés: {raw_name}  →  {normalized}")

    print(f"\n🔚 Kész!  Új kapcsolatok: {linked}, nem talált egyezés: {missing}\n")


# ----------------------------------------------------
# Railway Loop
# ----------------------------------------------------
if __name__ == "__main__":
    while True:
        main()
        time.sleep(300)
