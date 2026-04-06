"""
test_collect.py — ReleaseTune 動作確認スクリプト
==================================================
特定の年・月日に絞って Discogs からデータを取得し、
tracks.json に保存するテスト。

使い方:
  python3 test_collect.py

設定:
  TARGET_DATE  : 収集する月日（MM-DD 形式）
  TARGET_YEARS : 収集する年のリスト（テストなので1〜3年程度）
  MAX_PAGES    : 1年あたりの最大取得ページ数（1ページ=100件）
"""

import os, json, time, re
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

# ── 設定 ──────────────────────────────────────────────────────
TARGET_DATE  = "04-06"        # 収集する月日
TARGET_YEARS = [2014, 2015, 2016, 2017, 2018]  # テスト対象年
MAX_PAGES    = 2              # 1年あたり最大2ページ（200件）まで

DATA_FILE    = Path("data/tracks.json")

TOKEN = os.getenv("DISCOGS_TOKEN", "")
HEADERS = {
    "Authorization": f"Discogs token={TOKEN}",
    "User-Agent":    "ReleaseTune/1.0 (your@email.com)",  # ← 自分のメアドに変更
}
SLEEP = 1.2   # Discogs レートリミット対策

# ── Discogs 検索 ──────────────────────────────────────────────
def search_by_year(year: int, mmdd: str) -> list[dict]:
    """
    released=YYYY&country=Japan で検索し、
    詳細の released フィールドが YYYY-MM-DD のものだけ返す。
    """
    matched = []
    for page in range(1, MAX_PAGES + 1):
        params = {
            "released": str(year),
            "country":  "Japan",
            "type":     "release",
            "format":   "Single",   # シングルのみ
            "style":    "J-pop",    # J-popに絞る（外すと全ジャンル）
            "per_page": 100,
            "page":     page,
        }
        try:
            resp = requests.get(
                "https://api.discogs.com/database/search",
                headers=HEADERS, params=params, timeout=15,
            )
            resp.raise_for_status()
            data    = resp.json()
            results = data.get("results", [])
            pages   = data.get("pagination", {}).get("pages", 1)
            time.sleep(SLEEP)
        except requests.RequestException as e:
            print(f"  [!] {year} p{page} 検索エラー: {e}")
            break

        if not results:
            break

        print(f"  {year} p{page}/{min(pages, MAX_PAGES)}: {len(results)} 件取得")

        for r in results:
            detail = get_release_detail(r.get("id"))
            if not detail:
                continue
            rel_date = detail.get("released", "")
            if len(rel_date) == 10 and rel_date[5:10] == mmdd:
                title  = detail.get("title", "")
                artists = detail.get("artists", [{}])
                artist  = artists[0].get("name", "") if artists else ""
                # "アーティスト – タイトル" 形式を分割
                if " – " in title:
                    parts  = title.split(" – ", 1)
                    artist = parts[0].strip()
                    title  = parts[1].strip()
                artist = re.sub(r"\s*\([^)]*\)\s*$", "", artist).strip()
                print(f"  ✓ {rel_date}  {artist} 「{title}」")
                matched.append({
                    "detail": detail,
                    "title":  title,
                    "artist": artist,
                    "releaseDate": rel_date,
                })

        if page >= pages:
            break

    return matched


def get_release_detail(release_id) -> dict | None:
    if not release_id:
        return None
    try:
        resp = requests.get(
            f"https://api.discogs.com/releases/{release_id}",
            headers=HEADERS, timeout=15,
        )
        resp.raise_for_status()
        time.sleep(SLEEP)
        return resp.json()
    except requests.RequestException as e:
        print(f"  [!] 詳細取得エラー {release_id}: {e}")
        return None


# ── iTunes Search API（ジャケット＋Apple Music） ──────────────
def itunes_search(title: str, artist: str) -> dict | None:
    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={
                "term":    f"{artist} {title}",
                "country": "JP",
                "media":   "music",
                "entity":  "song",
                "limit":   5,
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        time.sleep(0.3)
        if not results:
            return None
        for r in results:
            if artist.lower() in r.get("artistName", "").lower():
                return r
        return results[0]
    except Exception:
        return None


# ── データ保存 ────────────────────────────────────────────────
def save_to_json(tracks: list[dict], mmdd: str) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing = {}
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            existing = json.load(f)

    current     = existing.get(mmdd, [])
    current_ids = {t["id"] for t in current}
    added = 0

    for t in tracks:
        if t["id"] not in current_ids:
            current.append(t)
            current_ids.add(t["id"])
            added += 1

    existing[mmdd] = current

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ {added} 件追加（{mmdd} 合計 {len(current)} 件）→ {DATA_FILE}")


# ── メイン ────────────────────────────────────────────────────
def main():
    mmdd = TARGET_DATE
    month, day = map(int, mmdd.split("-"))

    print(f"{'='*52}")
    print(f"📅  {month}月{day}日 のテスト収集")
    print(f"    対象年: {TARGET_YEARS}")
    print(f"    スタイル: J-pop / フォーマット: Single")
    print(f"{'='*52}\n")

    all_tracks = []

    for year in TARGET_YEARS:
        print(f"\n── {year}年 ──")
        matched = search_by_year(year, mmdd)

        for m in matched:
            title  = m["title"]
            artist = m["artist"]
            detail = m["detail"]

            # iTunes でジャケット・Apple Musicリンク取得
            itunes     = itunes_search(title, artist)
            jacket_url = ""
            apple_url  = ""
            if itunes:
                jacket_url = itunes.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
                apple_url  = itunes.get("trackViewUrl", "")

            # Spotify・YouTube・Amazon は検索URL（テストのため簡易版）
            q = requests.utils.quote(f"{artist} {title}")
            spotify_url = f"https://open.spotify.com/search/{q}"
            youtube_url = f"https://www.youtube.com/results?search_query={requests.utils.quote(artist+' '+title+' 公式')}"
            amazon_url  = f"https://music.amazon.co.jp/search/{q}"

            track = {
                "id":           str(detail.get("id", "")),
                "title":        title,
                "artist":       artist,
                "releaseDate":  m["releaseDate"],
                "note":         "",          # 本番では Wikipedia から取得
                "jacket":       jacket_url,
                "color":        "#c8a84b",
                "links": {
                    "spotify":  spotify_url,
                    "apple":    apple_url,
                    "youtube":  youtube_url,
                    "amazon":   amazon_url,
                },
                "source":       "discogs",
                "noteVerified": False,
            }
            all_tracks.append(track)

        time.sleep(2)

    # 結果サマリ
    print(f"\n{'='*52}")
    print(f"取得結果: {len(all_tracks)} 件")
    for t in all_tracks:
        print(f"  {t['releaseDate']}  {t['artist']} 「{t['title']}」")
    print(f"{'='*52}")

    # JSON に保存
    if all_tracks:
        save_to_json(all_tracks, mmdd)
    else:
        print("\nヒットなし。TARGET_YEARS や style パラメータを調整してみてください。")

    print("\n✨ テスト完了！")


if __name__ == "__main__":
    main()