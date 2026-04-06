"""
collect_all.py — アーティスト全楽曲データ収集スクリプト
=========================================================
アーティストリスト（CSV）を読み込み、各アーティストの
シングル・EPを全件取得して data/tracks.json に保存する。

データ構造:
  {
    "MM-DD": [
      { id, title, artist, releaseDate, note, jacket, links, ... },
      ...
    ]
  }

使い方:
  python3 collect_all.py                        # CSVの全アーティスト
  python3 collect_all.py --limit 10             # 先頭10アーティストのみ
  python3 collect_all.py --artist "スピッツ"    # 1アーティスト指定

必要なAPIキー（.env）:
  SPOTIFY_CLIENT_ID=xxxx
  SPOTIFY_CLIENT_SECRET=xxxx

Discogs・iTunes・Wikipedia は APIキー不要。
"""

import os, json, time, re, csv, unicodedata
from pathlib import Path
from argparse import ArgumentParser
from dotenv import load_dotenv
import requests

load_dotenv()

# ════════════════════════════════════════════════════════════════
# 設定
# ════════════════════════════════════════════════════════════════
ARTISTS_CSV = Path("billboard_artists_2025.csv")  # アーティストリスト
DATA_FILE   = Path("data/tracks.json")

DISCOGS_TOKEN = os.getenv("DISCOGS_TOKEN", "")
DISCOGS_HEADERS = {
    "Authorization": f"Discogs token={DISCOGS_TOKEN}",
    "User-Agent":    "ReleaseTune/1.0 (your@email.com)",  # ← 変更してください
}

SPOTIFY_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

SLEEP_DISCOGS = 1.2
SLEEP_ITUNES  = 0.3
SLEEP_SPOTIFY = 0.3

# シングル・EPのみ対象（アルバム・コンピは除外）
TARGET_FORMATS = {"Single", "EP"}

# ════════════════════════════════════════════════════════════════
# Discogs
# ════════════════════════════════════════════════════════════════

