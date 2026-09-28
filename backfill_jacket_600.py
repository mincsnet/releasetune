"""
backfill_jacket_600.py
======================
新着cron（`app/api/cron/new-releases/route.ts`）の不具合で 170x170bb のまま保存された
ジャケットURLを 600x600bb.jpg に書き換える一回限りのバックフィル。
（RSSの画像は最大170x170bbなのに "100x100bb" を置換していたため効いていなかった。cron側は2026-09-28に修正）

Supabase Egress節約のため、取得は id,jacket のみ、更新は Prefer: return=minimal（レスポンス本文なし）。
書き換え後のURLは mzstatic に HEAD して 200 が返ったものだけ更新する。
拡張子は既存データに合わせて .jpg に揃える（600x600のPNGはJPGの約5倍の容量）。

使い方:
    # まずドライラン（Supabaseへの書き込みなし）
    python3 backfill_jacket_600.py --dry-run --limit 20

    # 本実行（対象がなくなるまで全件）
    python3 backfill_jacket_600.py
"""

import os, re, sys
from pathlib import Path
from argparse import ArgumentParser

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SERVICE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")

PAGE_SIZE = 200
SIZE_TOKEN = re.compile(r"/\d+x\d+bb\.\w+$")  # route.ts と同じ置換


def supabase_headers():
    return {
        "apikey":        SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type":  "application/json",
    }


def fetch_page(cursor: str, page_size: int) -> list[dict]:
    params = {
        "select": "id,jacket",
        "jacket": "like.*170x170bb*",
        "order":  "id.asc",
        "limit":  str(page_size),
    }
    if cursor:
        params["id"] = f"gt.{cursor}"
    resp = requests.get(f"{SUPABASE_URL}/rest/v1/tracks", params=params, headers=supabase_headers(), timeout=30)
    resp.raise_for_status()
    return resp.json()


def url_ok(url: str) -> bool:
    try:
        return requests.head(url, timeout=15).status_code == 200
    except requests.RequestException:
        return False


def update_jacket(track_id: str, jacket: str) -> bool:
    resp = requests.patch(
        f"{SUPABASE_URL}/rest/v1/tracks",
        params={"id": f"eq.{track_id}"},
        json={"jacket": jacket},
        headers={**supabase_headers(), "Prefer": "return=minimal"},
        timeout=30,
    )
    return resp.status_code in (200, 204)


def main():
    parser = ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="Supabaseへの書き込みを行わず結果だけ表示")
    parser.add_argument("--limit", type=int, default=0, help="処理する最大件数（0=無制限）")
    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        sys.exit("NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY が .env にありません")

    cursor = ""
    seen = updated = skipped = failed = 0
    while True:
        page_size = min(PAGE_SIZE, args.limit - seen) if args.limit else PAGE_SIZE
        rows = fetch_page(cursor, page_size)
        if not rows:
            break
        cursor = rows[-1]["id"]
        seen += len(rows)

        for row in rows:
            new_url = SIZE_TOKEN.sub("/600x600bb.jpg", row["jacket"], count=1)
            if not url_ok(new_url):
                skipped += 1
                print(f"  [skip] {row['id']} 600x600が取得できない: {new_url}")
                continue
            if not args.dry_run and not update_jacket(row["id"], new_url):
                failed += 1
                print(f"  [fail] {row['id']} 更新失敗")
                continue
            updated += 1
            # 本実行でも1件ずつ出力し、ログを書き換え対象の記録として残す
            tag = "dry" if args.dry_run else "ok"
            print(f"  [{tag}] {row['id']} {row['jacket'].rsplit('/', 1)[-1]} → {new_url.rsplit('/', 1)[-1]}")

        print(f"[page] ~{cursor} 累計 {seen}件（更新{updated} / skip{skipped} / 失敗{failed}）")
        if args.limit and seen >= args.limit:
            break

    mode = "ドライラン" if args.dry_run else "本実行"
    print(f"\n{mode}完了: 対象{seen}件 / 更新{updated} / skip{skipped} / 失敗{failed}")


if __name__ == "__main__":
    main()
