import os, requests, time
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("DISCOGS_TOKEN", "")
HEADERS = {
    "Authorization": f"Discogs token={TOKEN}",
    "User-Agent": "ReleaseTune/1.0 (test)",
}

# 欅坂46を直接検索
resp = requests.get(
    "https://api.discogs.com/database/search",
    headers=HEADERS,
    params={"q": "サイレントマジョリティー 欅坂46", "country": "Japan", "type": "release", "per_page": 3},
    timeout=15,
)
results = resp.json().get("results", [])
for r in results:
    print(f"title={r.get('title')} / year={r.get('year')} / id={r.get('id')}")

if results:
    time.sleep(1.5)
    rid = results[0].get("id")
    resp2 = requests.get(f"https://api.discogs.com/releases/{rid}", headers=HEADERS, timeout=15)
    detail = resp2.json()
    print(f"released: {detail.get('released', 'なし')}")