"""
scripts/titles/fix_search_slash.py — Amazon Music・Spotify の検索URLの検索語にある「/」を空白にする
===================================================================================================
背景:
  過去の一括収集（collect_itunes.py など）は検索語を requests.utils.quote（safe="/" が既定）で
  エンコードしたため、アーティスト名・曲名の「/」がパス区切りとしてそのまま残っている。
    Amazon Music: 「/」のまま → トップページへリダイレクト、%2F → 404、空白 → 正しく検索できる
    Spotify     : 「/」のまま → 「エラーが発生したようです」、%2F・空白 → 正しく検索できる
  どちらも空白に置き換える（fix_ja_titles.py の rewrite_search_url と同じ方針）。
  YouTube の検索URLは検索語がクエリ文字列なので「/」のままで検索でき、対象外。直リンクも対象外。

使い方（リポジトリのルートで実行）:
  python3 scripts/titles/fix_search_slash.py apply --dry-run --limit 20
  python3 scripts/titles/fix_search_slash.py apply --ids 1001903677,1386699254   # 試験反映
  python3 scripts/titles/fix_search_slash.py apply
  python3 scripts/titles/fix_search_slash.py revert data/titles/slash_fixed_YYYYmmdd-HHMMSS.jsonl

変更前の値は data/titles/slash_fixed_*.jsonl に残す。revert は反映後に値が変わっていない列だけ戻す
（spotify-backfill cron が検索URLを直リンクに置き換えた列はそのままにする）。
"""

import json, re, sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notes"))
from common import ROOT, sb_select, sb_select_in, sb_update  # noqa: E402

DATA_DIR = ROOT / "data" / "titles"

# 検索URLの接頭辞（この後ろが検索語）
SEARCH_PREFIXES = {
    "amazon":  "https://music.amazon.co.jp/search/",
    "spotify": "https://open.spotify.com/search/",
}


def fix_search_url(url: str | None, prefix: str) -> str | None:
    """検索語に「/」を含む検索URLを、「/」を空白にしたURLにする。直す必要がなければ None"""
    if not url or not url.startswith(prefix) or "/" not in url[len(prefix):]:
        return None
    q = unquote(url[len(prefix):]).replace("/", " ")
    return prefix + quote(re.sub(r"\s+", " ", q).strip(), safe="")


def patch_for(row: dict) -> dict:
    patch = {}
    for col, prefix in SEARCH_PREFIXES.items():
        url = fix_search_url(row[col], prefix)
        if url:
            patch[col] = url
    return patch


def cmd_apply(args) -> None:
    if args.ids:
        rows = sb_select_in("tracks", "id", args.ids.split(","), "id,title,artist,amazon,spotify")
    else:
        rows = sb_select("tracks", {"select": "id,title,artist,amazon,spotify", "order": "id.asc"})
    targets = [(r, p) for r in rows if (p := patch_for(r))]
    counts = {col: sum(col in p for _, p in targets) for col in SEARCH_PREFIXES}
    print(f"対象: {len(targets):,}行（" + " / ".join(f"{c} {n:,}件" for c, n in counts.items()) + "）"
          + (" ※ドライラン" if args.dry_run else ""))
    if args.limit:
        targets = targets[:args.limit]

    log_path = DATA_DIR / f"slash_fixed_{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    if not args.dry_run:
        log_path.parent.mkdir(parents=True, exist_ok=True)
    log = None if args.dry_run else open(log_path, "w", encoding="utf-8")
    try:
        for n, (row, patch) in enumerate(targets, 1):
            if args.dry_run:
                print(f"  {row['id']} {row['artist']} | {row['title']}")
                for col, url in patch.items():
                    print(f"    {col:7}: {unquote(row[col][len(SEARCH_PREFIXES[col]):])!r}"
                          f" → {unquote(url[len(SEARCH_PREFIXES[col]):])!r}")
                continue
            sb_update("tracks", {"id": f"eq.{row['id']}"}, patch)
            log.write(json.dumps({"id": row["id"], "before": {k: row[k] for k in patch}, "after": patch},
                                 ensure_ascii=False) + "\n")
            log.flush()
            if n % 200 == 0:
                print(f"  {n:,} / {len(targets):,}")
    finally:
        if log:
            log.close()
    if not args.dry_run:
        print(f"反映: {len(targets):,}行")
        print(f"変更前の値: {log_path.relative_to(ROOT)}（戻すときは revert に渡す）")


def cmd_revert(args) -> None:
    entries = [json.loads(line) for line in open(args.log, encoding="utf-8") if line.strip()]
    current = {r["id"]: r for r in sb_select_in(
        "tracks", "id", [e["id"] for e in entries], "id," + ",".join(SEARCH_PREFIXES))}
    reverted = skipped = 0
    for e in entries:
        row = current.get(e["id"], {})
        patch = {col: before for col, before in e["before"].items() if row.get(col) == e["after"][col]}
        skipped += len(e["before"]) - len(patch)
        if patch:
            sb_update("tracks", {"id": f"eq.{e['id']}"}, patch)
            reverted += len(patch)
    print(f"元に戻した: {reverted:,}件 / スキップ（反映後に値が変わった）: {skipped:,}件")


def main() -> None:
    parser = ArgumentParser(description="Amazon Music・Spotify の検索URLの検索語にある「/」を空白にする")
    sub = parser.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("apply")
    p.add_argument("--ids", default="", help="対象にする曲のID（カンマ区切り、試験反映用）")
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--dry-run", action="store_true")
    p.set_defaults(func=cmd_apply)
    p = sub.add_parser("revert")
    p.add_argument("log", type=Path)
    p.set_defaults(func=cmd_revert)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
