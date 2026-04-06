"""
fetch_notes.py — Wikipedia から楽曲メモ（note）を取得
================================================================
指定アーティストリストに含まれるトラックの note フィールドを
日本語 Wikipedia から自動生成する。

優先抽出:
  1. ドラマ・映画・アニメ・CM タイアップ情報
  2. オリコン・チャート・売上情報
  3. 受賞・認定情報
  4. 上記なければイントロ冒頭2文

使い方:
  python3 fetch_notes.py                    # all_artists_clean.csv の先頭175件
  python3 fetch_notes.py --limit 50         # 先頭50アーティストのみ（テスト）
  python3 fetch_notes.py --artist "スピッツ" # 1アーティスト指定

出力: data/tracks.json を上書き（アーティスト1人ごとに自動保存）
"""

import json, re, time, unicodedata, csv
from pathlib import Path
from argparse import ArgumentParser
import requests

DATA_FILE   = Path("data/tracks.json")
ARTISTS_CSV = Path("all_artists_clean.csv")
SLEEP_WP    = 0.5

# note 抽出キーワード優先順位
PRIORITY_PATTERNS = [
    r"(テレビドラマ|連続テレビ小説|ドラマ|映画|劇場版|アニメ|テレビアニメ|CM|主題歌|挿入歌|エンディング|オープニング|タイアップ|イメージソング)",
    r"(オリコン|チャート|1位|2位|3位|ミリオン|万枚|累計|ストリーミング|億回)",
    r"(日本レコード大賞|ゴールデン|プラチナ|認定|受賞|年間)",
]


# ── Wikipedia API ──────────────────────────────────────────────

def wikipedia_search(title: str, artist: str) -> str | None:
    """Wikipedia でページタイトルを検索"""
    for query in [f"{title} {artist}", title]:
        try:
            resp = requests.get(
                "https://ja.wikipedia.org/w/api.php",
                params={
                    "action":   "query",
                    "list":     "search",
                    "srsearch": query,
                    "srlimit":  5,
                    "format":   "json",
                    "utf8":     1,
                },
                timeout=10,
            )
            resp.raise_for_status()
            hits = resp.json().get("query", {}).get("search", [])
            time.sleep(SLEEP_WP)
        except Exception:
            continue

        if not hits:
            continue

        title_norm = unicodedata.normalize("NFKC", title).lower()
        for hit in hits:
            page_norm = unicodedata.normalize("NFKC", hit.get("title", "")).lower()
            if title_norm in page_norm:
                return hit["title"]

        return hits[0]["title"]
    return None


def wikipedia_intro(page_title: str) -> str | None:
    """Wikipedia ページのイントロ段落を取得"""
    try:
        resp = requests.get(
            "https://ja.wikipedia.org/w/api.php",
            params={
                "action":      "query",
                "titles":      page_title,
                "prop":        "extracts",
                "exintro":     True,
                "explaintext": True,
                "format":      "json",
                "utf8":        1,
            },
            timeout=10,
        )
        resp.raise_for_status()
        pages = resp.json().get("query", {}).get("pages", {})
        time.sleep(SLEEP_WP)
    except Exception:
        return None

    for page in pages.values():
        if page.get("pageid", -1) != -1:
            return page.get("extract", "").strip()
    return None


def extract_note(raw: str) -> str:
    """Wikipedia イントロから note として使いやすい文を抽出"""
    if not raw:
        return ""

    text      = re.sub(r"\n{2,}", "\n", raw).strip()
    sentences = [s.strip() + "。" for s in re.split(r"。", text) if s.strip()]

    priority, others = [], []
    for s in sentences:
        if any(re.search(p, s) for p in PRIORITY_PATTERNS):
            priority.append(s)
        else:
            others.append(s)

    selected = priority[:2] if priority else others[:2]
    note     = "".join(selected)

    if len(note) > 120:
        note = note[:120].rstrip("、。") + "…"
    return note


def get_note(title: str, artist: str) -> str:
    page = wikipedia_search(title, artist)
    if not page:
        return ""
    raw  = wikipedia_intro(page)
    return extract_note(raw)


# ── メイン処理 ─────────────────────────────────────────────────

def load_artist_list(limit: int) -> list[str]:
    if not ARTISTS_CSV.exists():
        print(f"[!] {ARTISTS_CSV} が見つかりません")
        return []
    with open(ARTISTS_CSV, encoding="utf-8") as f:
        artists = [row["artist"].strip() for row in csv.DictReader(f) if row.get("artist")]
    # コラボ表記除外
    artists = [a for a in artists if "," not in a and " & " not in a]
    return artists[:limit]


def process_artist(name: str, db: dict) -> int:
    """アーティストに関連するすべてのトラックの note を取得・更新"""
    updated = 0
    name_norm = unicodedata.normalize("NFKC", name).lower()

    for mmdd, tracks in db.items():
        for track in tracks:
            t_artist = unicodedata.normalize("NFKC", track.get("artist", "")).lower()
            # 日本語名・英語名・ローマ字名の両方でマッチ
            # CSVの名前（例: スピッツ）とデータ上の名前（例: Spitz）が違う場合も対応
            match = (
                name_norm in t_artist or
                t_artist in name_norm or
                name_norm.replace(" ", "") in t_artist.replace(" ", "") or
                t_artist.replace(" ", "") in name_norm.replace(" ", "")
            )
            # 一致しなくてもWikipediaでアーティスト名（データ上の名前）で検索できるよう
            # artist フィールドをそのまま使う
            if not match:
                continue
            # note 検索時はデータ上のアーティスト名を優先して使う
            search_artist = track.get("artist", name)
            # note が空欄のものだけ対象
            if track.get("note", ""):
                continue

            title = track.get("title", "")
            note  = get_note(title, search_artist)
            if note:
                track["note"]          = note
                track["noteVerified"]  = False
                updated += 1
                print(f"    ✓ {title[:30]} → {note[:40]}...")

    return updated


def main():
    parser = ArgumentParser(description="Wikipedia から楽曲メモを取得")
    parser.add_argument("--limit",  type=int, default=175, help="対象アーティスト数（デフォルト: 175）")
    parser.add_argument("--artist", type=str,              help="アーティスト名を直接指定")
    args = parser.parse_args()

    with open(DATA_FILE, encoding="utf-8") as f:
        db = json.load(f)

    if args.artist:
        artists = [args.artist]
    else:
        artists = load_artist_list(args.limit)

    print(f"対象: {len(artists)} アーティスト")
    print(f"既存データ: {sum(len(v) for v in db.values()):,} 件")

    total_updated = 0

    for i, artist in enumerate(artists, 1):
        print(f"\n[{i}/{len(artists)}] {artist}")
        updated = process_artist(artist, db)
        print(f"  → {updated} 件更新")
        total_updated += updated

        # アーティストごとに保存
        with open(DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(db, f, ensure_ascii=False, indent=2)

        time.sleep(1)

    print(f"\n✨ 完了！")
    print(f"   更新件数: {total_updated:,} 件")
    print(f"   ファイル: {DATA_FILE}")
    print(f"   noteVerified: false の項目は内容確認をお願いします。")


if __name__ == "__main__":
    main()