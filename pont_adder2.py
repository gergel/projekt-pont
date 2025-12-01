import os
import time
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
DB1_ID = os.environ.get("DB1_ID")   # 1e7c9afdd53b809bbbe3d6aafae6fdc6
DB2_ID = os.environ.get("DB2_ID")   # e23876f7f17b4fcbac6352b63303c7c8

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

# ------------------ HELPER: Query teljes adatbázis ------------------
def query_database(db_id):
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    results = []
    payload = {}

    while True:
        res = requests.post(url, headers=HEADERS, json=payload)
        data = res.json()

        if "results" not in data:
            print("❌ Hiba a lekérdezésnél:", data)
            break

        results.extend(data["results"])

        if data.get("has_more"):
            payload["start_cursor"] = data["next_cursor"]
        else:
            break

    return results

# ------------------ DB2 Lookup készítése ------------------
# DB2: Full Name → Page ID
def build_db2_lookup():
    lookup = {}
    rows = query_database(DB2_ID)

    for row in rows:
        try:
            full_name = row["properties"]["Full Name"]["title"][0]["plain_text"].strip()
            lookup[full_name.lower()] = row["id"]
        except (KeyError, IndexError, TypeError):
            continue

    print(f"📄 DB2 név-mapping kész: {len(lookup)} név")
    return lookup

# ------------------ DB1 bejárása + linkelés ------------------
def link_editors(db2_lookup):
    rows = query_database(DB1_ID)
    print(f"📄 DB1 sorok száma: {len(rows)}")

    updated = 0
    skipped = 0

    for row in rows:
        page_id = row["id"]

        # ---- 1) Name mező kinyerése DB1-ből ----
        try:
            raw_name = row["properties"]["Name"]["title"][0]["plain_text"].strip()
        except (KeyError, IndexError, TypeError):
            print(f"⚠️ Hiányzó Name mező: {page_id}")
            continue

        # Elől a @ eltávolítása
        name_clean = raw_name.lstrip("@").strip().lower()

        # ---- 2) Megnézzük, hogy benne van-e DB2-ben ----
        if name_clean not in db2_lookup:
            print(f"❌ Nincs egyezés DB2-ben: {raw_name}")
            skipped += 1
            continue

        target_id = db2_lookup[name_clean]

        # ---- 3) Kapcsolat frissítése a Vágó mezőben ----
        update_payload = {
            "properties": {
                "Vágó": {
                    "relation": [{"id": target_id}]
                }
            }
        }

        url = f"https://api.notion.com/v1/pages/{page_id}"
        res = requests.patch(url, headers=HEADERS, json=update_payload)

        if res.status_code == 200:
            updated += 1
            print(f"✅ Linkelve: {raw_name} → {target_id}")
        else:
            print(f"⚠️ Sikertelen frissítés: {raw_name}, hiba: {res.text}")

    print(f"\n🔚 Összegzés: {updated} frissítve, {skipped} kihagyva.")

# ------------------ MAIN LOOP ------------------
def main():
    print("🔁 Név-összekapcsolás indul...")
    db2_lookup = build_db2_lookup()
    link_editors(db2_lookup)

if __name__ == "__main__":
    while True:
        main()
        time.sleep(300)
