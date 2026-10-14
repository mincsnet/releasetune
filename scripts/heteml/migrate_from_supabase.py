"""
Supabase → ヘテムル（MySQL）のデータ移行
========================================

  python3 scripts/heteml/migrate_from_supabase.py export
      Supabase の全行（tracks・track_note_drafts）を data/backup/supabase_YYYYMMDD-HHMMSS.jsonl に書き出す。
      このファイルがそのまま移行元データ兼バックアップになる（data/backup/ は git 管理外）。

  php heteml/bin/import_snapshot.php <ファイル>
      書き出したファイルを MySQL に入れる（ヘテムルでは SSH 越しに実行する）。何度でもやり直せる。

  python3 scripts/heteml/migrate_from_supabase.py compare <ファイル>
      ヘテムルの DB API（.env の HETEML_API_URL）から全行を読み、書き出したファイルと列ごとに比べる。
      差分が 0 件なら移行は正しい（API の返す値の形が Supabase と同じことの確認も兼ねる）。
"""

import json, sys
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notes"))
from common import ROOT, SUPABASE_URL, http_request, heteml_db, supabase_headers  # noqa: E402

TABLES = {"tracks": "id", "track_note_drafts": "track_id"}
TIMESTAMP_COLUMNS = {"updated_at"}
BACKUP_DIR = ROOT / "data" / "backup"
PAGE = 1000


def fetch_supabase(table: str, pk: str) -> list[dict]:
    rows: list[dict] = []
    while True:
        resp = http_request("get", f"{SUPABASE_URL}/rest/v1/{table}", headers=supabase_headers(), timeout=60,
                            params={"select": "*", "order": f"{pk}.asc", "limit": str(PAGE), "offset": str(len(rows))})
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < PAGE:
            return rows


def fetch_heteml(table: str, pk: str) -> list[dict]:
    rows: list[dict] = []
    while True:
        page = heteml_db({"op": "select", "table": table,
                          "params": {"select": "*", "order": f"{pk}.asc", "limit": str(PAGE), "offset": str(len(rows))}})
        rows.extend(page)
        if len(page) < PAGE:
            return rows


def cmd_export() -> None:
    BACKUP_DIR.mkdir(parents=True, exist_ok=True)
    path = BACKUP_DIR / f"supabase_{datetime.now().strftime('%Y%m%d-%H%M%S')}.jsonl"
    with path.open("w", encoding="utf-8") as f:
        for table, pk in TABLES.items():
            rows = fetch_supabase(table, pk)
            for r in rows:
                f.write(json.dumps({"t": table, "r": r}, ensure_ascii=False) + "\n")
            print(f"{table}: {len(rows):,} 行")
    print(f"書き出し: {path.relative_to(ROOT)}（{path.stat().st_size / 1e6:.1f} MB）")


def normalize(col: str, v) -> str:
    # 日時は表記の細部（秒未満の桁数）ではなく時刻として比べる
    if col in TIMESTAMP_COLUMNS and isinstance(v, str):
        return datetime.fromisoformat(v).isoformat()
    # 型まで比べる（Python では True == 1、{} と [] の取り違えも見逃さないよう JSON の表記で比べる）
    return json.dumps(v, sort_keys=True, ensure_ascii=False)


def cmd_compare(path: Path) -> None:
    snapshot: dict[str, dict[str, dict]] = {t: {} for t in TABLES}
    with path.open(encoding="utf-8") as f:
        for line in f:
            item = json.loads(line)
            snapshot[item["t"]][item["r"][TABLES[item["t"]]]] = item["r"]

    total_diffs = 0
    for table, pk in TABLES.items():
        expected = snapshot[table]
        actual = {r[pk]: r for r in fetch_heteml(table, pk)}
        diffs = []
        for key in sorted(set(expected) | set(actual)):
            a, b = expected.get(key), actual.get(key)
            if a is None or b is None:
                diffs.append(f"  {key}: {'ヘテムルにない' if b is None else 'ファイルにない'}")
                continue
            for col in sorted(set(a) | set(b)):
                if normalize(col, a.get(col)) != normalize(col, b.get(col)):
                    diffs.append(f"  {key}.{col}: {a.get(col)!r} ≠ {b.get(col)!r}")
        print(f"{table}: ファイル {len(expected):,} 行 / ヘテムル {len(actual):,} 行 / 差分 {len(diffs)} 件")
        for d in diffs[:20]:
            print(d)
        total_diffs += len(diffs)
    sys.exit(1 if total_diffs else 0)


def main() -> None:
    ap = ArgumentParser(description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("export")
    c = sub.add_parser("compare")
    c.add_argument("file", type=Path)
    args = ap.parse_args()
    if args.cmd == "export":
        cmd_export()
    else:
        cmd_compare(args.file)


if __name__ == "__main__":
    main()
