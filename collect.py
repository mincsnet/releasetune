"""
ReleaseTune データ収集スクリプト v2
=====================================
データソース:
  - MusicBrainz API  : リリース日（月日完全一致）・基本情報  ← メイン
  - Wikipedia API    : noteコメント自動生成
  - iTunes Search API: ジャケット画像・Apple Musicリンク
  - Spotify API      : 楽曲直接リンク

使い方:
  python3 collect.py --date 04-06
  python3 collect.py --range 04-01 04-30

必要なAPIキー（.env に記載）:
  SPOTIFY_CLIENT_ID=xxxx
  SPOTIFY_CLIENT_SECRET=xxxx

MusicBrainz・Wikipedia・iTunes は APIキー不要。
"""

import os, json, time, re, unicodedata
from datetime import date, timedelta
from pathlib import Path
from argparse import ArgumentParser

import requests
from dotenv import load_dotenv
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials

load_dotenv()

# ════════════════════════════════════════════════════════════════
# 設定
# ════════════════════════════════════════════════════════════════
SPOTIFY_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")
DATA_FILE      = Path("data/tracks.json")

SLEEP_MB        = 1.1   # MusicBrainz: 1 req/sec
SLEEP_WIKIPEDIA = 0.5
SLEEP_ITUNES    = 0.3
SLEEP_SPOTIFY   = 0.3

MB_HEADERS = {
    # MusicBrainz はアプリ名・バージョン・連絡先の記載が必須
    "User-Agent": "ReleaseTune/1.0 ( your@email.com )",  # ← メアドを変更
    "Accept":     "application/json",
}


# ════════════════════════════════════════════════════════════════
# MusicBrainz API
# ════════════════════════════════════════════════════════════════

def mb_search_releases(month: int, day: int) -> list[dict]:
    """
    MusicBrainz で指定月日にリリースされた日本の楽曲を検索する。

    MusicBrainz の Lucene 検索は先頭ワイルドカード（????-MM-DD）が使えないため、
    正規表現 /[0-9]{4}-MM-DD/ を使って月日を絞り込む。
    """
    mmdd  = f"{month:02d}-{day:02d}"
    # 正規表現で年4桁-月日 に一致するものを検索
    # country:JP でリリースイベントが日本のものを対象
    query = f'date:/[0-9]{{4}}-{mmdd}/ AND country:JP'

    url    = "https://musicbrainz.org/ws/2/release"
    params = {
        "query":  query,
        "fmt":    "json",
        "limit":  100,
        "offset": 0,
    }

    all_releases = []
    while True:
        try:
            resp = requests.get(url, headers=MB_HEADERS, params=params, timeout=20)
            resp.raise_for_status()
            data  = resp.json()
            time.sleep(SLEEP_MB)
        except requests.RequestException as e:
            print(f"  [MusicBrainz] 検索失敗: {e}")
            break

        releases = data.get("releases", [])
        count    = data.get("release-count", 0)

        if not releases:
            break

        print(f"  [MusicBrainz] {len(releases)} 件取得（全{count}件中）")

        # 月日が正確に一致 かつ release-group type が Single のものを採用
        for r in releases:
            rel_date = r.get("date", "")
            if len(rel_date) >= 7 and rel_date[5:10] == mmdd:
                rg_type = r.get("release-group", {}).get("primary-type", "")
                # Single またはタイプ未指定も含める（アルバムは除外）
                if rg_type in ("Single", "EP", ""):
                    all_releases.append(r)

        params["offset"] += len(releases)
        if params["offset"] >= count or params["offset"] >= 500:
            break
        print(f"  [MusicBrainz] 次ページを取得中... ({params['offset']}/{count})")

    return all_releases


