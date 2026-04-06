import requests, time

def find_artist(name):
    resp = requests.get(
        "https://itunes.apple.com/search",
        params={"term": name, "country": "JP", "media": "music",
                "entity": "musicArtist", "limit": 5},
        timeout=10,
    )
    results = resp.json().get("results", [])
    print(f"\n「{name}」の検索結果:")
    for r in results[:3]:
        print(f"  id={r['artistId']:12}  {r['artistName']:<30}  genre={r.get('primaryGenreName','')}")
    time.sleep(0.5)

find_artist("Vaundy")
find_artist("ちゃんみな")
find_artist("Mrs.GREEN APPLE")