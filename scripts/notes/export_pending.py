"""
export_pending.py — 執筆待ちの記事を data/notes/pending.json に書き出す
======================================================================
track_note_drafts の sourced（未執筆）と rewrite（書き直し依頼）を記事単位にまとめる。
書き直し依頼を先に、残りは収集した順に --limit 件まで。

使い方:
    python3 scripts/notes/export_pending.py --limit 20
"""

import json, sys
from argparse import ArgumentParser
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, sb_select, sb_select_in


def main():
    ap = ArgumentParser(description="執筆待ちの記事を書き出す")
    ap.add_argument("--limit", type=int, default=20, help="書き出す記事数（デフォルト: 20）")
    ap.add_argument("--out", default=str(DATA_DIR / "pending.json"))
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
    ordered = sorted(groups.values(), key=lambda g: (g[0]["status"] != "rewrite", g[0]["updated_at"]))

    articles = []
    for g in ordered[:args.limit]:
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
        articles.append(a)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(articles, ensure_ascii=False, indent=1), encoding="utf-8")
    n_rewrite = sum(a["status"] == "rewrite" for a in articles)
    print(f"書き出し: {len(articles)}記事（書き直し {n_rewrite} / 新規 {len(articles) - n_rewrite}）→ {out}")
    print(f"執筆待ちの残り: {max(len(ordered) - len(articles), 0)}記事")


if __name__ == "__main__":
    main()
