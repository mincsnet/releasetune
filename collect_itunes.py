"""
collect_itunes.py — iTunes Search API ベース全楽曲収集スクリプト
================================================================
アーティストリスト（CSV）を読み込み、iTunes Search API で
全シングル・アルバムを取得して data/tracks.json に保存する。

APIキー不要・完全無料。

使い方:
  python3 collect_itunes.py                    # CSV の全アーティスト
  python3 collect_itunes.py --limit 5          # 先頭5アーティストのみ
  python3 collect_itunes.py --artist "欅坂46"  # 1アーティスト指定
  python3 collect_itunes.py --year 2020 2024   # 指定年代のみ保存

出力: data/tracks.json
  {
    "04-06": [ { id, title, artist, releaseDate, jacket, links, ... } ],
    "09-23": [ ... ],
    ...
  }
"""

import json, time, re, csv, unicodedata
from pathlib import Path
from argparse import ArgumentParser
import requests

# ════════════════════════════════════════════════════════════════
# 設定
# ════════════════════════════════════════════════════════════════
ARTISTS_CSV = Path("billboard_artists_2025.csv")
DATA_FILE   = Path("data/tracks.json")

SLEEP       = 0.5   # iTunes API: 制限は緩いが礼儀として

# 収集対象年（この範囲外のリリースは保存しない）
YEAR_MIN = 1980
YEAR_MAX = 2030

# iTunes の collectionType でフィルタ（シングル・アルバム両方取る）
# "Single" = シングル, "Album" = アルバム
TARGET_TYPES = {"Single", "Album", "EP"}


# ════════════════════════════════════════════════════════════════
# iTunes Search API
# ════════════════════════════════════════════════════════════════