def mb_get_release_detail(mbid: str) -> dict | None:
    """MusicBrainz のリリース詳細（アーティスト等）を取得"""
    url = f"https://musicbrainz.org/ws/2/release/{mbid}"
    params = {
        "inc": "artist-credits+labels+recordings",
        "fmt": "json",
    }
    try:
        resp = requests.get(url, headers=MB_HEADERS, params=params, timeout=20)
        resp.raise_for_status()
        time.sleep(SLEEP_MB)
        return resp.json()
    except requests.RequestException as e:
        print(f"  [MusicBrainz] 詳細取得失敗 {mbid}: {e}")
        return None


def parse_mb_release(release: dict) -> dict | None:
    """MusicBrainz レスポンスを内部形式に変換"""
    rel_date = release.get("date", "")
    if len(rel_date) < 7:
        return None

    # YYYY-MM-DD 形式に正規化（日がない場合は 01 補完）
    if len(rel_date) == 7:
        rel_date += "-01"

    # タイトル
    title = release.get("title", "").strip()
    if not title:
        return None

    # アーティスト名（artist-credit から取得）
    artist_credit = release.get("artist-credit", [])
    artist_parts  = []
    for ac in artist_credit:
        if isinstance(ac, dict):
            name = ac.get("name") or ac.get("artist", {}).get("name", "")
            joinphrase = ac.get("joinphrase", "")
            if name:
                artist_parts.append(name + joinphrase)
    artist = "".join(artist_parts).strip()

    if not artist:
        return None

    return {
        "mbid":        release.get("id", ""),
        "title":       title,
        "artist":      artist,
        "releaseDate": rel_date,
    }


# ════════════════════════════════════════════════════════════════
# Wikipedia API（日本語）
# ════════════════════════════════════════════════════════════════

def wikipedia_search_title(title: str, artist: str) -> str | None:
    query  = f"{title} {artist}"
    url    = "https://ja.wikipedia.org/w/api.php"
    params = {
        "action":   "query",
        "list":     "search",
        "srsearch": query,
        "srlimit":  5,
        "format":   "json",
        "utf8":     1,
    }
    try:
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        hits = resp.json().get("query", {}).get("search", [])
        time.sleep(SLEEP_WIKIPEDIA)
    except requests.RequestException as e:
        print(f"  [Wikipedia] 検索失敗: {e}")
        return None

    if not hits:
        return None

    title_norm = unicodedata.normalize("NFKC", title).lower()
    for hit in hits:
        page_title = hit.get("title", "")
        page_norm  = unicodedata.normalize("NFKC", page_title).lower()
        if title_norm in page_norm or page_norm.startswith(title_norm):
            return page_title
    return hits[0].get("title")


def wikipedia_get_intro(page_title: str) -> str | None:
    url    = "https://ja.wikipedia.org/w/api.php"
    params = {
        "action":      "query",
        "titles":      page_title,
        "prop":        "extracts",
        "exintro":     True,
        "explaintext": True,
        "format":      "json",
        "utf8":        1,
    }
    try:
        resp  = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        time.sleep(SLEEP_WIKIPEDIA)
    except requests.RequestException as e:
        print(f"  [Wikipedia] イントロ取得失敗: {e}")
        return None

    for page in pages.values():
        extract = page.get("extract", "").strip()
        if extract and page.get("pageid", -1) != -1:
            return extract
    return None


def extract_note(raw_text: str) -> str:
    """Wikipedia イントロから note として使いやすい文を抽出"""
    if not raw_text:
        return ""

    text      = re.sub(r"\n{2,}", "\n", raw_text).strip()
    sentences = [s.strip() + "。" for s in re.split(r"。", text) if s.strip()]

    PATTERNS = [
        r"(テレビドラマ|ドラマ|映画|アニメ|テレビアニメ|CM|主題歌|挿入歌|タイアップ)",
        r"(オリコン|チャート|1位|2位|3位|ミリオン|万枚|累計)",
        r"(日本レコード大賞|ゴールデン|プラチナ|認定|受賞)",
    ]
    priority, others = [], []
    for s in sentences:
        if any(re.search(p, s) for p in PATTERNS):
            priority.append(s)
        else:
            others.append(s)

    selected = priority[:2] if priority else others[:2]
    note     = "".join(selected)
    if len(note) > 120:
        note = note[:120].rstrip("、。") + "…"
    return note


