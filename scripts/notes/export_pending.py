"""
export_pending.py — 執筆待ちの記事を data/notes/pending.json に書き出す
======================================================================
track_note_drafts の sourced（未執筆）と rewrite（書き直し依頼）を記事単位にまとめる。
書き直し依頼を先に、残りは収集した順（--by-date なら次のリリース記念日が近い順、--artists なら一覧の順・発売日順）に --limit 件まで。

使い方:
    python3 scripts/notes/export_pending.py --limit 20
    python3 scripts/notes/export_pending.py --blank --out data/notes/muse/muse-2026-11-06.json   # Muse に渡す作業ファイル
    python3 scripts/notes/export_pending.py --blank --mmdd 11-10 --limit 100 --out data/notes/muse/muse-1110.json   # 11月10日の曲だけ
    # 一覧のアーティストの記事を全部、30記事ずつの作業ファイルに（muse-top100-001.json …）。渡し済みのファイルの記事は除く
    python3 scripts/notes/export_pending.py --blank --artists artists.txt --limit 0 --split 30 \
        --exclude data/notes/muse/muse-11*.json --out data/notes/muse/muse-top100.json
"""

import json, sys
from argparse import ArgumentParser
from collections import defaultdict
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, sb_select, sb_select_in, today_jst


def days_to_anniversary(release_date: str, today: date) -> int:
    """次のリリース記念日（今日を含む）までの日数。2月29日の曲は平年は2月28日として数える"""
    _, m, d = map(int, release_date.split("-"))
    for year in (today.year, today.year + 1):
        try:
            day = date(year, m, d)
        except ValueError:
            day = date(year, 2, 28)
        if day >= today:
            return (day - today).days
    raise AssertionError


def primary_artist(a: dict, rank: dict[str, int]) -> str:
    return min((t["artist"] for t in a["tracks"]), key=lambda n: rank.get(n, len(rank)))


def split_by_artist(articles: list[dict], size: int, rank: dict[str, int]) -> list[list[dict]]:
    """並び順を保ったまま size 件ずつに分ける。アーティストの記事がいまのファイルに収まらなければ次のファイルから始める
    （size より多いアーティストは、いまのファイルの残りを埋めてから複数のファイルにまたがる）"""
    runs: list[list[dict]] = []
    for a in articles:
        if runs and primary_artist(runs[-1][0], rank) == primary_artist(a, rank):
            runs[-1].append(a)
        else:
            runs.append([a])
    chunks: list[list[dict]] = [[]]
    for run in runs:
        if chunks[-1] and len(run) <= size and len(chunks[-1]) + len(run) > size:
            chunks.append([])
        for a in run:
            if len(chunks[-1]) >= size:
                chunks.append([])
            chunks[-1].append(a)
    return [c for c in chunks if c]


