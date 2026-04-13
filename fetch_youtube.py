"""
fetch_youtube.py — YouTube Data API v3 で公式PVのIDを収集
================================================================
tracks.json の楽曲に対してYouTube検索を行い、
links.youtubeId フィールドを追加・更新する。

使い方:
  python3 fetch_youtube.py                     # youtubeId未設定の全曲を対象
  python3 fetch_youtube.py --limit 100         # 先頭100件のみ（テスト）
  python3 fetch_youtube.py --artist "欅坂46"   # 1アーティスト指定
  python3 fetch_youtube.py --force             # 既存youtubeIdも上書き

出力: data/tracks.json を上書き（10件ごとに自動保存）

注意:
  YouTube Data API v3 の無料枠は 1日10,000ユニット。
  Search API は 1回=100ユニットなので、1日100件が上限。
  --limit で件数を制限しながら数日に分けて実行してください。
"""

import json, os, time, re
from pathlib import Path
from argparse import ArgumentParser
import requests
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = Path("data/tracks.json")
API_KEY   = os.getenv("YOUTUBE_API_KEY", "")
SLEEP     = 1.0  # リクエスト間隔（秒）


# ── YouTube Search API ──────────────────────────────────────────

def search_youtube(title: str, artist: str) -> str | None:
    """
    アーティスト名 + 楽曲タイトルで検索し、最も適切な動画IDを返す。
    公式チャンネルの動画を優先する。
    """
    # タイトルの末尾の " - Single" " - EP" などを除去して検索
    clean_title = re.sub(r"\s*[-–]\s*(Single|EP|Album|Maxi Single).*$", "", title, flags=re.IGNORECASE).strip()

    query = f"{artist} {clean_title} 公式"

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part":       "snippet",
                "q":          query,
                "type":       "video",
                "maxResults": 5,
                "regionCode": "JP",
                "relevanceLanguage": "ja",
                "key":        API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        time.sleep(SLEEP)
        items = resp.json().get("items", [])
    except Exception as e:
        print(f"    [YT] APIエラー: {e}")
        return None

    if not items:
        return None

    # 公式チャンネルらしいキーワードを含む動画を優先
    official_keywords = ["official", "公式", "vevo", artist.lower()]

    for item in items:
        snippet = item.get("snippet", {})
        channel = snippet.get("channelTitle", "").lower()
        vid_title = snippet.get("title", "").lower()

        # チャンネル名や動画タイトルに公式キーワードが含まれるか
        if any(kw in channel or kw in vid_title for kw in official_keywords):
            return item["id"]["videoId"]

    # 公式っぽいものがなければ先頭を返す
    return items[0]["id"]["videoId"]


# ── メイン処理 ─────────────────────────────────────────────────

def main():
    if not API_KEY:
        print("❌ YOUTUBE_API_KEY が設定されていません。.env を確認してください。")
        return

    parser = ArgumentParser(description="YouTube動画IDを収集")
    parser.add_argument("--limit",  type=int, default=0,  help="処理件数上限（0=全件）")
    parser.add_argument("--artist", type=str, default="", help="アーティスト名を指定")
    parser.add_argument("--force",  action="store_true",  help="既存youtubeIdも上書き")
    args = parser.parse_args()

    with open(DATA_FILE, encoding="utf-8") as f:
        db = json.load(f)

    # 対象楽曲を収集
    targets = []
    for mmdd, tracks in db.items():
        for track in tracks:
            if args.artist and track.get("artist", "") != args.artist:
                continue
            links = track.get("links", {})
            has_id = bool(links.get("youtubeId"))
            if has_id and not args.force:
                continue
            targets.append((mmdd, track))

    if args.limit > 0:
        targets = targets[:args.limit]

    total = len(targets)
    print(f"対象: {total} 件")
    print(f"APIキー: {API_KEY[:8]}...")
    print(f"※ 1日の無料上限は100件です\n")

    if total > 100:
        print(f"⚠️  {total}件は1日の無料上限(100件)を超えています。")
        print(f"   --limit 100 オプションで件数を絞ることを推奨します。\n")

    updated = 0
    skipped = 0

    for i, (mmdd, track) in enumerate(targets, 1):
        title  = track.get("title", "")
        artist = track.get("artist", "")
        print(f"[{i}/{total}] {artist} — {title[:30]}")

        video_id = search_youtube(title, artist)

        if video_id:
            if "links" not in track:
                track["links"] = {}
            track["links"]["youtubeId"] = video_id
            print(f"  ✓ {video_id}")
            updated += 1
        else:
            print(f"  - 見つかりませんでした")
            skipped += 1

        # 10件ごとに保存
        if updated % 10 == 0 and updated > 0:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, separators=(",", ":"))
            print(f"  💾 {updated}件保存済み")

    # 最終保存
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n✨ 完了！")
    print(f"   取得成功: {updated} 件")
    print(f"   見つからず: {skipped} 件")
    print(f"   本日の消費ユニット数（目安）: {updated + skipped} × 100 = {(updated + skipped) * 100} ユニット")


if __name__ == "__main__":
    main()