def get_wikipedia_note(title: str, artist: str) -> str:
    page = wikipedia_search_title(title, artist)
    if not page:
        return ""
    raw = wikipedia_get_intro(page)
    if not raw:
        return ""
    note = extract_note(raw)
    if note:
        print(f"  [Wikipedia] ✓ {note[:50]}...")
    return note


# ════════════════════════════════════════════════════════════════
# iTunes Search API
# ════════════════════════════════════════════════════════════════

def itunes_search(title: str, artist: str) -> dict | None:
    url    = "https://itunes.apple.com/search"
    params = {
        "term":    f"{artist} {title}",
        "country": "JP",
        "media":   "music",
        "entity":  "song",
        "limit":   5,
        "lang":    "ja_jp",
    }
    try:
        resp    = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        results = resp.json().get("results", [])
        time.sleep(SLEEP_ITUNES)
    except requests.RequestException as e:
        print(f"  [iTunes] 検索失敗: {e}")
        return None

    if not results:
        return None

    artist_norm = unicodedata.normalize("NFKC", artist).lower()
    for r in results:
        r_artist = unicodedata.normalize("NFKC", r.get("artistName", "")).lower()
        if artist_norm in r_artist or r_artist in artist_norm:
            return r
    return results[0]


def build_apple_url(itunes: dict) -> str:
    return itunes.get("trackViewUrl", "")


def build_jacket_url(itunes: dict) -> str:
    url = itunes.get("artworkUrl100", "")
    return url.replace("100x100bb", "600x600bb") if url else ""


# ════════════════════════════════════════════════════════════════
# Spotify API
# ════════════════════════════════════════════════════════════════

def get_spotify_client() -> spotipy.Spotify | None:
    if not SPOTIFY_ID or not SPOTIFY_SECRET:
        print("  [Spotify] APIキー未設定。検索URLにフォールバック。")
        return None
    try:
        auth = SpotifyClientCredentials(
            client_id=SPOTIFY_ID,
            client_secret=SPOTIFY_SECRET,
        )
        return spotipy.Spotify(auth_manager=auth)
    except Exception as e:
        print(f"  [Spotify] 認証失敗: {e}")
        return None


def spotify_search(sp: spotipy.Spotify, title: str, artist: str) -> str:
    fallback = (
        "https://open.spotify.com/search/"
        + requests.utils.quote(f"{artist} {title}")
    )
    try:
        for query in [f"track:{title} artist:{artist}", f"{artist} {title}"]:
            results = sp.search(q=query, type="track", limit=5, market="JP")
            items   = results.get("tracks", {}).get("items", [])
            time.sleep(SLEEP_SPOTIFY)
            if items:
                url = items[0].get("external_urls", {}).get("spotify", "")
                return url if url else fallback
    except Exception as e:
        print(f"  [Spotify] 検索失敗: {e}")
    return fallback


# ════════════════════════════════════════════════════════════════
# YouTube / Amazon（検索URL）
# ════════════════════════════════════════════════════════════════

def build_youtube_url(title: str, artist: str) -> str:
    return "https://www.youtube.com/results?search_query=" + requests.utils.quote(f"{artist} {title} 公式")


def build_amazon_url(title: str, artist: str) -> str:
    return "https://music.amazon.co.jp/search/" + requests.utils.quote(f"{title} {artist}")


# ════════════════════════════════════════════════════════════════
# メイン収集処理
# ════════════════════════════════════════════════════════════════