def itunes_find_artist(name: str) -> tuple[int | None, str]:
    """アーティスト名 → iTunes artistId を返す"""
    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={
                "term":    name,
                "country": "JP",
                "media":   "music",
                "entity":  "musicArtist",
                "limit":   10,
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        time.sleep(SLEEP)
    except Exception as e:
        print(f"  [iTunes] アーティスト検索エラー: {e}")
        return None, ""

    if not results:
        return None, ""

    # iTunes の関連度順（先頭）を採用
    return results[0]["artistId"], results[0]["artistName"]


def itunes_get_albums(artist_id: int, limit: int = 200) -> list[dict]:
    """
    アーティストIDから全アルバム・シングル一覧を取得。
    iTunes の /lookup エンドポイントを使用。
    """
    try:
        resp = requests.get(
            "https://itunes.apple.com/lookup",
            params={
                "id":      artist_id,
                "country": "JP",
                "entity":  "album",
                "limit":   limit,
                "lang":    "ja_jp",   # 日本語タイトル優先
            },
            timeout=15,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        time.sleep(SLEEP)
    except Exception as e:
        print(f"  [iTunes] アルバム取得エラー: {e}")
        return []

    # 先頭はアーティスト情報なのでスキップ
    return [r for r in results if r.get("wrapperType") == "collection"]


def parse_album(album: dict, fallback_artist: str) -> dict | None:
    """
    iTunes のアルバム情報を ReleaseTune 形式に変換。
    releaseDate が YYYY-MM-DD 形式に正規化できるものだけ採用。
    """
    raw_date = album.get("releaseDate", "")
    if not raw_date:
        return None

    # "2016-04-06T07:00:00Z" → "2016-04-06"
    rel_date = raw_date[:10]
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", rel_date):
        return None

    year = int(rel_date[:4])
    if not (YEAR_MIN <= year <= YEAR_MAX):
        return None

    title  = album.get("collectionName", "").strip()
    artist = album.get("artistName", fallback_artist).strip()

    # "(Special Edition)" "(Complete Edition)" などのサフィックスを除去するか判断
    # → ReleaseTune では元のタイトルを保持する
    if not title or not artist:
        return None

    # ジャケット画像: 100x100 → 600x600 に差し替え
    jacket = album.get("artworkUrl100", "").replace("100x100bb", "600x600bb")

    # Apple Music リンク
    apple_url = album.get("collectionViewUrl", "")

    # YouTube・Amazon は検索URL
    q   = requests.utils.quote(f"{artist} {title}")
    yt  = "https://www.youtube.com/results?search_query=" + requests.utils.quote(f"{artist} {title} 公式")
    amz = "https://music.amazon.co.jp/search/" + q
    sp  = "https://open.spotify.com/search/" + q

    # コレクションタイプ（Single / Album 等）
    col_type = album.get("collectionType", "")

    return {
        "id":          str(album.get("collectionId", "")),
        "title":       title,
        "artist":      artist,
        "releaseDate": rel_date,
        "type":        col_type,   # "Single" or "Album"
        "note":        "",
        "jacket":      jacket,
        "color":       "#c8a84b",
        "links": {
            "spotify": sp,
            "apple":   apple_url,
            "youtube": yt,
            "amazon":  amz,
        },
        "source":       "itunes",
        "noteVerified": False,
    }


# ════════════════════════════════════════════════════════════════
# データ保存
# ════════════════════════════════════════════════════════════════

def load_db() -> dict:
    if DATA_FILE.exists():
        with open(DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {}


def flush_db(db: dict):
    DATA_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)


def add_track(db: dict, track: dict) -> bool:
    """MM-DD キーにトラックを追加。重複IDはスキップ。"""
    mmdd   = track["releaseDate"][5:10]
    bucket = db.setdefault(mmdd, [])
    if any(t["id"] == track["id"] for t in bucket):
        return False
    bucket.append(track)
    return True


# ════════════════════════════════════════════════════════════════
# アーティスト1人分の処理
# ════════════════════════════════════════════════════════════════

def process_artist(name: str, db: dict) -> int:
    print(f"\n{'─'*48}")
    print(f"🎤  {name}")

    # ① アーティストID取得
    artist_id, found_name = itunes_find_artist(name)
    if not artist_id:
        print(f"  → iTunes で見つかりません。スキップ。")
        return 0
    print(f"  → {found_name} (id={artist_id})")

    # ② 全アルバム・シングル取得
    albums = itunes_get_albums(artist_id, limit=200)
    print(f"  → {len(albums)} 件取得")

    added = 0
    for album in albums:
        track = parse_album(album, name)
        if not track:
            continue
        if add_track(db, track):
            added += 1
            type_label = "💿" if track["type"] == "Album" else "🎵"
            print(f"  {type_label} {track['releaseDate']}  {track['artist']} 「{track['title']}」")

    print(f"  → 追加: {added} 件")

    # 1アーティストごとに保存
    flush_db(db)
    return added


# ════════════════════════════════════════════════════════════════
# CLI
# ════════════════════════════════════════════════════════════════

def load_artist_list(limit: int | None) -> list[str]:
    if not ARTISTS_CSV.exists():
        print(f"[!] {ARTISTS_CSV} が見つかりません。")
        return []
    with open(ARTISTS_CSV, encoding="utf-8") as f:
        reader  = csv.DictReader(f)
        artists = [row["artist"].strip() for row in reader if row.get("artist")]
    # コラボ表記はスキップ（"A, B" / "A & B"）
    artists = [a for a in artists if "," not in a and " & " not in a]
    return artists[:limit] if limit else artists


def main():
    parser = ArgumentParser(description="ReleaseTune 全楽曲収集（iTunes版）")
    parser.add_argument("--limit",  type=int, help="先頭N アーティストのみ処理")
    parser.add_argument("--artist", type=str, help="アーティスト名を直接指定")
    args = parser.parse_args()

    artists = [args.artist] if args.artist else load_artist_list(args.limit)
    if not artists:
        print("アーティストリストが空です。")
        return

    print(f"{'='*48}")
    print(f"ReleaseTune 全楽曲収集（iTunes Search API）")
    print(f"対象: {len(artists)} アーティスト")
    print(f"出力: {DATA_FILE.resolve()}")
    print(f"{'='*48}")

    db = load_db()
    existing = sum(len(v) for v in db.values())
    print(f"既存データ: {existing} 件 / {len(db)} 日分")

    total_added = 0
    for i, name in enumerate(artists, 1):
        print(f"\n[{i}/{len(artists)}]", end="")
        total_added += process_artist(name, db)
        time.sleep(1)

    print(f"\n{'='*48}")
    print(f"✨ 完了！")
    print(f"   今回追加: {total_added} 件")
    print(f"   総データ: {sum(len(v) for v in db.values())} 件")
    print(f"   日付数:   {len(db)} 日分")
    print(f"   ファイル: {DATA_FILE.resolve()}")
    print(f"{'='*48}")


if __name__ == "__main__":
    main()