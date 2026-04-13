"""
fetch_debuts.py — MusicBrainz からアーティストのデビュー日を収集
================================================================
tracks.json に含まれるアーティストのデビュー日（最初のリリース日）を
MusicBrainz API から取得し、debut_artists.csv に保存する。

使い方:
  python3 fetch_debuts.py                  # 全アーティスト対象
  python3 fetch_debuts.py --limit 50       # 先頭50件のみ（テスト）
  python3 fetch_debuts.py --artist "欅坂46" # 1アーティスト指定

出力: debut_artists.csv（なければ新規作成、あれば追記・上書き）
"""

import json, csv, time, unicodedata
from pathlib import Path
from argparse import ArgumentParser
import requests

DATA_FILE  = Path("data/tracks.json")
OUTPUT_CSV = Path("debut_artists.csv")
SLEEP_MB   = 1.2  # MusicBrainz: 1 req/sec

MB_HEADERS = {
    "User-Agent": "ReleaseTune/1.0 ( https://releasetune.com )",
    "Accept": "application/json",
}


# ── MusicBrainz API ────────────────────────────────────────────

def mb_search_artist(name: str) -> dict | None:
    """アーティスト名でMusicBrainzを検索し最初の候補を返す"""
    try:
        resp = requests.get(
            "https://musicbrainz.org/ws/2/artist",
            headers=MB_HEADERS,
            params={
                "query": f'artist:"{name}" AND country:JP',
                "limit": 5,
                "fmt": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        time.sleep(SLEEP_MB)
        artists = resp.json().get("artists", [])
        if not artists:
            # 日本限定で見つからない場合は国指定なしで再検索
            resp2 = requests.get(
                "https://musicbrainz.org/ws/2/artist",
                headers=MB_HEADERS,
                params={
                    "query": f'artist:"{name}"',
                    "limit": 5,
                    "fmt": "json",
                },
                timeout=15,
            )
            resp2.raise_for_status()
            time.sleep(SLEEP_MB)
            artists = resp2.json().get("artists", [])

        if not artists:
            return None

        # 名前の一致度が高いものを選ぶ
        name_norm = unicodedata.normalize("NFKC", name).lower()
        for a in artists:
            a_norm = unicodedata.normalize("NFKC", a.get("name", "")).lower()
            if a_norm == name_norm:
                return a
        # 完全一致がなければ先頭を返す
        return artists[0]

    except Exception as e:
        print(f"    [MB] 検索エラー: {e}")
        return None


def mb_get_first_release(mbid: str) -> dict | None:
    """
    アーティストのMBIDから最初のリリース情報を取得する。
    release-groupsのearliest-release-dateを使う。
    """
    try:
        resp = requests.get(
            f"https://musicbrainz.org/ws/2/artist/{mbid}",
            headers=MB_HEADERS,
            params={
                "inc": "release-groups",
                "fmt": "json",
            },
            timeout=15,
        )
        resp.raise_for_status()
        time.sleep(SLEEP_MB)
        data = resp.json()

        release_groups = data.get("release-groups", [])
        if not release_groups:
            return None

        # Single / EP / Album の順で最古のリリースを探す
        singles = [
            rg for rg in release_groups
            if rg.get("primary-type") in ("Single", "EP")
            and rg.get("first-release-date", "")
        ]
        all_rg = [
            rg for rg in release_groups
            if rg.get("first-release-date", "")
        ]

        candidates = singles if singles else all_rg
        if not candidates:
            return None

        # 最古のリリースを選択
        oldest = min(candidates, key=lambda r: r.get("first-release-date", "9999"))
        return {
            "date": oldest.get("first-release-date", ""),
            "title": oldest.get("title", ""),
            "type": oldest.get("primary-type", ""),
        }

    except Exception as e:
        print(f"    [MB] リリース取得エラー: {e}")
        return None


# ── CSV 読み書き ────────────────────────────────────────────────

def load_existing_csv() -> dict[str, dict]:
    """既存CSVを読み込んでアーティスト名をキーにしたdictを返す"""
    if not OUTPUT_CSV.exists():
        return {}
    result = {}
    with open(OUTPUT_CSV, encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("artist"):
                result[row["artist"]] = row
    return result


def save_csv(data: dict[str, dict]) -> None:
    """dictをCSVに保存"""
    rows = sorted(data.values(), key=lambda r: r.get("artist", ""))
    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["artist", "debut_date", "debut_track", "mbid", "verified"])
        writer.writeheader()
        writer.writerows(rows)


# ── メイン ─────────────────────────────────────────────────────

def get_all_artists() -> list[str]:
    """tracks.json から全アーティスト名を取得"""
    with open(DATA_FILE, encoding="utf-8") as f:
        db = json.load(f)
    artists = set()
    for tracks in db.values():
        for t in tracks:
            if t.get("artist"):
                artists.add(t["artist"])
    # コラボ表記（&、feat.等）は除外気味に
    filtered = [
        a for a in sorted(artists)
        if " & " not in a and " feat." not in a.lower()
    ]
    return filtered


def fetch_debut(artist_name: str) -> dict | None:
    """1アーティストのデビュー情報を取得"""
    print(f"  検索中: {artist_name}")
    mb_artist = mb_search_artist(artist_name)
    if not mb_artist:
        print(f"    → MusicBrainzで見つかりません")
        return None

    mbid = mb_artist.get("id", "")
    mb_name = mb_artist.get("name", "")
    print(f"    → MB: {mb_name} ({mbid[:8]}...)")

    release = mb_get_first_release(mbid)
    if not release or not release.get("date"):
        print(f"    → リリース日が取得できませんでした")
        return None

    debut_date = release["date"]
    # YYYY形式（年のみ）は除外
    if len(debut_date) < 7:
        print(f"    → 日付が不完全: {debut_date}")
        return None

    print(f"    → デビュー日: {debut_date} / {release['title']}")
    return {
        "artist": artist_name,
        "debut_date": debut_date,
        "debut_track": release["title"],
        "mbid": mbid,
        "verified": "false",
    }


def main():
    parser = ArgumentParser(description="MusicBrainzからデビュー日を収集")
    parser.add_argument("--limit",  type=int, default=0,   help="処理件数上限（0=全件）")
    parser.add_argument("--artist", type=str, default="",  help="アーティスト名を直接指定")
    parser.add_argument("--force",  action="store_true",   help="既存データを上書き")
    args = parser.parse_args()

    # 既存データ読み込み
    existing = load_existing_csv()
    print(f"既存データ: {len(existing)} 件")

    if args.artist:
        targets = [args.artist]
    else:
        all_artists = get_all_artists()
        if args.limit > 0:
            all_artists = all_artists[:args.limit]
        # --force でなければ未取得のみ対象
        if not args.force:
            targets = [a for a in all_artists if a not in existing]
        else:
            targets = all_artists
        print(f"対象: {len(targets)} 件（全{len(all_artists)}件中）")

    updated = 0
    for i, artist in enumerate(targets, 1):
        print(f"\n[{i}/{len(targets)}] {artist}")
        result = fetch_debut(artist)
        if result:
            existing[artist] = result
            updated += 1
            # 10件ごとに保存
            if updated % 10 == 0:
                save_csv(existing)
                print(f"  💾 {updated}件保存済み")
        time.sleep(0.5)

    save_csv(existing)
    print(f"\n✨ 完了！")
    print(f"   新規取得: {updated} 件")
    print(f"   合計: {len(existing)} 件 → {OUTPUT_CSV}")
    print(f"\n   verified: false の項目は内容確認をお願いします。")
    print(f"   手動で修正する場合は verified を true に変更してください。")


if __name__ == "__main__":
    main()
