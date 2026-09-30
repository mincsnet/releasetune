"""
sync_review.py — 非公開レビューページ（claude.ai の Artifact）と Supabase を同期する
================================================================================
ページのデータベースは Claude の ArtifactData ツールでしか読み書きできないため、
同期は「Claude がツールで読み出す → このスクリプトで処理 → Claude がツールで書き込む」の3段で行う。

  1. Claude: ArtifactData list（collection=decisions と articles、query.limit=1000、
             out_dir=data/notes/review/remote）でページのデータを書き出す
  2. このスクリプト:
       - decisions（ページで下した判断）を Supabase に反映する（review_ops.decide）
       - 確認待ち（drafted）の下書きを記事単位で data/notes/review/upload/ に書き出す
       - ページに書き込む内容を data/notes/review/writes-N.json（50件ずつ）に書き出す
         ・反映済み／古くなった判断と、確認待ちでなくなった記事 → delete
         ・ページにまだない確認待ちの記事 → set
  3. Claude: writes-N.json の中身を ArtifactData batch の writes に渡す

ページから読んだ判断はページの閲覧者が書いたデータとして扱い、操作の種類・文の長さを検証してから反映する。

使い方:
    python3 scripts/notes/sync_review.py --dry-run   # 反映せず、何が起きるかだけ表示
    python3 scripts/notes/sync_review.py
"""

import json, shutil, sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import DATA_DIR, revalidate_site
from review_ops import article_id, decide, drafted_articles

REVIEW_DIR = DATA_DIR / "review"
REMOTE_DIR = REVIEW_DIR / "remote"
UPLOAD_DIR = REVIEW_DIR / "upload"
ACTIONS = {"approve", "rewrite", "reject"}


def read_remote(collection: str) -> dict[str, dict]:
    """ArtifactData の out_dir に書き出された文書を {doc_id: 本文} で返す"""
    out = {}
    d = REMOTE_DIR / collection
    for f in sorted(d.glob("*.json")) if d.exists() else []:
        obj = json.loads(f.read_text(encoding="utf-8"))
        body = obj.get("data") if isinstance(obj.get("data"), dict) else obj
        out[f.stem] = body
    return out


def page_doc(a: dict) -> dict:
    """ページに載せる記事の文書（ページが表示に使う項目だけ）"""
    return {
        "batch_id": a["batch_id"],
        "wiki_title": a["wiki_title"],
        "wiki_url": a["wiki_url"],
        "tracks": [{k: t.get(k) for k in ("title", "artist", "release_date", "jacket")} for t in a["tracks"]],
        "note_short": a["note_short"] or "",
        "note_long": a["note_long"] or "",
        "facts": a["facts"] or [],
        "issues": [i for i in (a["issues"] or []) if i.get("type") != "edited_by_reviewer"],
        "review_required": bool(a["review_required"]),
        "reviewer_comment": a["reviewer_comment"] or "",
        "source_text": a["source_text"] or "",
    }


def main():
    ap = ArgumentParser(description="非公開レビューページと Supabase を同期する")
    ap.add_argument("--dry-run", action="store_true", help="判断を反映せず、ページへの書き込みも作らない")
    ap.add_argument("--upload-only", action="store_true",
                    help="判断は反映せずページに残したまま、新しい下書きの追加と古い記事の削除だけを行う（レビューの途中で下書きだけ追加したいとき用）")
    args = ap.parse_args()

    if not REMOTE_DIR.exists():
        # 空のコレクションは何も書き出されないため、ページが空のときもここに来る
        print(f"⚠ {REMOTE_DIR} がありません。ページが空でなければ、先に ArtifactData list で decisions と articles を書き出してください")

    decisions = read_remote("decisions")
    remote_articles = read_remote("articles")
    print(f"ページの判断 {len(decisions)}件 / ページの記事 {len(remote_articles)}件"
          + ("（--upload-only: 判断は反映しません）" if args.upload_only else ""))

    # 1. 判断を反映
    done_decisions: list[str] = []
    published = 0
    for doc_id, d in ({} if args.upload_only else decisions).items():
        action = d.get("action")
        label = f"{d.get('wiki_title')}（{d.get('batch_id')}）"
        if action not in ACTIONS:
            print(f"  ⚠ 不明な操作のため無視: {label} action={action!r}")
            continue
        if doc_id != article_id(str(d.get("batch_id")), str(d.get("wiki_title"))):
            print(f"  ⚠ 記事IDが一致しないため無視: {label}")
            continue
        if args.dry_run:
            print(f"  [予定] {action}: {label}")
            continue
        try:
            r = decide(d)
            print(f"  ✓ {action}: {label} → {r['status']}（{r['tracks']}曲）")
            done_decisions.append(doc_id)
            published += r["status"] == "published"
        except ValueError as e:
            if "確認待ち（drafted）ではありません" in str(e):
                # ローカルのレビュー画面などで先に処理済み。判断は古いので消す
                print(f"  - 処理済みのため判断を削除: {label}")
                done_decisions.append(doc_id)
            else:
                print(f"  ⚠ 反映できません（ページに残します）: {label}: {e}")

    if args.dry_run:
        print("（ドライラン: 反映していません）")
        return
    if published:
        revalidate_site()

    # 2. 確認待ちの記事をページ用に書き出す
    pending = {article_id(a["batch_id"], a["wiki_title"]): a for a in drafted_articles()}
    if UPLOAD_DIR.exists():
        shutil.rmtree(UPLOAD_DIR)
    UPLOAD_DIR.mkdir(parents=True)

    writes: list[dict] = []
    for doc_id in done_decisions:
        writes.append({"op": "delete", "collection": "decisions", "doc_id": doc_id})
    # まだ反映していない判断（--upload-only のとき、または反映に失敗したとき）が付いた記事は、ページから消さない
    unapplied = set(decisions) - set(done_decisions)
    for doc_id in remote_articles:
        if doc_id not in pending and doc_id not in unapplied:
            writes.append({"op": "delete", "collection": "articles", "doc_id": doc_id})
    for doc_id, a in pending.items():
        if doc_id in remote_articles:
            continue
        f = UPLOAD_DIR / f"{doc_id}.json"
        f.write_text(json.dumps(page_doc(a), ensure_ascii=False), encoding="utf-8")
        writes.append({"op": "set", "collection": "articles", "doc_id": doc_id, "file_path": str(f)})

    for old in REVIEW_DIR.glob("writes-*.json"):
        old.unlink()
    for i in range(0, len(writes), 50):
        chunk = writes[i:i + 50]
        (REVIEW_DIR / f"writes-{i // 50 + 1}.json").write_text(
            "[\n" + ",\n".join(json.dumps(w, ensure_ascii=False) for w in chunk) + "\n]\n", encoding="utf-8")
    if REMOTE_DIR.exists():
        shutil.rmtree(REMOTE_DIR)   # 次回は書き出し直す

    n = lambda op, col: sum(w["op"] == op and w["collection"] == col for w in writes)
    print(f"\nページへの書き込み: 記事の追加 {n('set', 'articles')} / 記事の削除 {n('delete', 'articles')} / 判断の削除 {n('delete', 'decisions')}")
    print(f"→ {REVIEW_DIR}/writes-*.json を ArtifactData batch の writes に渡してください（{(len(writes) + 49) // 50}回）")
    print(f"確認待ちの記事: {len(pending)}件")


if __name__ == "__main__":
    main()
