import os
import time
import requests

NOTION_TOKEN = os.environ.get("NOTION_TOKEN")
UTOMUNKA_DB_ID = os.environ.get("UTOMUNKA_DB_ID")
VAGOK_DB_ID = os.environ.get("VAGOK_DB_ID")

HEADERS = {
    "Authorization": f"Bearer {NOTION_TOKEN}",
    "Notion-Version": "2022-06-28",
    "Content-Type": "application/json"
}

def get_main_entries():
    url = f"https://api.notion.com/v1/databases/{UTOMUNKA_DB_ID}/query"
    payload = {
        "filter": {
            "and": [
                {
                    "property": "Állapot",
                    "status": {
                        "equals": "Ellenőrzés"
                    }
                },
                {
                    "property": "jóváírva",
                    "checkbox": {
                        "equals": False
                    }
                }
            ]
        }
    }
    response = requests.post(url, headers=HEADERS, json=payload)
    data = response.json()
    
    if "results" not in data:
        print("❌ Nincs találat vagy hiba:", data)
        return []
    
    return data["results"]



def get_vago_id_by_person_name(name):
    url = f"https://api.notion.com/v1/databases/{VAGOK_DB_ID}/query"
    response = requests.post(url, headers=HEADERS)
    results = response.json().get("results", [])

    for item in results:
        try:
            vago_name = item["properties"]["Person"]["people"][0]["name"]
            if vago_name.strip().lower() == name.strip().lower():
                return item["id"]
        except (KeyError, IndexError):
            continue

    return None


def get_current_project_points(vago_page_id):
    url = f"https://api.notion.com/v1/pages/{vago_page_id}"
    res = requests.get(url, headers=HEADERS)
    return res.json()["properties"]["projekt pont"]["number"]

def update_project_points(vago_page_id, new_total):
    url = f"https://api.notion.com/v1/pages/{vago_page_id}"
    payload = {
        "properties": {
            "projekt pont": {
                "number": new_total
            }
        }
    }
    res = requests.patch(url, headers=HEADERS, json=payload)
    return res.status_code == 200

def mark_as_processed(UTOMUNKA_DB_ID):
    url = f"https://api.notion.com/v1/pages/{UTOMUNKA_DB_ID}"
    payload = {
        "properties": {
            "jóváírva": {
                "checkbox": True
            }
        }
    }
    requests.patch(url, headers=HEADERS, json=payload)

def main():
    print("🔁 Új jóváírás ellenőrzés...")
    entries = get_main_entries()
    print(f"📄 Feldolgozandó elemek: {len(entries)}")
    


    for entry in entries:
        page_id = entry["id"]
        try:
            name = entry["properties"]["Aki ellenőrzésbe tette 1"]["people"][0]["name"]
            points = entry["properties"]["jóváirandó pont"]["number"]
        except (KeyError, IndexError, TypeError):
            print(f"❗ Hiányos adat: {entry['id']} - ellenőrzést végző: {entry['properties'].get('ellenőrzést végző')}, pont: {entry['properties'].get('jóváírandó pont')}")
            continue

        vago_id = get_vago_id_by_person_name(name)
        if not vago_id:
            print(f"❌ Nincs vágó találat: {name}")
            continue

        current_points = get_current_project_points(vago_id)
        if current_points is None:
            current_points = 0  # ha még nincs érték, akkor 0-ról indul

        new_total = current_points + points

        updated = update_project_points(vago_id, new_total)

        if updated:
            print(f"✅ {name} pont frissítve: {current_points} → {new_total}")
            mark_as_processed(page_id)
        else:
            print(f"⚠️ Nem sikerült frissíteni: {name}")

if __name__ == "__main__":
    while True:
        main()
        time.sleep(300)
