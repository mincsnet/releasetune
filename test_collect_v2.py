"""
test_collect_v2.py — アーティストリスト方式テスト
====================================================
アーティスト名 → Discogs でアーティストID検索
→ ディスコグラフィー取得
→ released が指定月日のシングルを抽出
→ iTunes でジャケット・Apple Musicリンク取得
→ data/tracks.json に保存

使い方:
  python3 test_collect_v2.py

設定:
  TARGET_DATE : 収集する月日（MM-DD）
"""

import os, json, time, re
from pathlib import Path
from dotenv import load_dotenv
import requests

load_dotenv()

# ── 設定 ──────────────────────────────────────────────────────
TARGET_DATE = "04-06"   # 収集する月日

# 収集対象アーティスト（テスト用・20組）
ARTISTS = [
    "スピッツ",
    "Mr.Children",
    "SMAP",
    "AKB48",
    "嵐",
    "サザンオールスターズ",
    "B'z",
    "宇多田ヒカル",
    "浜崎あゆみ",
    "欅坂46",
    "乃木坂46",
    "Official髭男dism",
    "King Gnu",
    "米津玄師",
    "あいみょん",
    "back number",
    "RADWIMPS",
    "いきものがかり",
    "関ジャニ∞",
    "Hey! Say! JUMP",
]

DATA_FILE = Path("data/tracks.json")

TOKEN = os.getenv("DISCOGS_TOKEN", "")
HEADERS = {
    "Authorization": f"Discogs token={TOKEN}",
    "User-Agent":    "ReleaseTune/1.0 (your@email.com)",
}
SLEEP = 1.2


