"""
fix_japanese_titles.py — 英語タイトルを日本語タイトルに修正
================================================================
iTunes Search API で曲名＋アーティストを再検索し、
日本語タイトルが存在する場合は上書きする。

対象: title に日本語が含まれていないもの（英語表記になっているもの）

使い方:
  python3 fix_japanese_titles.py
  python3 fix_japanese_titles.py --limit 500   # 先頭500件のみ（テスト用）

出力: data/tracks.json を上書き（1000件ごとに自動保存）
"""

import json, re, time, unicodedata
from pathlib import Path
from argparse import ArgumentParser
import requests

DATA_FILE = Path("data/tracks.json")
SLEEP     = 2.0   # iTunes API レートリミット対策

def has_japanese(s: str) -> bool:
    return bool(re.search(r'[\u3040-\u9FFF]', s))

def normalize(s: str) -> str:
    return unicodedata.normalize("NFKC", s).lower().strip()

def itunes_search_ja(title: str, artist: str) -> dict | None:
    """
    iTunes Search API で日本語タイトルを検索。
    country=JP&lang=ja_jp で日本語優先の結果を取得。
    """
    try:
        resp = requests.get(
            "https://itunes.apple.com/search",
            params={
                "term":    f"{artist} {title}",
                "country": "JP",
                "media":   "music",
                "entity":  "album",
                "limit":   10,
                "lang":    "ja_jp",
            },
            timeout=10,
        )
        resp.raise_for_status()
        results = resp.json().get("results", [])
        time.sleep(SLEEP)
    except Exception as e:
        print(f"  [iTunes] エラー: {e}")
        return None

    if not results:
        return None

    artist_norm = normalize(artist)
    title_norm  = normalize(title)

    # ベスト盤・ライブ盤・コンピレーションは除外
    EXCLUDE = ["best", "ベスト", "live", "ライブ", "collection",
               "anthology", "complete", "special", "golden", "all time"]

    def is_excluded(title: str) -> bool:
        t = title.lower()
        return any(kw in t for kw in EXCLUDE)

    # アーティスト名が完全に一致 かつ 日本語タイトル かつ 除外なし
    for r in results:
        r_artist = normalize(r.get("artistName", ""))
        r_title  = r.get("collectionName", "")
        # アーティスト名の一致度を厳しく（部分一致ではなく包含関係）
        artist_match = (
            r_artist == artist_norm or
            r_artist.startswith(artist_norm) or
            artist_norm.startswith(r_artist)
        )
        if artist_match and has_japanese(r_title) and not is_excluded(r_title):
            return r

    return None


def fix_titles(limit: int | None = None):
    with open(DATA_FILE, encoding="utf-8") as f:
        db = json.load(f)

    # 英語タイトルのトラックを収集
    targets = []
    for mmdd, tracks in db.items():
        for t in tracks:
            if not has_japanese(t.get("title", "")):
                targets.append((mmdd, t))

    print(f"英語タイトルのトラック: {len(targets):,} 件")

    if limit:
        targets = targets[:limit]
        print(f"処理対象: {limit} 件（--limit 指定）")

    fixed   = 0
    skipped = 0

    for i, (mmdd, track) in enumerate(targets, 1):
        title  = track.get("title", "")
        artist = track.get("artist", "")

        # タイトルからサフィックスを除いてコアタイトルで検索
        core = re.sub(r'\s*[-–]\s*(EP|Single|Album)$', '', title, flags=re.IGNORECASE).strip()
        core = re.sub(r'\s*\(.*?\)$', '', core).strip()

        result = itunes_search_ja(core, artist)

        if result:
            ja_title = result.get("collectionName", "")
            if ja_title and has_japanese(ja_title) and ja_title != title:
                # ジャケット・Apple Musicリンクも更新
                old_title = track["title"]
                track["title"] = ja_title
                jacket = result.get("artworkUrl100", "").replace("100x100bb", "600x600bb")
                if jacket:
                    track["jacket"] = jacket
                apple_url = result.get("collectionViewUrl", "")
                if apple_url:
                    track["links"]["apple"] = apple_url
                fixed += 1
                print(f"  [{i}/{len(targets)}] ✓ {old_title} → {ja_title}")
            else:
                skipped += 1
        else:
            skipped += 1

        # 1000件ごとに中間保存
        if i % 1000 == 0:
            with open(DATA_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            print(f"\n  💾 中間保存: {i} 件処理済み（修正 {fixed} 件）\n")

    # 最終保存
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print(f"\n完了:")
    print(f"  処理数: {len(targets):,} 件")
    print(f"  修正数: {fixed:,} 件")
    print(f"  スキップ: {skipped:,} 件")
    print(f"  ファイル: {DATA_FILE}")


if __name__ == "__main__":
    parser = ArgumentParser(description="英語タイトルを日本語に修正")
    parser.add_argument("--limit", type=int, help="処理件数の上限（テスト用）")
    args = parser.parse_args()
    fix_titles(limit=args.limit)