import os, requests, time, json
from dotenv import load_dotenv
load_dotenv()

TOKEN = os.getenv("DISCOGS_TOKEN", "")
HEADERS = {
    "Authorization": f"Discogs token={TOKEN}",
    "User-Agent": "ReleaseTune/1.0 (test)",
}

# 2016年 Japan Single を1ページ取得
resp = requests.get(
    "https://api.discogs.com/database/search",
    headers=HEADERS,
    params={"released": "2016", "country": "Japan", "type": "release",
            "format": "Single", "style": "J-pop", "per_page": 5, "page": 1},
    timeout=15,
)
results = resp.json().get("results", [])
print(f"検索結果: {len(results)} 件")

# 最初の1件だけ詳細取得して released フィールドを確認
if results:
    rid = results[0].get("id")
    print(f"先頭ID: {rid}")
    time.sleep(1.5)
    resp2 = requests.get(f"https://api.discogs.com/releases/{rid}", headers=HEADERS, timeout=15)
    detail = resp2.json()
    print(f"released: {detail.get('released', 'なし')}")
    print(f"title: {detail.get('title', '')}")