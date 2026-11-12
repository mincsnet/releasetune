"""
build_corrections.py — 照合の結果から、サイトに反映するデータを作る

入力（git 管理外の data/audit/）:
  muse/inbox/releases_*.csv  Muse の照合（作品のリリース日）
  muse/inbox/debuts_*.csv    Muse の照合（デビュー日・デビュー作）
  muse/outbox/debuts_004-medium-recheck.csv  debuts_004 の medium を Muse が本文で確かめ直した結果（2026-11-07）
  debuts.csv                 運営側の精査（スケジュール済みタスク）。Muse のシートにないか、Muse が unknown のアーティストに使う
  release_dates.csv          運営側の精査の作品。wrong を1件ずつ仕分けた OWN_RELEASES に従う（仕分けていない wrong は一覧に出す）

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
# 運営側の精査（release_dates.csv）の wrong の仕分け（2026-11-13、Muse の指示書と同じ基準: 再発・デラックス盤は元の作品の日付、
# 再録・リミックス・ライブはその盤自身の日付、先行配信日と同じなら正しい）。
# 運営側の精査は再録も「元の曲の日付」で wrong にするので、そのままは使えない。
#   値が (correct_date, release_type, confidence) → 直す。文字列 → 直さない理由
OWN_RELEASES = {
    "1714384567": ("2023-10-13", "reissue", "medium"),      # 藤井 風「花」4曲入り。1曲の配信シングル（2023-10-13）に Ballad・demo などを足した盤
    "1444611634": ("2006-11-01", "original", "medium"),     # 坂本冬美「秋まつり、お月さま」。CD シングルの発売日
    "203853522":  ("2006-11-01", "original", "high"),       # misono「ラブリー・キャッツアイ」。Wikipedia・MusicBrainz とも
    "1595213550": ("2021-11-12", "rerecording", "medium"),  # テイラー・スウィフト「I Bet You Think About Me (Taylor's Version)」。Red (Taylor's Version) と同日
    "1772758653": ("2021-08-30", "original", "medium"),     # SHOW-YA『Showdown』。日本先行の発売日（DB は世界発売日）
    "1592933770": ("2021-11-15", "original", "medium"),     # Novelbright「ワンルーム」先行配信シングル（11/15 0時）
    "1864135508": ("2011-11-09", "original", "medium"),     # 平松愛理「いいんじゃない?」CD シングル（TECG-37）
    "1593710942": ("2002-09-26", "reissue", "medium"),      # 浜崎あゆみ『ayu trance 2 (COMPLETE EDITION)』。曲を足した2021年の配信版
    "1595925412": ("2021-10-05", "reissue", "medium"),      # aespa『Savage (Extended Version)』。元のミニアルバムに曲を足した版
    "720581650":  ("2006-11-15", "original", "medium"),     # DJ OZMA『I Love Party People』。英語版 Wikipedia・Generasia（MusicBrainz は 11/5）
    "265185782":  ("1996-12-16", "reissue", "high"),        # THE ALFEE『CLASSICS II』（℗ 1996）。Wikipedia・MusicBrainz とも
    "1592697911": ("2021-11-24", "original", "medium"),     # スキマスイッチ『Hot Milk』。Wikipedia・MusicBrainz とも（11/17 の先行配信は確認できず）
    "1590266229": ("2021-11-24", "original", "medium"),     # Novelbright「seeker / ワンルーム」CD の発売日（DB はフラゲ日）
    "1590268187": ("2021-10-25", "original", "medium"),     # Novelbright「seeker」先行配信シングル
    "1590987014": "再録（2021Ver.）。その盤の日付で正しい",
    "1840596873": "再録（2021Ver.）。その盤の日付で正しい",
    "1607858567": "2022年リマスターの再発。元の CD シングル（1996-11-04）と同じ日付で正しい。9/11 は曲のダウンロード先行",
    "1536487084": "再録（JEWEL ver.）。その盤の日付で正しい",
    "478822939":  "再録（2011 Acoustic Ver.）。その盤の日付で正しい",
    "1595666852": "再録（10 Minute Version）。その盤の日付で正しい",
    "1031482546": "2004年のマキシ CD（曲を足した別の盤）。その盤の日付で正しい",
    "1537779516": "再録（feat. SKY-HI）。その盤の日付で正しい",
    "1596155189": "再録（Sad Girl Autumn Version）。その盤の日付で正しい",
    "1594599836": "リミックス。その盤の日付で正しい",
    "1594489051": "ライブ録音。その盤の日付で正しい",
    "1592264553": "MusicBrainz の 11/9 は時差の可能性。DB の 11/10（水曜）のほうが確か",
    "1591893278": "保留: Wikipedia は 11/11 だが Apple は 11/10（水曜）。決め手がない",
    "1653259965": "保留: 元のシングル（2001-02-21）は別の行にある。この6曲入りの盤が何か分からない",
    "1839433391": "保留: 2023年の再録だが DB は 2008-11-19。再録盤の発売日が分からない",
    "1536495013": "保留: Wikipedia は 11/25 だが Apple は 11/16。違いの理由が分からない",
}

# confidence が high のものだけ使うシート
HIGH_ONLY_SHEETS = {"debuts_004.csv"}


def is_ymd(s: str) -> bool:
    return bool(re.fullmatch(r"\d{4}-\d{2}-\d{2}", s or ""))


def read_csv(path: str) -> list[dict]:
    with open(path, encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def release_corrections(audit: Path) -> tuple[list[dict], dict]:
    rows, stats = [], {"wrong": 0, "excluded": 0, "skipped": 0, "own": 0, "own_kept": 0, "undecided": []}
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
    muse_ids = {r["track_id"] for r in rows}
    for r in read_csv(str(audit / "release_dates.csv")):
        if r["status"] != "wrong" or r["track_id"] in muse_ids:
            continue
        decision = OWN_RELEASES.get(r["track_id"])
        if decision is None:
            stats["undecided"].append(f"{r['track_id']} {r['artist']}「{r['title']}」 {r['db_date']} → {r['verified_date'] or '?'}")
        elif isinstance(decision, tuple):
            correct_date, release_type, confidence = decision
            rows.append({
                "track_id": r["track_id"], "artist": r["artist"], "title": r["title"], "db_date": r["db_date"],
                "correct_date": correct_date, "release_type": release_type, "confidence": confidence,
                "source_url": r["source_url"], "checked_by": r["checked_by"],
            })
            stats["own"] += 1
        else:
            stats["own_kept"] += 1
    return rows, stats


def debut_updates(audit: Path) -> tuple[dict, dict]:
    """アーティスト名 → 書き換える値（verified だけのときは debut_date を含まない）"""
    updates, stats = {}, {"muse_fixed": 0, "muse_rechecked": 0, "muse_ok": 0, "muse_held": 0, "muse_unchanged": 0, "muse_unknown": 0, "own_fixed": 0, "own_ok": 0, "own_unchanged": 0}
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
            elif r["status"] == "unknown":
                stats["muse_unknown"] += 1  # 運営側の精査の結果があればそれを使う
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

    print(f"リリース日: 反映 {len(corrections)}（Muse の wrong {rstats['wrong']}、除外 {rstats['excluded']}、対象外 {rstats['skipped']}／"
          f"運営側 直す {rstats['own']}・直さない {rstats['own_kept']}）")
    for u in rstats["undecided"]:
        print(f"  未仕分け（OWN_RELEASES に足す）: {u}")
    print(f"デビュー: 値を直す {changed}（Muse {dstats['muse_fixed']}＋再確認 {dstats['muse_rechecked']}・運営側 {dstats['own_fixed']}）、"
          f"verified {sum(1 for d in debuts if d['verified'] == 'true')} / {len(debuts)}、"
          f"保留 {dstats['muse_held']}、変えない Muse {dstats['muse_unchanged']}・運営側 {dstats['own_unchanged']}"
          f"（Muse の unknown {dstats['muse_unknown']} は運営側の結果を使う）")
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
