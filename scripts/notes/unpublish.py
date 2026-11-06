"""
unpublish.py — 公開済みの紹介文をサイトから取り消す
====================================================
自動公開した記事などに誤りが見つかったときに使う。tracks の紹介文と出典を空にし、
下書きを書き直し依頼（--rewrite、次の執筆に回る）か「掲載しない」にする。

使い方:
    python3 scripts/notes/unpublish.py "箱根八里の半次郎" --comment "受賞者が歌手なのに曲の受賞と書いている" --rewrite
    python3 scripts/notes/unpublish.py "箱根八里の半次郎" --comment "出典が別の曲の記事"
"""

import sys
from argparse import ArgumentParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import revalidate_site
from review_ops import unpublish


def main():
    ap = ArgumentParser(description="公開済みの紹介文を取り消す")
    ap.add_argument("wiki_title", help="記事名（出典の Wikipedia 記事名）")
    ap.add_argument("--comment", required=True, help="取り消しの理由（書き直し依頼なら、次の執筆者への指摘になる）")
    ap.add_argument("--rewrite", action="store_true", help="書き直し依頼にする（付けなければ「掲載しない」）")
    args = ap.parse_args()
    try:
        n = unpublish(args.wiki_title, args.comment.strip(), args.rewrite)
    except ValueError as e:
        sys.exit(f"❌ {e}")
    print(f"取り消しました: {args.wiki_title}（{n}曲、{'書き直し依頼' if args.rewrite else '掲載しない'}）")
    revalidate_site()


if __name__ == "__main__":
    main()
