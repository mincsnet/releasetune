"""
build_corrections.py — 照合の結果から、サイトに反映するデータを作る

入力（git 管理外の data/audit/）:
  muse/inbox/releases_*.csv  Muse の照合（作品のリリース日）
  muse/inbox/debuts_*.csv    Muse の照合（デビュー日・デビュー作）
  muse/outbox/debuts_004-medium-recheck.csv  debuts_004 の medium を Muse が本文で確かめ直した結果（2026-11-07）
  debuts.csv                 運営側の精査（スケジュール済みタスク）。Muse のシートにないアーティストだけ使う

出力:
  heteml/data/date_corrections.csv  直すリリース日（heteml/bin/apply_date_corrections.php が DB に反映する）
  heteml/data/debut_artists.csv     デビュー日の一覧を書き換える（直した値・verified・根拠・補足の列）

使い方:
  python3 scripts/audit/build_corrections.py --dry-run   件数だけ表示する
  python3 scripts/audit/build_corrections.py             書き出す

反映の範囲（2026-11-07 Muse の推奨をユーザーが承認）:
  - wrong のうち、年月日まで分かり confidence が high・medium のものだけ。年・年月だけのもの、unknown は変えない
  - =LOVE のライブ盤6件は外す（照合の日付が映像盤の発売日。ライブ音源は音源としての初出日を採る方針）
  - debuts_004.csv（検索結果の抜粋との照合が中心）は high だけ。medium は Muse が本文で確かめ直した結果（RECHECK_CSV）で
    confirmed のものを足す。unknown（「初リリース」と「メジャーデビュー」の定義の違いだけが残る2組）は変えない
"""
import argparse
import csv
import glob
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CORRECTIONS_CSV = ROOT / "heteml/data/date_corrections.csv"
DEBUTS_CSV = ROOT / "heteml/data/debut_artists.csv"
CORRECTION_COLUMNS = ["track_id", "artist", "title", "db_date", "correct_date", "release_type", "confidence", "source_url", "checked_by"]
DEBUT_COLUMNS = ["artist", "debut_date", "debut_track", "mbid", "verified", "source_url", "checked_by", "note"]
RECHECK_CSV = "muse/outbox/debuts_004-medium-recheck.csv"

# 反映しない作品（track_id → 理由）
EXCLUDED_RELEASES = {
    tid: "=LOVE のライブ盤。照合の日付が映像盤の発売日"
    for tid in ["1653349409", "1653349761", "1653368701", "1653368756", "1653368886", "1653369257"]
}
# confidence が high のものだけ使うシート
HIGH_ONLY_SHEETS = {"debuts_004.csv"}


def is_ymd(s: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""))


def read_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def release_corrections(audit: Path) -> tuple[list[dict], dict]:
    rows, stats = [], {"wrong": 0, "excluded": 0, "skipped": 0}
    for path in sorted(glob.glob(str(audit / "muse/inbox/releases_*.csv"))):
        for r in read_csv(path):
            if r["status"] != "wrong":
                continue
            stats["wrong"] += 1
            if r["track_id"] in EXCLUDED_RELEASES:
                stats["excluded"] += 1
            elif is_ymd(r["correct_date"]) and r["confidence"] in ("high", "medium") and r["source_url"]:
                rows.append({
                    "track_id": r["track_id"], "artist": r["artist"], "title": r["title"], "db_date": r["db_date"],
                    "correct_date": r["correct_date"], "release_type": r["release_type"], "confidence": r["confidence"],
                    "source_url": r["source_url"], "checked_by": "muse",
                })
            else:
                stats["skipped"] += 1
    return rows, stats