def main():
    ap = ArgumentParser(description="執筆待ちの記事を書き出す")
    ap.add_argument("--limit", type=int, default=20, help="書き出す記事数（デフォルト: 20。0 なら上限なし）")
    ap.add_argument("--out", default=str(DATA_DIR / "pending.json"))
    ap.add_argument("--by-date", action="store_true",
                    help="次のリリース記念日が近い順に並べる（日付ページや X の紹介に間に合わせたいとき）")
    ap.add_argument("--mmdd", help="この日付（例: 11-10）にリリースされた曲の記事だけを書き出す")
    ap.add_argument("--artists", help="このファイル（1行に1組、DB のアーティスト名）のアーティストの記事だけを、ファイルの順に書き出す")
    ap.add_argument("--exclude", nargs="*", default=[], help="これらの作業ファイルにある記事は書き出さない（Muse に渡し済みの分）")
    ap.add_argument("--split", type=int, help="この記事数ずつ <out の名前>-001.json … に分けて書き出す（同じアーティストはなるべく同じファイルに）")
    ap.add_argument("--blank", action="store_true",
                    help="記事ごとに空の回答欄を付ける（外部の執筆者が埋めて返す作業ファイル用。MUSE.md 参照）")
    args = ap.parse_args()

    rows = sb_select("track_note_drafts", {
        "select": "track_id,status,wiki_title,wiki_url,source_text,note_short,note_long,reviewer_comment,updated_at",
        "status": "in.(sourced,rewrite)",
        "order": "updated_at.asc,track_id.asc",
    })
    tracks = {t["id"]: t for t in sb_select_in("tracks", "id", [r["track_id"] for r in rows],
                                               "id,title,artist,release_date")}

    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["wiki_title"]].append(r)
    if args.mmdd:
        groups = {k: g for k, g in groups.items()
                  if any(r["track_id"] in tracks and tracks[r["track_id"]]["release_date"][5:] == args.mmdd for r in g)}
    excluded = {a["wiki_title"] for f in args.exclude for a in json.loads(Path(f).read_text(encoding="utf-8"))}
    groups = {k: g for k, g in groups.items() if k not in excluded}
    rank: dict[str, int] = {}
    if args.artists:
        names = [l.strip() for l in Path(args.artists).read_text(encoding="utf-8").splitlines() if l.strip()]
        rank = {n: i for i, n in reversed(list(enumerate(names)))}
        groups = {k: g for k, g in groups.items()
                  if any(r["track_id"] in tracks and tracks[r["track_id"]]["artist"] in rank for r in g)}
    today = date.fromisoformat(today_jst())
    def soon(g):
        return min((days_to_anniversary(tracks[r["track_id"]]["release_date"], today)
                    for r in g if r["track_id"] in tracks), default=366)
    def artist_order(g):
        ts = [tracks[r["track_id"]] for r in g if r["track_id"] in tracks]
        return (min(rank.get(t["artist"], len(rank)) for t in ts), min(t["release_date"] for t in ts))
    def sort_key(g):
        if rank:
            return (g[0]["status"] != "rewrite", artist_order(g))
        return (g[0]["status"] != "rewrite", soon(g) if args.by_date else 0, g[0]["updated_at"])
    ordered = sorted(groups.values(), key=sort_key)

    articles = []
    for g in (ordered[:args.limit] if args.limit else ordered):
        head = g[0]
        a = {
            "wiki_title": head["wiki_title"],
            "wiki_url": head["wiki_url"],
            "status": head["status"],
            "tracks": [{k: tracks[r["track_id"]][k] for k in ("id", "title", "artist", "release_date")}
                       for r in g if r["track_id"] in tracks],
            "source_text": head["source_text"],
        }
        if head["status"] == "rewrite":
            a["reviewer_comment"] = head["reviewer_comment"]
            a["previous"] = {"note_short": head["note_short"], "note_long": head["note_long"]}
        if args.blank:
            a.update({"note_short": "", "note_long": "", "facts": [], "skip": False, "skip_reason": ""})
        articles.append(a)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if args.split:
        for i, chunk in enumerate(split_by_artist(articles, args.split, rank), 1):
            f = out.with_name(f"{out.stem}-{i:03d}.json")
            f.write_text(json.dumps(chunk, ensure_ascii=False, indent=1), encoding="utf-8")
            artists = list(dict.fromkeys(primary_artist(a, rank) for a in chunk))
            print(f"  {f.name}: {len(chunk)}記事 / {'・'.join(artists[:6])}{' ほか' if len(artists) > 6 else ''}")
    else:
        out.write_text(json.dumps(articles, ensure_ascii=False, indent=1), encoding="utf-8")
    n_rewrite = sum(a["status"] == "rewrite" for a in articles)
    print(f"書き出し: {len(articles)}記事（書き直し {n_rewrite} / 新規 {len(articles) - n_rewrite}）→ {out}"
          + (f"（{args.split}記事ずつに分割）" if args.split else ""))
    print(f"執筆待ちの残り: {max(len(ordered) - len(articles), 0)}記事" + (f"（{args.mmdd} の曲のうち）" if args.mmdd else ""))


if __name__ == "__main__":
    main()
