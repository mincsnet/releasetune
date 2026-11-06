"""
auto_publish.py — 事実の照合を通った下書きを、人の確認なしで公開する
=====================================================================
対象は確認待ち（drafted）のうち要確認でない記事（機械チェックの指摘・書き手の申し送りがなく、1割の抜き取りにも入らなかったもの）。

  1. export: 対象の記事を文に分けて data/notes/verify/input.json に書き出す
  2. 照合: 書き手とは別の Claude（サブエージェント）が VERIFY.md に従い、文ごとに出典の根拠を確かめて results.json に書く
  3. apply: 次の条件をすべて満たす記事を公開し、満たさない記事は要確認にしてレビューに回す
     - 出典が DB の曲と同じ作品の記事（same_work）
     - すべての文が出典で裏付けられる（verdict が supported）
     - 賞の記述がない（受賞者の取り違えが起きやすいため、人が確認する）
     - 照合したときから文面が変わっていない

公開の取り消しは unpublish.py。

使い方:
    python3 scripts/notes/auto_publish.py export
    python3 scripts/notes/auto_publish.py apply --dry-run
    python3 scripts/notes/auto_publish.py apply
"""

import json, re, sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, now_iso, revalidate_site, sb_in, sb_update
from review_ops import article_rows, drafted_articles, publish

VERIFY_DIR = DATA_DIR / "verify"
HOLD_WORDS = re.compile(r"賞")


def sentences(text: str) -> list[str]:
    """「。」で文に分ける。作品名の中の「。」（『心が叫びたがってるんだ。』）では区切らない"""
    out, buf, depth = [], "", 0
    for ch in text or "":
        buf += ch
        if ch in "『「":
            depth += 1
        elif ch in "』」":
            depth = max(depth - 1, 0)
        elif ch == "。" and depth == 0:
            out.append(buf.strip())
            buf = ""
    if buf.strip():
        out.append(buf.strip())
    return out


def article_sentences(a: dict) -> list[str]:
    return sentences(a["note_short"] or "") + sentences(a["note_long"] or "")


def targets() -> list[dict]:
    return [a for a in drafted_articles() if not a["review_required"]]


def export(out: Path) -> None:
    arts = targets()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps([{
        "batch_id": a["batch_id"],
        "wiki_title": a["wiki_title"],
        "tracks": [{k: t[k] for k in ("title", "artist", "release_date")} for t in a["tracks"]],
        "sentences": article_sentences(a),
        "source_text": a["source_text"],
    } for a in arts], ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"書き出し: {len(arts)}記事 → {out}")


def judge(a: dict, r: dict | None) -> tuple[str, list[dict]]:
    """('publish' | 'hold' | 'wait', 要確認にする理由)"""
    if r is None:
        return "wait", []
    if [s.get("text") for s in r.get("sentences") or []] != article_sentences(a):
        return "wait", []
    holds = []
    if r.get("same_work") is not True:
        holds.append({"type": "verify", "detail": f"照合: 出典が別の作品の可能性（{r.get('same_work_reason') or '理由なし'}）"})
    for s in r["sentences"]:
        if s.get("verdict") != "supported":
            holds.append({"type": "verify", "detail": f"照合: 根拠が不十分「{s['text']}」（{s.get('reason') or s.get('verdict')}）"})
    if HOLD_WORDS.search((a["note_short"] or "") + (a["note_long"] or "")):
        holds.append({"type": "hold_award", "detail": "賞の記述があるため人が確認"})
    return ("hold" if holds else "publish"), holds


def apply(results_path: Path, dry_run: bool) -> None:
    results = {(r["batch_id"], r["wiki_title"]): r
               for r in json.loads(results_path.read_text(encoding="utf-8"))}
    counts = {"publish": 0, "hold": 0, "wait": 0}
    for a in targets():
        verdict, holds = judge(a, results.get((a["batch_id"], a["wiki_title"])))
        counts[verdict] += 1
        label = f"{a['wiki_title']}（{a['batch_id']}）"
        if verdict == "wait":
            print(f"[未照合] {label}: 照合結果がないか、照合後に文面が変わった。export からやり直す")
            continue
        print(f"[{'公開' if verdict == 'publish' else '要確認へ'}] {label}")
        for h in holds:
            print(f"    ⚠ {h['detail']}")
        if dry_run:
            continue
        rows = article_rows(a["batch_id"], a["wiki_title"])
        if verdict == "publish":
            publish(rows, a["note_short"], a["note_long"] or "", "",
                    [{"type": "auto_published", "detail": "機械チェックと事実の照合を通過して自動公開"}])
        else:
            sb_update("track_note_drafts", {"track_id": sb_in([r["track_id"] for r in rows])},
                      {"review_required": True, "issues": (a["issues"] or []) + holds, "updated_at": now_iso()})
    print(f"\n公開 {counts['publish']} / 要確認へ {counts['hold']} / 未照合 {counts['wait']}"
          + ("（ドライラン: 反映していません）" if dry_run else ""))
    if counts["publish"] and not dry_run:
        revalidate_site()


def main():
    ap = ArgumentParser(description="事実の照合を通った下書きを公開する")
    sub = ap.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export", help="照合用に書き出す")
    e.add_argument("--out", default=str(VERIFY_DIR / "input.json"))
    p = sub.add_parser("apply", help="照合結果を反映する")
    p.add_argument("results", nargs="?", default=str(VERIFY_DIR / "results.json"))
    p.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()
    if args.cmd == "export":
        export(Path(args.out))
    else:
        apply(Path(args.results), args.dry_run)


if __name__ == "__main__":
    main()
