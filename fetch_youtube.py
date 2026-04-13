"""
fetch_youtube.py — YouTube Data API v3 で公式PVのIDを収集
================================================================
tracks.json の楽曲に対してYouTube検索を行い、
links.youtubeId と links.youtubeVerified フィールドを追加・更新する。

youtubeVerified:
  true  = 公式動画として確認済み（サイトに表示）
  false = 未確認（サイトに表示されない）

使い方:
  python3 fetch_youtube.py                     # youtubeId未設定の全曲を対象
  python3 fetch_youtube.py --limit 100         # 先頭100件のみ
  python3 fetch_youtube.py --artist "欅坂46"   # 1アーティスト指定
  python3 fetch_youtube.py --force             # 既存youtubeIdも上書き

確認作業:
  python3 fetch_youtube.py --show-unverified   # 未確認のURLを一覧表示
  python3 fetch_youtube.py --verify TRACK_ID   # verified=trueに変更
  python3 fetch_youtube.py --reject TRACK_ID   # youtubeIdを削除
"""

import json, os, time, re, unicodedata
from pathlib import Path
from argparse import ArgumentParser
import requests
from dotenv import load_dotenv

load_dotenv()

DATA_FILE = Path("data/tracks.json")
API_KEY   = os.getenv("YOUTUBE_API_KEY", "")
SLEEP     = 1.0


def is_japanese(text: str) -> bool:
    for ch in text:
        name = unicodedata.name(ch, "")
        if "HIRAGANA" in name or "KATAKANA" in name or "CJK" in name:
            return True
    return False


def clean_title(title: str) -> str:
    return re.sub(r"\s*[-–]\s*(Single|EP|Album|Maxi Single|CD|DVD).*$", "", title, flags=re.IGNORECASE).strip()


def search_youtube(title: str, artist: str) -> tuple[str | None, bool]:
    q_title = clean_title(title)
    has_ja  = is_japanese(title) or is_japanese(artist)
    query   = f"{artist} {q_title} 公式" if has_ja else f"{artist} {q_title} official"

    try:
        resp = requests.get(
            "https://www.googleapis.com/youtube/v3/search",
            params={
                "part":              "snippet",
                "q":                 query,
                "type":              "video",
                "maxResults":        5,
                "regionCode":        "JP",
                "relevanceLanguage": "ja",
                "key":               API_KEY,
            },
            timeout=10,
        )
        resp.raise_for_status()
        time.sleep(SLEEP)
        items = resp.json().get("items", [])
    except Exception as e:
        print(f"    [YT] APIエラー: {e}")
        return None, False

    if not items:
        return None, False

    artist_norm = artist.lower()
    official_kw = ["official", "公式", "vevo", artist_norm]

    for item in items:
        snippet     = item.get("snippet", {})
        channel     = snippet.get("channelTitle", "").lower()
        vid_title   = snippet.get("title", "").lower()
        is_official = any(kw in channel or kw in vid_title for kw in official_kw)
        if is_official:
            return item["id"]["videoId"], has_ja

    return items[0]["id"]["videoId"], False


def show_unverified(db: dict) -> None:
    print("\n未確認の YouTube ID 一覧:")
    print("-" * 60)
    count = 0
    for tracks in db.values():
        for t in tracks:
            links = t.get("links", {})
            vid   = links.get("youtubeId", "")
            if vid and not links.get("youtubeVerified", False):
                print(f"  {t['artist']} | {t['title'][:30]}")
                print(f"    https://www.youtube.com/watch?v={vid}")
                print(f"    track ID: {t['id']}")
                count += 1
    print(f"\n合計 {count} 件")


def update_by_track_id(db: dict, track_id: str, verified: bool) -> bool:
    for tracks in db.values():
        for t in tracks:
            if t.get("id") == track_id:
                if verified:
                    t["links"]["youtubeVerified"] = True
                    print(f"✅ verified=true: {t['artist']} | {t['title']}")
                else:
                    t["links"].pop("youtubeId", None)
                    t["links"].pop("youtubeVerified", None)
                    print(f"🗑  削除: {t['artist']} | {t['title']}")
                return True
    print(f"❌ track ID が見つかりません: {track_id}")
    return False


def main():
    if not API_KEY:
        print("❌ YOUTUBE_API_KEY が設定されていません。.env を確認してください。")
        return

    parser = ArgumentParser()
    parser.add_argument("--limit",           type=int, default=0)
    parser.add_argument("--artist",          type=str, default="")
    parser.add_argument("--force",           action="store_true")
    parser.add_argument("--show-unverified", action="store_true")
    parser.add_argument("--verify",          type=str, default="")
    parser.add_argument("--reject",          type=str, default="")
    args = parser.parse_args()

    with open(DATA_FILE, encoding="utf-8") as f:
        db = json.load(f)

    if args.show_unverified:
        show_unverified(db)
        return

    if args.verify:
        if update_by_track_id(db, args.verify, True):
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, separators=(",", ":"))
        return

    if args.reject:
        if update_by_track_id(db, args.reject, False):
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, separators=(",", ":"))
        return

    targets = []
    for mmdd, tracks in db.items():
        for track in tracks:
            if args.artist and track.get("artist", "") != args.artist:
                continue
            links  = track.get("links", {})
            has_id = bool(links.get("youtubeId"))
            if has_id and not args.force:
                continue
            targets.append((mmdd, track))

    if args.limit > 0:
        targets = targets[:args.limit]

    total = len(targets)
    print(f"対象: {total} 件")
    if total > 100:
        print(f"⚠️  1日の無料上限(100件)を超えています。--limit 100 推奨\n")

    updated = confident = skipped = 0

    for i, (mmdd, track) in enumerate(targets, 1):
        title  = track.get("title", "")
        artist = track.get("artist", "")
        print(f"[{i}/{total}] {artist} — {title[:30]}")

        video_id, is_confident = search_youtube(title, artist)

        if video_id:
            if "links" not in track:
                track["links"] = {}
            track["links"]["youtubeId"]       = video_id
            track["links"]["youtubeVerified"] = is_confident
            flag = "✅ 高信頼" if is_confident else "⚠️  要確認"
            print(f"  {flag} {video_id}")
            updated += 1
            if is_confident:
                confident += 1
        else:
            print(f"  - 見つかりませんでした")
            skipped += 1

        if updated % 10 == 0 and updated > 0:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, separators=(",", ":"))
            print(f"  💾 {updated}件保存済み")

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, separators=(",", ":"))

    print(f"\n✨ 完了！")
    print(f"   取得成功: {updated} 件（高信頼: {confident} 件 / 要確認: {updated - confident} 件）")
    print(f"   見つからず: {skipped} 件")
    print(f"   消費ユニット数（目安）: {(updated + skipped) * 100} ユニット")
    print(f"\n要確認の動画を確認: python3 fetch_youtube.py --show-unverified")


if __name__ == "__main__":
    main()