def discogs_find_artist(name: str) -> tuple[int | None, str]:
    """アーティスト名 → Discogs artist ID を返す"""
    try:
        resp = requests.get(
            "https://api.discogs.com/database/search",
            headers=DISCOGS_HEADERS,
            params={"q": name, "type": "artist", "per_page": 5},
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        time.sleep(SLEEP_DISCOGS)
    except requests.RequestException as e:
        print(f"  [Discogs] アーティスト検索エラー: {e}")
        return None, ""

    if not results:
        return None, ""

    r = results[0]
    return r.get("id"), r.get("title", "")


def discogs_get_discography(artist_id: int) -> list[dict]:
    """
    アーティストの全リリース一覧を取得。
    ページネーションで全件取得する。
    """
    all_releases = []
    page = 1
    while True:
        try:
            resp = requests.get(
                f"https://api.discogs.com/artists/{artist_id}/releases",
                headers=DISCOGS_HEADERS,
                params={
                    "sort":       "year",
                    "sort_order": "asc",
                    "per_page":   100,
                    "page":       page,
                },
                timeout=15,
            )
            resp.raise_for_status()
            data     = resp.json()
            releases = data.get("releases", [])
            pages    = data.get("pagination", {}).get("pages", 1)
            time.sleep(SLEEP_DISCOGS)
        except requests.RequestException as e:
            print(f"  [Discogs] ディスコグラフィー取得エラー p{page}: {e}")
            break

        if not releases:
            break

        # Mainクレジット（本人名義）のみ対象
        for r in releases:
            if r.get("role") == "Main":
                all_releases.append(r)

        if page >= pages:
            break
        page += 1

    return all_releases


def discogs_get_release_detail(release_id: int, is_master: bool) -> dict | None:
    """リリース詳細を取得（master / release を自動判別）"""
    endpoint = (
        f"https://api.discogs.com/masters/{release_id}"
        if is_master
        else f"https://api.discogs.com/releases/{release_id}"
    )
    try:
        resp = requests.get(endpoint, headers=DISCOGS_HEADERS, timeout=15)
        resp.raise_for_status()
        time.sleep(SLEEP_DISCOGS)
        return resp.json()
    except requests.RequestException as e:
        print(f"  [Discogs] 詳細取得エラー {release_id}: {e}")
        return None


def is_single_or_ep(detail: dict) -> bool:
    """フォーマットがシングル or EP かどうか判定"""
    formats = detail.get("formats", [])
    for f in formats:
        name = f.get("name", "")
        descs = f.get("descriptions", [])
        combined = name + " " + " ".join(descs)
        if any(t in combined for t in TARGET_FORMATS):
            return True
    # master の場合は formats がないことがある → title に頼る
    return False


def parse_release(detail: dict, fallback_artist: str) -> dict | None:
    """
    Discogs レスポンスから ReleaseTune 形式に変換。
    released が YYYY-MM-DD 形式のものだけ採用。
    """
    rel_date = detail.get("released", "")

    # 日付が不完全なものは補完
    if not rel_date:
        return None
    if re.match(r"^\d{4}$", rel_date):
        # 年のみ → スキップ（月日不明）
        return None
    if re.match(r"^\d{4}-\d{2}$", rel_date):
        # 年月のみ → 01日として補完
        rel_date += "-01"
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", rel_date):
        return None

    # タイトル・アーティスト名
    title = detail.get("title", "").strip()
    if not title:
        return None

    artists_list = detail.get("artists", [{}])
    if artists_list:
        artist = artists_list[0].get("name", fallback_artist).strip()
        artist = re.sub(r"\s*\([^)]*\)\s*$", "", artist).strip()
    else:
        artist = fallback_artist

    # "アーティスト – タイトル" 形式を分割
    if " – " in title:
        parts  = title.split(" – ", 1)
        artist = parts[0].strip()
        title  = parts[1].strip()
        artist = re.sub(r"\s*\([^)]*\)\s*$", "", artist).strip()

    if not artist or not title:
        return None

    return {
        "id":          str(detail.get("id", "")),
        "title":       title,
        "artist":      artist,
        "releaseDate": rel_date,
    }


# ════════════════════════════════════════════════════════════════
# iTunes Search API（ジャケット画像 + Apple Music リンク）
# ════════════════════════════════════════════════════════════════

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
        time.sleep(SLEEP_ITUNES)
    except Exception:
        return None

    if not results:
        return None

    artist_norm = unicodedata.normalize("NFKC", artist).lower()
    for r in results:
        r_norm = unicodedata.normalize("NFKC", r.get("artistName", "")).lower()
        if artist_norm in r_norm or r_norm in artist_norm:
            return r
    return results[0]


# ════════════════════════════════════════════════════════════════
# Spotify API（直接リンク）
# ════════════════════════════════════════════════════════════════

_sp = None

def get_spotify():
    global _sp
    if _sp is not None:
        return _sp
    if not SPOTIFY_ID or not SPOTIFY_SECRET:
        return None
    try:
        import spotipy
        from spotipy.oauth2 import SpotifyClientCredentials
        auth = SpotifyClientCredentials(
            client_id=SPOTIFY_ID,
            client_secret=SPOTIFY_SECRET,
        )
        _sp = spotipy.Spotify(auth_manager=auth)
        return _sp
    except Exception as e:
        print(f"  [Spotify] 認証失敗: {e}")
        return None


def spotify_url(title: str, artist: str) -> str:
    fallback = "https://open.spotify.com/search/" + requests.utils.quote(f"{artist} {title}")
    sp = get_spotify()
    if not sp:
        return fallback
    try:
        for q in [f"track:{title} artist:{artist}", f"{artist} {title}"]:
            res   = sp.search(q=q, type="track", limit=5, market="JP")
            items = res.get("tracks", {}).get("items", [])
            time.sleep(SLEEP_SPOTIFY)
            if items:
                url = items[0].get("external_urls", {}).get("spotify", "")
                return url or fallback
    except Exception:
        pass
    return fallback


# ════════════════════════════════════════════════════════════════
# データ保存
# ════════════════════════════════════════════════════════════════

def load_existing() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def save_track(db: dict, track: dict) -> bool:
    """
    tracks.json の MM-DD キーにトラックを追加。
    同じ ID が既にあればスキップ。
    戻り値: 追加したなら True
    """
    mmdd = track["releaseDate"][5:10]   # "YYYY-MM-DD" → "MM-DD"
    bucket = db.setdefault(mmdd, [])
    ids    = {t["id"] for t in bucket}
    if track["id"] in ids:
        return False
    bucket.append(track)
    return True


def flush(db: dict):
    """DB をファイルに書き出す"""
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


# ════════════════════════════════════════════════════════════════
# アーティスト1人分の処理
# ════════════════════════════════════════════════════════════════

def process_artist(name: str, db: dict) -> int:
    """
    アーティスト名を受け取り、全シングル・EPを db に追加。
    追加件数を返す。
    """
    print(f"\n{'─'*48}")
    print(f"🎤  {name}")

    # ① アーティストID取得
    artist_id, found_name = discogs_find_artist(name)
    if not artist_id:
        print(f"  → Discogsで見つかりません。スキップ。")
        return 0
    print(f"  → {found_name} (id={artist_id})")

    # ② ディスコグラフィー全件取得
    releases = discogs_get_discography(artist_id)
    print(f"  → リリース {len(releases)} 件取得")

    added_total = 0
    skipped     = 0

    for r in releases:
        r_type = r.get("type", "release")   # "master" or "release"
        r_id   = r.get("id")
        if not r_id:
            continue

        # 詳細取得
        detail = discogs_get_release_detail(r_id, is_master=(r_type == "master"))
        if not detail:
            continue

        # シングル・EPのみ対象
        if not is_single_or_ep(detail):
            skipped += 1
            continue

        # パース
        parsed = parse_release(detail, name)
        if not parsed:
            skipped += 1
            continue

        title  = parsed["title"]
        artist = parsed["artist"]

        # ③ iTunes でジャケット・Apple Music
        itunes     = itunes_search(title, artist)
        jacket_url = ""
        apple_url  = ""
        if itunes:
            jacket_url = itunes.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
            apple_url  = itunes.get("trackViewUrl", "")

        # ④ Spotify 直接URL
        sp_url = spotify_url(title, artist)

        # ⑤ YouTube・Amazon 検索URL
        q   = requests.utils.quote(f"{artist} {title}")
        yt  = "https://www.youtube.com/results?search_query=" + requests.utils.quote(f"{artist} {title} 公式")
        amz = "https://music.amazon.co.jp/search/" + q

        track = {
            "id":          parsed["id"],
            "title":       title,
            "artist":      artist,
            "releaseDate": parsed["releaseDate"],
            "note":        "",
            "jacket":      jacket_url,
            "color":       "#c8a84b",
            "links": {
                "spotify": sp_url,
                "apple":   apple_url,
                "youtube": yt,
                "amazon":  amz,
            },
            "source":       "discogs",
            "noteVerified": False,
        }

        if save_track(db, track):
            added_total += 1
            mmdd = parsed["releaseDate"][5:10]
            print(f"  ✓ {parsed['releaseDate']}  {artist} 「{title}」")
        else:
            skipped += 1

    print(f"  → 追加: {added_total} 件 / スキップ: {skipped} 件")

    # アーティスト1人分処理するたびにファイルに保存
    flush(db)
    return added_total


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════

def load_artist_list(limit: int | None) -> list[str]:
    if not ARTISTS_CSV.exists():
        print(f"[!] {ARTISTS_CSV} が見つかりません。")
        return []
    with open(ARTISTS_CSV, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        artists = [row["artist"].strip() for row in reader if row.get("artist")]
    # コラボ表記（"A, B" や "A & B"）はスキップ
    artists = [a for a in artists if "," not in a and "&" not in a]
    if limit:
        artists = artists[:limit]
    return artists


def main():
    parser = ArgumentParser(description="ReleaseTune 全楽曲収集スクリプト")
    parser.add_argument("--limit",  type=int,  help="先頭N アーティストのみ処理")
    parser.add_argument("--artist", type=str,  help="アーティスト名を直接指定（テスト用）")
    args = parser.parse_args()

    # アーティストリスト決定
    if args.artist:
        artists = [args.artist]
    else:
        artists = load_artist_list(args.limit)

    if not artists:
        print("アーティストリストが空です。")
        return

    print(f"{'='*48}")
    print(f"ReleaseTune 全楽曲収集")
    print(f"対象: {len(artists)} アーティスト")
    print(f"出力: {DATA_FILE.resolve()}")
    print(f"{'='*48}")

    # 既存データを読み込み
    db = load_existing()
    print(f"既存データ: {sum(len(v) for v in db.values())} 件")

    total_added = 0
    for i, name in enumerate(artists, 1):
        print(f"\n[{i}/{len(artists)}]", end="")
        added = process_artist(name, db)
        total_added += added
        # アーティスト間のインターバル
        time.sleep(2)

    print(f"\n{'='*48}")
    print(f"✨ 完了！")
    print(f"   今回追加: {total_added} 件")
    print(f"   総データ: {sum(len(v) for v in db.values())} 件")
    print(f"   日付数:   {len(db)} 日分")
    print(f"   ファイル: {DATA_FILE.resolve()}")
    print(f"{'='*48}")


if __name__ == "__main__":
    main()