def debut_updates(audit: Path) -> tuple[dict, dict]:
    """アーティスト名 → 書き換える値（verified だけのときは debut_date を含まない）"""
    updates, stats = {}, {"muse_fixed": 0, "muse_rechecked": 0, "muse_ok": 0, "muse_held": 0, "muse_unchanged": 0, "own_fixed": 0, "own_ok": 0, "own_unchanged": 0}
    recheck_path = audit / RECHECK_CSV
    recheck = {r["artist"]: r for r in read_csv(str(recheck_path))} if recheck_path.exists() else {}
    for path in sorted(glob.glob(str(audit / "muse/inbox/debuts_*.csv"))):
        sheet = Path(path).name
        for r in read_csv(path):
            base = {"verified": "true", "source_url": r["source_url"], "checked_by": "muse"}
            if r["status"] == "ok":
                updates[r["artist"]] = base
                stats["muse_ok"] += 1
            elif r["status"] == "wrong" and is_ymd(r["correct_debut_date"]) and r["confidence"] in ("high", "medium"):
                if sheet in HIGH_ONLY_SHEETS and r["confidence"] != "high":
                    rc = recheck.get(r["artist"])
                    if rc and rc["recheck_verdict"] == "confirmed" and is_ymd(rc["final_debut_date"]) and rc["source_url"]:
                        updates[r["artist"]] = {"verified": "true", "source_url": rc["source_url"], "checked_by": "muse",
                                                "debut_date": rc["final_debut_date"], "debut_track": rc["final_debut_work"].strip(), "note": rc["note"]}
                        stats["muse_rechecked"] += 1
                    else:
                        stats["muse_held"] += 1
                        updates[r["artist"]] = None  # 運営側の精査でも上書きしない
                    continue
                updates[r["artist"]] = base | {"debut_date": r["correct_debut_date"], "debut_track": r["correct_debut_work"].strip()}
                stats["muse_fixed"] += 1
            else:
                updates[r["artist"]] = None
                stats["muse_unchanged"] += 1
    for r in read_csv(str(audit / "debuts.csv")):
        if r["artist"] in updates:
            continue
        base = {"verified": "true", "source_url": r["source_url"], "checked_by": r["checked_by"]}
        if r["status"] == "ok":
            updates[r["artist"]] = base
            stats["own_ok"] += 1
        elif r["status"] == "wrong" and is_ymd(r["verified_date"]) and r["source_url"]:
            updates[r["artist"]] = base | {"debut_date": r["verified_date"], "debut_track": r["verified_track"].strip()}
            stats["own_fixed"] += 1
        else:
            stats["own_unchanged"] += 1
    return {a: u for a, u in updates.items() if u is not None}, stats


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--audit-dir", default=str(Path.home() / "releasetune/data/audit"))
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()
    audit = Path(args.audit_dir)

    corrections, rstats = release_corrections(audit)
    updates, dstats = debut_updates(audit)

    debuts = read_csv(str(DEBUTS_CSV))
    missing = sorted(set(updates) - {d["artist"] for d in debuts})
    if missing:
        sys.exit(f"debut_artists.csv にないアーティスト: {missing[:5]}")
    changed = 0
    for d in debuts:
        for col in DEBUT_COLUMNS:
            d.setdefault(col, "")
        u = updates.get(d["artist"])
        if u:
            before = (d["debut_date"], d["debut_track"])
            d.update(u)
            changed += (d["debut_date"], d["debut_track"]) != before

    print(f"リリース日: 反映 {len(corrections)}（wrong {rstats['wrong']}、除外 {rstats['excluded']}、対象外 {rstats['skipped']}）")
    print(f"デビュー: 値を直す {changed}（Muse {dstats['muse_fixed']}＋再確認 {dstats['muse_rechecked']}・運営側 {dstats['own_fixed']}）、"
          f"verified {sum(1 for d in debuts if d['verified'] == 'true')} / {len(debuts)}、"
          f"保留 {dstats['muse_held']}、変えない Muse {dstats['muse_unchanged']}・運営側 {dstats['own_unchanged']}")
    if args.dry_run:
        return

    with open(CORRECTIONS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CORRECTION_COLUMNS, lineterminator="\n")
        w.writeheader()
        w.writerows(sorted(corrections, key=lambda r: r["track_id"]))
    with open(DEBUTS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=DEBUT_COLUMNS, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(debuts)
    print(f"書き出し: {CORRECTIONS_CSV.relative_to(ROOT)}、{DEBUTS_CSV.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