# ── Discogs: アーティストID検索 ───────────────────────────────
def find_artist_id(name: str) -> int | None:
    """アーティスト名から Discogs の artist ID を取得"""
    try:
        resp = requests.get(
            "https://api.discogs.com/database/search",
            headers=HEADERS,
            params={"q": name, "type": "artist", "per_page": 5},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        time.sleep(SLEEP)
    except requests.RequestException as e:
        print(f"  [!] アーティスト検索エラー: {e}")
        return None

    if not results:
        print(f"  [!] 見つかりません: {name}")
        return None

    # 最もスコアが高い（=先頭）を採用
    artist_id = results[0].get("id")
    found_name = results[0].get("title", "")
    print(f"  → {name} = {found_name} (id={artist_id})")
    return artist_id


# ── Discogs: ディスコグラフィー取得 ──────────────────────────
def get_discography(artist_id: int, mmdd: str) -> list[dict]:
    """
    アーティストIDからリリース一覧を取得し、
    released が MM-DD に一致するシングルを返す。
    """
    matched = []
    page = 1
    while True:
        try:
            resp = requests.get(
                f"https://api.discogs.com/artists/{artist_id}/releases",
                headers=HEADERS,
                params={
                    "sort":     "year",
                    "sort_order": "asc",
                    "per_page": 100,
                    "page":     page,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data     = resp.json()
            releases = data.get("releases", [])
            pages    = data.get("pagination", {}).get("pages", 1)
            time.sleep(SLEEP)
        except requests.RequestException as e:
            print(f"  [!] ディスコグラフィー取得エラー: {e}")
            break

        if not releases:
            break

        for r in releases:
            # type=master はオリジナルリリース、release は個別プレス
            # シングルに絞る（role が Main のもの）
            if r.get("role") != "Main":
                continue
            r_type = r.get("type", "")    # "master" or "release"
            r_format = r.get("format", "") # "Single" など（masterには含まれないことも）

            # 詳細を取得してリリース日を確認
            detail = get_release_detail_by_type(r, r_type)
            if not detail:
                continue

            rel_date = detail.get("released", "") or detail.get("date", "")
            if not rel_date or len(rel_date) < 7:
                continue

            if rel_date[5:7] + "-" + rel_date[8:10] != mmdd:
                continue

            # シングルかどうか確認
            formats = detail.get("formats", [])
            is_single = any(
                "Single" in (f.get("name", "") + " ".join(f.get("descriptions", [])))
                for f in formats
            )
            if not is_single and r_type != "master":
                continue

            # タイトル・アーティスト名を整形
            title = detail.get("title", "")
            artists_list = detail.get("artists", [{}])
            artist_name = artists_list[0].get("name", "") if artists_list else ""
            if " – " in title:
                parts = title.split(" – ", 1)
                artist_name = parts[0].strip()
                title = parts[1].strip()
            artist_name = re.sub(r"\s*\([^)]*\)\s*$", "", artist_name).strip()

            print(f"  ✓ {rel_date}  {artist_name} 「{title}」")
            matched.append({
                "id":          str(detail.get("id", r.get("id", ""))),
                "title":       title,
                "artist":      artist_name,
                "releaseDate": rel_date[:10],
                "detail":      detail,
            })

        if page >= pages:
            break
        page += 1

    return matched


def get_release_detail_by_type(r: dict, r_type: str) -> dict | None:
    """master / release に応じてエンドポイントを切り替えて詳細取得"""
    rid = r.get("id")
    if not rid:
        return None

    if r_type == "master":
        endpoint = f"https://api.discogs.com/masters/{rid}"
    else:
        endpoint = f"https://api.discogs.com/releases/{rid}"

    try:
        resp = requests.get(endpoint, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        time.sleep(SLEEP)
        return resp.json()
    except requests.RequestException as e:
        print(f"  [!] 詳細取得エラー {rid}: {e}")
        return None


# ── iTunes Search API ─────────────────────────────────────────
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
    print(f"📅  {month}月{day}日 — アーティストリスト方式テスト")
    print(f"    対象: {len(ARTISTS)} アーティスト")
    print(f"{'='*52}\n")

    all_tracks = []
    seen_ids   = set()

    for artist_name in ARTISTS:
        print(f"\n── {artist_name} ──")

        # ① アーティストID取得
        artist_id = find_artist_id(artist_name)
        if not artist_id:
            continue

        # ② ディスコグラフィーから月日一致を抽出
        matched = get_discography(artist_id, mmdd)
        if not matched:
            print(f"  {month}月{day}日のリリースなし")

        for m in matched:
            if m["id"] in seen_ids:
                continue
            seen_ids.add(m["id"])

            title  = m["title"]
            artist = m["artist"]

            # ③ iTunes でジャケット・Apple Musicリンク
            itunes     = itunes_search(title, artist)
            jacket_url = ""
            apple_url  = ""
            if itunes:
                jacket_url = itunes.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
                apple_url  = itunes.get("trackViewUrl", "")

            q = requests.utils.quote(f"{artist} {title}")
            track = {
                "id":          m["id"],
                "title":       title,
                "artist":      artist,
                "releaseDate": m["releaseDate"],
                "note":        "",
                "jacket":      jacket_url,
                "color":       "#c8a84b",
                "links": {
                    "spotify":  f"https://open.spotify.com/search/{q}",
                    "apple":    apple_url,
                    "youtube":  f"https://www.youtube.com/results?search_query={requests.utils.quote(artist+' '+title+' 公式')}",
                    "amazon":   f"https://music.amazon.co.jp/search/{q}",
                },
                "source":       "discogs",
                "noteVerified": False,
            }
            all_tracks.append(track)

        time.sleep(1)

    # 結果サマリ
    print(f"\n{'='*52}")
    print(f"✨ 取得結果: {len(all_tracks)} 件")
    for t in all_tracks:
        jacket_mark = "🖼" if t["jacket"] else "  "
        print(f"  {jacket_mark} {t['releaseDate']}  {t['artist']} 「{t['title']}」")
    print(f"{'='*52}")

    # 保存
    if all_tracks:
        save_to_json(all_tracks, mmdd)
    else:
        print("\n該当なし。別の日付や ARTISTS リストを追加してみてください。")

    print("\n✨ テスト完了！")


if __name__ == "__main__":
    main()