def collect_for_date(month: int, day: int, sp) -> list[dict]:
    mmdd = f"{month:02d}-{day:02d}"
    print(f"\n{'='*52}")
    print(f"📅  {month}月{day}日 ({mmdd}) の楽曲を収集中...")
    print(f"{'='*52}")

    # ① MusicBrainz で月日一致リリースを検索
    releases = mb_search_releases(month, day)
    if not releases:
        print("  MusicBrainz: ヒットなし")
        return []

    print(f"  MusicBrainz: {len(releases)} 件ヒット")

    tracks = []
    seen_titles = set()  # 重複排除用

    for r in releases:
        parsed = parse_mb_release(r)
        if not parsed:
            continue

        title  = parsed["title"]
        artist = parsed["artist"]

        # 同じ曲名・アーティストの重複をスキップ
        key = f"{artist}|{title}"
        if key in seen_titles:
            continue
        seen_titles.add(key)

        print(f"\n  ── {artist} 「{title}」 ({parsed['releaseDate']}) ──")

        # ② Wikipedia から note を生成
        note = get_wikipedia_note(title, artist)

        # ③ iTunes からジャケット・Apple Music URL
        itunes     = itunes_search(title, artist)
        jacket_url = build_jacket_url(itunes) if itunes else ""
        apple_url  = build_apple_url(itunes)  if itunes else ""
        if jacket_url:
            print(f"  [iTunes] ✓ ジャケット取得")

        # ④ Spotify 直接URL
        spotify_url = spotify_search(sp, title, artist) if sp else (
            "https://open.spotify.com/search/" + requests.utils.quote(f"{artist} {title}")
        )

        # ⑤ YouTube・Amazon 検索URL
        youtube_url = build_youtube_url(title, artist)
        amazon_url  = build_amazon_url(title, artist)

        track = {
            "id":           parsed["mbid"],
            "title":        title,
            "artist":       artist,
            "releaseDate":  parsed["releaseDate"],
            "note":         note,
            "jacket":       jacket_url,
            "color":        "#c8a84b",
            "links": {
                "spotify":  spotify_url,
                "apple":    apple_url,
                "youtube":  youtube_url,
                "amazon":   amazon_url,
            },
            "source":       "musicbrainz",
            "noteVerified": False,
        }
        tracks.append(track)

    print(f"\n  合計 {len(tracks)} 件を処理")
    return tracks


# ════════════════════════════════════════════════════════════════
# 保存
# ════════════════════════════════════════════════════════════════

def save_tracks(new_tracks: list[dict], mmdd: str) -> None:
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)

    existing: dict = {}
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            existing = json.load(f)

    current     = existing.get(mmdd, [])
    current_ids = {t["id"] for t in current}
    added       = 0

    for t in new_tracks:
        if t["id"] not in current_ids:
            current.append(t)
            current_ids.add(t["id"])
            added += 1

    existing[mmdd] = current

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    print(f"\n  ✅ {mmdd}: {added} 件追加（合計 {len(current)} 件）→ {DATA_FILE}")


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════

def main() -> None:
    parser = ArgumentParser(description="ReleaseTune データ収集 v2（MusicBrainz）")
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--date",  metavar="MM-DD",
                       help="特定の月日（例: 04-06）")
    group.add_argument("--range", metavar=("MM-DD", "MM-DD"), nargs=2,
                       help="月日の範囲（例: 04-01 04-30）")
    args = parser.parse_args()

    sp = get_spotify_client()

    target_dates: list[tuple[int, int]] = []
    if args.date:
        m, d = map(int, args.date.split("-"))
        target_dates.append((m, d))
    else:
        sm, sd = map(int, args.range[0].split("-"))
        em, ed = map(int, args.range[1].split("-"))
        cur = date(2024, sm, sd)
        end = date(2024, em, ed)
        while cur <= end:
            target_dates.append((cur.month, cur.day))
            cur += timedelta(days=1)

    print(f"対象: {len(target_dates)} 日分")

    for month, day in target_dates:
        mmdd   = f"{month:02d}-{day:02d}"
        tracks = collect_for_date(month, day, sp)
        if tracks:
            save_tracks(tracks, mmdd)
        time.sleep(2)

    print("\n\n✨ 完了！")
    print(f"   データファイル: {DATA_FILE.resolve()}")
    print("   noteVerified: false の項目は内容を確認・修正してください。")


if __name__ == "__main__":
    main()