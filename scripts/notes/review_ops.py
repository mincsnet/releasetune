"""
review_ops.py — レビューの判断（承認・書き直し依頼・掲載しない）を Supabase に反映する共通処理
============================================================================================
ローカルのレビュー画面（review_server.py）と、非公開ページの判断を同期する sync_review.py の両方が使う。
"""

import hashlib, sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import now_iso, sb_in, sb_select, sb_select_in, sb_update

BATCH_STATUSES = "in.(drafted,published,rewrite,rejected,insufficient)"
SHORT_LIMIT, LONG_LIMIT = 200, 1000   # 手で直した文の上限（明らかな入力ミスを弾くためのもの）


def article_id(batch_id: str, wiki_title: str) -> str:
    """非公開ページのデータベースで使う記事ID（記事名には「/」などが入るためハッシュにする）"""
    return hashlib.sha1(f"{batch_id}|{wiki_title}".encode()).hexdigest()[:20]


def list_batches() -> list[dict]:
    rows = sb_select("track_note_drafts", {
        "select": "batch_id,wiki_title,status,review_required",
        "batch_id": "not.is.null", "status": BATCH_STATUSES,
    })
    arts: dict[tuple, dict] = {}
    for r in rows:
        arts.setdefault((r["batch_id"], r["wiki_title"]), r)
    out: dict[str, dict] = defaultdict(lambda: defaultdict(int))
    for (b, _), r in arts.items():
        c = out[b]
        c["articles"] += 1
        c[r["status"]] += 1
        if r["status"] == "drafted":
            c["need_review" if r["review_required"] else "unsampled"] += 1
    return [{"batch_id": b, **c} for b, c in sorted(out.items(), reverse=True)]


def articles(filters: dict) -> list[dict]:
    """記事単位にまとめた下書き（tracks にジャケット等を付ける）"""
    rows = sb_select("track_note_drafts", {
        "select": "track_id,status,batch_id,wiki_title,wiki_url,source_text,note_short,note_long,facts,issues,review_required,reviewer_comment",
        "order": "wiki_title.asc", **filters,
    })
    tracks = {t["id"]: t for t in sb_select_in("tracks", "id", [r["track_id"] for r in rows],
                                               "id,title,artist,release_date,jacket")}
    groups: dict[tuple, dict] = {}
    for r in rows:
        g = groups.setdefault((r["batch_id"], r["wiki_title"]),
                              {**{k: r[k] for k in r if k != "track_id"}, "tracks": []})
        if r["track_id"] in tracks:
            g["tracks"].append(tracks[r["track_id"]])
    return sorted(groups.values(), key=lambda g: (not g["review_required"], g["tracks"][0]["release_date"] if g["tracks"] else ""))


def batch_articles(batch_id: str) -> list[dict]:
    return articles({"batch_id": f"eq.{batch_id}", "status": BATCH_STATUSES})


def drafted_articles() -> list[dict]:
    return articles({"status": "eq.drafted"})


def article_rows(batch_id: str, wiki_title: str, status: str = "drafted") -> list[dict]:
    return sb_select("track_note_drafts", {
        "select": "track_id,wiki_title,wiki_url,note_short,note_long,issues",
        "batch_id": f"eq.{batch_id}", "wiki_title": f"eq.{wiki_title}", "status": f"eq.{status}",
    })


def publish(rows: list[dict], note_short: str, note_long: str, comment: str) -> int:
    ids = [r["track_id"] for r in rows]
    head = rows[0]
    sb_update("tracks", {"id": sb_in(ids)}, {
        "note": note_short,
        "note_long": note_long or None,
        "note_source_title": head["wiki_title"],
        "note_source_url": head["wiki_url"],
        "note_verified": True,
    })
    issues = head["issues"] or []
    if note_short != (head["note_short"] or "") or (note_long or None) != head["note_long"]:
        # レビューで直した内容は執筆ルールの改善に使うので、元の下書きを残しておく
        issues = issues + [{"type": "edited_by_reviewer", "detail": "レビューで修正",
                            "before_short": head["note_short"], "before_long": head["note_long"]}]
    sb_update("track_note_drafts", {"track_id": sb_in(ids)}, {
        "status": "published", "note_short": note_short, "note_long": note_long or None,
        "issues": issues, "reviewer_comment": comment or None, "updated_at": now_iso(),
    })
    return len(ids)


def decide(p: dict) -> dict:
    """p: {batch_id, wiki_title, action: approve|rewrite|reject, note_short, note_long, comment}"""
    batch_id, title, action = p.get("batch_id"), p.get("wiki_title"), p.get("action")
    if not isinstance(batch_id, str) or not isinstance(title, str):
        raise ValueError("batch_id と wiki_title が必要です")
    rows = article_rows(batch_id, title)
    if not rows:
        raise ValueError("この記事は確認待ち（drafted）ではありません")
    comment = str(p.get("comment") or "").strip()
    if action == "approve":
        short = str(p.get("note_short") or "").strip()
        long_ = str(p.get("note_long") or "").strip()
        if not short:
            raise ValueError("短文が空です")
        if len(short) > SHORT_LIMIT or len(long_) > LONG_LIMIT:
            raise ValueError("文が長すぎます")
        n = publish(rows, short, long_, comment)
        return {"status": "published", "tracks": n}
    if action in ("rewrite", "reject"):
        if action == "rewrite" and not comment:
            raise ValueError("書き直し依頼にはコメントが必要です")
        status = "rewrite" if action == "rewrite" else "rejected"
        sb_update("track_note_drafts", {"track_id": sb_in([r["track_id"] for r in rows])},
                  {"status": status, "reviewer_comment": comment or None, "updated_at": now_iso()})
        return {"status": status, "tracks": len(rows)}
    raise ValueError(f"不明な操作: {action}")


def approve_rest(batch_id: str) -> dict:
    rows = sb_select("track_note_drafts", {
        "select": "track_id,wiki_title,wiki_url,note_short,note_long,issues,review_required",
        "batch_id": f"eq.{batch_id}", "status": "eq.drafted",
    })
    if any(r["review_required"] for r in rows):
        raise ValueError("要確認の記事が残っています")
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["wiki_title"]].append(r)
    n = sum(publish(g, g[0]["note_short"], g[0]["note_long"] or "", "") for g in groups.values())
    return {"articles": len(groups), "tracks": n}
