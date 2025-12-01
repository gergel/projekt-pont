import os
import time
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
MAIN_DB_ID = "1e7c9afdd53b809bbbe3d6aafae6fdc6"
CUTTERS_DB_ID = "e23876f7f17b4fcbac6352b63303c7c8"

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# ----------------------------------------------------
#  Helper: név átalakítás
# ----------------------------------------------------
def normalize_main_name(name_raw: str) -> str:
    """
    MAIN DB: @John Doe  →  John Doe  → Doe John
    """
    if not name_raw:
        return ""

    # @ levágása
    if name_raw.startswith("@"):
        name_raw = name_raw[1:]

    parts = name_raw.strip().split()

    if len(parts) == 1:
        return parts[0]

    # John Doe → Doe John
    first = parts[0]
    last = " ".join(parts[1:])
    return f"{last} {first}".strip()


# ----------------------------------------------------
# Lekérjük a cutters név → pageID lookupot
# ----------------------------------------------------
def load_cutters_lookup():
    url = f"https://api.notion.com/v1/databases/{CUTTERS_DB_ID}/query"
    lookup = {}

    has_more = True
    cursor = None

    while has_more:
        payload = {}
        if cursor:
            payload["start_cursor"] = cursor

        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()
        results = data.get("results", [])

        for row in results:
            try:
                full_name = row["properties"]["Full Name"]["title"][0]["plain_text"].strip()
                lookup[full_name.lower()] = row["id"]
            except:
                continue

        cursor = data.get("next_cursor")
        has_more = data.get("has_more", False)

    return lookup


# ----------------------------------------------------
# Main DB lekérése
# ----------------------------------------------------
def load_main_entries():
    url = f"https://api.notion.com/v1/databases/{MAIN_DB_ID}/query"

    all_results = []
    payload = {}

    while True:
        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()

        if "results" not in data:
            print("❌ Lekérési hiba:", data)
            break

        all_results.extend(data["results"])

        if data.get("has_more"):
            payload["start_cursor"] = data["next_cursor"]
        else:
            break

    return all_results


# ----------------------------------------------------
# Relations frissítése
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
    print("🔁 Vágó kapcsolatok frissítése...")

    cutters = load_cutters_lookup()
    print(f"📄 Cutter nevekből betöltve: {len(cutters)} db")

    main_entries = load_main_entries()
    print(f"📄 Main DB sorok: {len(main_entries)} db")

    linked = 0
    missing = 0

    for row in main_entries:
        page_id = row["id"]
        try:
            raw_name = row["properties"]["Name"]["title"][0]["plain_text"]
        except:
            print(f"⚠️ Nincs Name mező: {page_id}")
            continue

        normalized = normalize_main_name(raw_name)
        normalized_key = normalized.lower()

        if normalized_key in cutters:
            cutter_id = cutters[normalized_key]
            ok = update_relation(page_id, cutter_id)
            if ok:
                linked += 1
                print(f"✅ {raw_name}  →  {normalized} (match) – relation frissítve")
            else:
                print(f"❌ Nem sikerült frissíteni: {raw_name}")
        else:
            missing += 1
            print(f"❗ Nincs egyezés: {raw_name}  → {normalized}")

    print(f"🔚 Kész! Kapcsolva: {linked}, nem talált egyezés: {missing}")


# ----------------------------------------------------
# Loop a Railway-hez
# ----------------------------------------------------
if __name__ == "__main__":
    while True:
        main()
        time.sleep(300)
