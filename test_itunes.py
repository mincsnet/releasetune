"""
test_itunes.py — iTunes Search API 動作確認
欅坂46のシングル一覧・リリース日・ジャケットが取れるか確認する
"""
import requests, json

def itunes_get_artist_singles(artist_name: str, country: str = "JP", limit: int = 20):
    """
    アーティスト名でiTunes Search APIを叩き、
    シングル（コレクション）一覧を返す
    """
    # まずアーティストIDを取得
    resp = requests.get(
        "https://itunes.apple.com/search",
        params={
            "term":    artist_name,
            "country": country,
            "media":   "music",
            "entity":  "musicArtist",
            "limit":   5,
        },
        timeout=10,
    )
    artists = resp.json().get("results", [])
    if not artists:
        print(f"アーティストが見つかりません: {artist_name}")
        return []

    artist_id = artists[0]["artistId"]
    artist_found = artists[0]["artistName"]
    print(f"アーティスト: {artist_found} (id={artist_id})")

    # アーティストIDでアルバム（シングル含む）一覧を取得
    resp2 = requests.get(
        "https://itunes.apple.com/lookup",
        params={
            "id":      artist_id,
            "country": country,
            "entity":  "album",   # album に single も含まれる
            "limit":   limit,
        },
        timeout=10,
    )
    results = resp2.json().get("results", [])

    # 先頭はアーティスト情報なのでスキップ
    albums = [r for r in results if r.get("wrapperType") == "collection"]
    return albums


# テスト実行
artist = "欅坂46"
print(f"=== {artist} のシングル一覧 ===\n")
albums = itunes_get_artist_singles(artist, limit=50)

print(f"\n取得件数: {len(albums)} 件")
print()
for a in albums:
    print(f"  {a.get('releaseDate','')[:10]}  {a.get('collectionName','')}")
    print(f"    ジャケット: {a.get('artworkUrl100','')[:60]}...")
    print(f"    Apple Music: {a.get('collectionViewUrl','')[:60]}...")
    print()