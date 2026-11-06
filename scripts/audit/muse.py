"""
Muse（外部の確認担当）に作品のリリース日・アーティストのデビュー日を確かめてもらうシートの書き出しと取り込み
==========================================================================================

使い方（リポジトリのどの checkout から実行してもよい。.env の DATA_BACKEND=heteml で DB を読む）:
  python3 scripts/audit/muse.py export [--releases 5] [--debuts 0]
      確認シートを outbox/ に書き出す。--releases は作品のシートの数、--debuts はデビューのシートの数（0 は残り全部）。
      1シート100行。確認済み（ok・wrong。Muse が確かめたものは unknown も）と、outbox/ にあって返ってきていない行は入れない
  python3 scripts/audit/muse.py import [--dry-run] [CSV ...]
      inbox/ の CSV（または指定した CSV）を、outbox/ の渡したシートと突き合わせて検証し、結果を記録する。
      1つでも誤りのあるファイルは何も書かずに飛ばす。--dry-run は検証と集計だけ

置き場所: 本体の checkout の data/audit/muse/（git 管理外。worktree から実行しても本体に置く）
  outbox/   Muse に渡すもの（00_作業指示書.md と releases_NNN.csv・debuts_NNN.csv）
  inbox/    Muse から返ってきた CSV を置く
  done/     取り込み済み（sent_NNN.csv が渡したもの、NNN.csv が返ってきたもの）
  results_releases.csv・results_debuts.csv   Muse の結果の累積（全部の列。キーは track_id・artist）
取り込みでは data/audit/release_dates.csv・debuts.csv（スケジュール済みタスクの記録）にも基本の列を書く。
すでに ok・wrong の行と食い違うときは上書きせず、食い違いとして表示する。
DB と heteml/data/debut_artists.csv は変更しない（直すのは結果を見てから別に行う）。
"""

import argparse, csv, re, shutil, subprocess, sys, unicodedata
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from urllib.parse import quote

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "notes"))
from common import ROOT, sb_select, today_jst  # noqa: E402

# 本体の checkout（worktree の .git が指す共通の .git の親）
MAIN_ROOT = Path(subprocess.run(["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
                                cwd=ROOT, capture_output=True, text=True, check=True).stdout.strip()).parent
AUDIT_DIR = MAIN_ROOT / "data" / "audit"
MUSE_DIR  = AUDIT_DIR / "muse"
OUTBOX, INBOX, DONE = MUSE_DIR / "outbox", MUSE_DIR / "inbox", MUSE_DIR / "done"
GUIDE     = HERE / "MUSE_GUIDE.md"
DEBUT_CSV = ROOT / "heteml" / "data" / "debut_artists.csv"
SITE      = "https://releasetune.com"
ROWS_PER_SHEET = 100

REL_GIVEN = ["track_id", "artist", "title", "kind", "db_date", "apple_url", "site_url", "reason"]
REL_FILL  = ["status", "correct_date", "release_type", "original_title", "prerelease_date", "song_original_date",
             "source_url", "source_url2", "evidence", "confidence", "note", "checked_at"]
DEB_GIVEN = ["artist", "csv_debut_date", "csv_debut_track", "musicbrainz_url", "site_url", "site_works", "site_earliest"]
DEB_FILL  = ["status", "correct_debut_date", "correct_debut_work", "debut_kind", "major_debut_date", "major_debut_work",
             "indie_debut_date", "indie_debut_work", "source_url", "source_url2", "evidence", "confidence", "note", "checked_at"]

SHEETS = {
    "releases": {"key": "track_id", "given": REL_GIVEN, "fill": REL_FILL,
                 "audit": AUDIT_DIR / "release_dates.csv", "results": MUSE_DIR / "results_releases.csv"},
    "debuts":   {"key": "artist", "given": DEB_GIVEN, "fill": DEB_FILL,
                 "audit": AUDIT_DIR / "debuts.csv", "results": MUSE_DIR / "results_debuts.csv"},
}
AUDIT_HEADERS = {
    "releases": ["track_id", "artist", "title", "db_date", "verified_date", "status", "source_url", "checked_at", "checked_by", "note"],
    "debuts":   ["artist", "csv_debut_date", "csv_debut_track", "verified_date", "verified_track", "major_or_indie",
                 "status", "source_url", "checked_at", "checked_by", "note"],
}

STATUSES      = {"ok", "wrong", "unknown"}
RELEASE_TYPES = {"original", "reissue", "rerecording", "compilation", "live", "other"}
CONFIDENCES   = {"high", "medium", "low"}
DEBUT_KINDS   = {"major", "indie", "other"}

# 作品名に再発・再録らしい語（「Japanese Ver.」「10th Anniversary BEST」のような元の作品は拾わない）
REISSUE_TITLE = re.compile(r"(?i)remaster|original cover art|re-?record|reissue|deluxe|\b(?:19|20)\d\d\s*ver|リマスター|再録|復刻")
BATCH_MIN = 5  # heteml/src/releases.php の BATCH_MIN と同じ（同じアーティスト・同じ発売日にこの数以上＝一括配信）


# ── CSV ────────────────────────────────────────────────

def read_csv(path: Path) -> tuple[list[str], list[dict]]:
    if not path.exists():
        return [], []
    with path.open(encoding="utf-8-sig", newline="") as f:
        r = csv.DictReader(f)
        return list(r.fieldnames or []), list(r)


def write_csv(path: Path, header: list[str], rows: list[dict], bom: bool = False) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8-sig" if bom else "utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=header, lineterminator="\n", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)
    tmp.replace(path)


def checked_keys(kind: str) -> set[str]:
    """もう Muse に渡さないキー: スケジュール済みタスクが ok・wrong と決めたものと、Muse が一度確かめたもの（unknown を含む）"""
    key = SHEETS[kind]["key"]
    done = {r[key] for r in read_csv(SHEETS[kind]["audit"])[1] if r.get("status") in ("ok", "wrong")}
    return done | {r[key] for r in read_csv(SHEETS[kind]["results"])[1]}


def pending_keys(kind: str) -> set[str]:
    key = SHEETS[kind]["key"]
    return {r[key] for p in OUTBOX.glob(f"{kind}_*.csv") for r in read_csv(p)[1]}


def next_number(kind: str) -> int:
    nums = [int(m.group(1)) for d in (OUTBOX, DONE) for p in d.glob(f"*{kind}_*.csv")
            if (m := re.search(rf"{kind}_(\d+)\.csv$", p.name))]
    return max(nums, default=0) + 1


# ── 書き出し ───────────────────────────────────────────

def release_kind(t: dict) -> str:
    """heteml/src/releases.php の release_kind_label と同じ見分け方"""
    if re.search(r"-\s*Single$", t["title"]):
        return "シングル"
    if re.search(r"-\s*EP$", t["title"]):
        return "EP"
    n = t.get("track_count")
    return "シングル" if n is not None and int(n) <= 3 else "アルバム"


def artist_url(name: str) -> str:
    """heteml/src/site.php の artist_path と同じ（「/」入りは ?name=）"""
    enc = quote(name, safe="-_.!~*'()")
    return f"{SITE}/artist?name={enc}" if "/" in name else f"{SITE}/artist/{enc}"


def days_until(mmdd: str, today: date) -> int:
    """明日を 0 として、次にその月日が来るまでの日数（うるう年の暦で数える）"""
    doy = lambda m, d: date(2024, m, d).timetuple().tm_yday
    m, d = map(int, mmdd.split("-"))
    return (doy(m, d) - doy(today.month, today.day) - 1) % 366


def read_debut_list() -> list[dict]:
    # サイト（releases.php の debut_db）は単純にカンマで区切るが、ここでは「"Each Day, Everyday"」のような
    # 引用符付きの値も正しく読む（Muse には本来の作品名を渡す）
    return [r for r in read_csv(DEBUT_CSV)[1] if r.get("artist") and r.get("debut_date")]


def build_release_rows(tracks: list[dict], debuts: list[dict], today: date) -> list[dict]:
    debut_date = {d["artist"]: d["debut_date"] for d in debuts}
    batch = Counter((t["artist"].lower(), t["release_date"]) for t in tracks)
    rows = []
    for t in tracks:
        if debut_date.get(t["artist"]) == t["release_date"]:
            tier, reason = 0, "debut_work"
        elif batch[(t["artist"].lower(), t["release_date"])] >= BATCH_MIN:
            tier, reason = 1, "batch"
        elif REISSUE_TITLE.search(t["title"]):
            tier, reason = 1, "reissue_title"
        else:
            tier, reason = 2, "upcoming"
        rows.append({
            "_sort": (tier, days_until(t["release_date"][5:], today), t["artist"].lower(), t["release_date"], t["id"]),
            "track_id": t["id"], "artist": t["artist"], "title": t["title"], "kind": release_kind(t),
            "db_date": t["release_date"], "apple_url": (t.get("apple") or "").replace("?uo=4", ""),
            "site_url": f"{SITE}/track/{t['id']}", "reason": reason,
        })
    rows.sort(key=lambda r: r["_sort"])
    return rows


def build_debut_rows(tracks: list[dict], debuts: list[dict], today: date) -> list[dict]:
    by_artist: dict[str, list[dict]] = {}
    for t in tracks:
        by_artist.setdefault(t["artist"].lower(), []).append(t)  # アーティストページと同じく大文字小文字を区別しない
    rows = []
    for d in debuts:
        works = by_artist.get(d["artist"].lower(), [])
        first = min(works, key=lambda t: (t["release_date"], t["id"]), default=None)
        rows.append({
            # 年月だけの日付（「1989-05」。サイトのデビュー記念日には出ない）は最後に回す
            "_sort": (days_until(d["debut_date"][5:], today) if len(d["debut_date"]) == 10 else 999, d["artist"].lower()),
            "artist": d["artist"], "csv_debut_date": d["debut_date"], "csv_debut_track": d.get("debut_track", ""),
            "musicbrainz_url": f"https://musicbrainz.org/artist/{d['mbid']}" if d.get("mbid") else "",
            "site_url": artist_url(d["artist"]), "site_works": str(len(works)),
            "site_earliest": f"{first['release_date']} {first['title']}" if first else "",
        })
    rows.sort(key=lambda r: r["_sort"])
    return rows


def export_sheets(kind: str, rows: list[dict], sheets: int) -> list[Path]:
    skip = checked_keys(kind) | pending_keys(kind)
    key, header = SHEETS[kind]["key"], SHEETS[kind]["given"] + SHEETS[kind]["fill"]
    rows = [r for r in rows if r[key] not in skip]
    remaining = len(rows)
    if sheets:
        rows = rows[:sheets * ROWS_PER_SHEET]
    n, paths = next_number(kind), []
    for i in range(0, len(rows), ROWS_PER_SHEET):
        path = OUTBOX / f"{kind}_{n:03d}.csv"
        write_csv(path, header, rows[i:i + ROWS_PER_SHEET], bom=True)  # Excel でも文字化けしないよう BOM 付き
        paths.append(path)
        n += 1
    reasons = Counter(r.get("reason", "") for r in rows) if kind == "releases" else None
    print(f"{kind}: 未確認 {remaining} 件のうち {len(rows)} 件を {len(paths)} シートに書き出し"
          + (f"（{dict(reasons)}）" if reasons else ""))
    return paths


def cmd_export(args) -> None:
    today = date.fromisoformat(today_jst())
    tracks = sb_select("tracks", {"select": "id,title,artist,release_date,apple,track_count", "order": "id.asc"})
    debuts = read_debut_list()
    print(f"DB の作品 {len(tracks)} 件・デビュー一覧 {len(debuts)} 組")
    OUTBOX.mkdir(parents=True, exist_ok=True)
    INBOX.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(GUIDE, OUTBOX / "00_作業指示書.md")
    export_sheets("releases", build_release_rows(tracks, debuts, today), args.releases)
    export_sheets("debuts", build_debut_rows(tracks, debuts, today), args.debuts)
    print(f"→ {OUTBOX}")


# ── 取り込み ───────────────────────────────────────────

def norm(s: str | None) -> str:
    return unicodedata.normalize("NFKC", s or "").strip()


def norm_work(s: str) -> str:
    """デビュー作の名前の比較用（「- Single」・空白・大文字小文字・括弧の種類を無視）"""
    s = re.sub(r"\s*-\s*(?:Single|EP)$", "", norm(s))
    return re.sub(r"[\s「」『』\"']", "", s).lower()


DATE_RE = re.compile(r"^\d{4}(?:-\d{2}(?:-\d{2})?)?$")


def date_error(value: str) -> str | None:
    if not value:
        return None
    if not DATE_RE.match(value):
        return f"日付の形が違う: {value!r}（YYYY-MM-DD・YYYY-MM・YYYY）"
    try:
        datetime.strptime(value, {4: "%Y", 7: "%Y-%m", 10: "%Y-%m-%d"}[len(value)])
    except ValueError:
        return f"ありえない日付: {value!r}"
    return None


def url_error(value: str, required: bool) -> str | None:
    if not value:
        return "根拠の URL（source_url）がない" if required else None
    return None if re.match(r"^https?://\S+$", value) else f"URL の形が違う: {value!r}"


def validate_release(r: dict) -> list[str]:
    st, errs = r["status"], []
    for col in ("correct_date", "prerelease_date", "song_original_date", "checked_at"):
        errs.append(date_error(r[col]))
    if st in ("ok", "wrong"):
        if r["release_type"] not in RELEASE_TYPES:
            errs.append(f"release_type が {sorted(RELEASE_TYPES)} のどれでもない: {r['release_type']!r}")
        if r["confidence"] not in CONFIDENCES:
            errs.append(f"confidence が high・medium・low のどれでもない: {r['confidence']!r}")
        errs.append(url_error(r["source_url"], True))
    errs.append(url_error(r["source_url2"], False))
    db, cd, pre = r["db_date"], r["correct_date"], r["prerelease_date"]
    if pre and len(cd) == 10 and len(pre) == 10 and pre > cd:
        errs.append(f"先行配信日 {pre} が発売日 {cd} より後")
    if st == "ok":
        if not cd:
            r["correct_date"] = db
        elif db not in (cd, pre):
            errs.append(f"ok なのに correct_date {cd}（先行配信 {pre or 'なし'}）が db_date {db} と違う")
    elif st == "wrong":
        if not cd:
            errs.append("wrong なのに correct_date がない")
        elif db in (cd, pre):
            errs.append(f"wrong なのに db_date {db} が correct_date・先行配信日と同じ（ok では？）")
        elif len(cd) < 10 and db.startswith(cd):
            errs.append(f"correct_date {cd} は db_date {db} と食い違っていない（年・年月だけで wrong にはできない）")
    return [e for e in errs if e]


def validate_debut(r: dict) -> list[str]:
    st, errs = r["status"], []
    for col in ("correct_debut_date", "major_debut_date", "indie_debut_date", "checked_at"):
        errs.append(date_error(r[col]))
    if st in ("ok", "wrong"):
        if r["debut_kind"] not in DEBUT_KINDS:
            errs.append(f"debut_kind が major・indie・other のどれでもない: {r['debut_kind']!r}")
        if r["confidence"] not in CONFIDENCES:
            errs.append(f"confidence が high・medium・low のどれでもない: {r['confidence']!r}")
        errs.append(url_error(r["source_url"], True))
    errs.append(url_error(r["source_url2"], False))
    cd, cw = r["correct_debut_date"], r["correct_debut_work"]
    if st == "ok":
        r["correct_debut_date"] = cd = cd or r["csv_debut_date"]
        r["correct_debut_work"] = cw = cw or r["csv_debut_track"]
        if cd != r["csv_debut_date"] or norm_work(cw) != norm_work(r["csv_debut_track"]):
            errs.append(f"ok なのに正しいデビュー {cd}「{cw}」が一覧の {r['csv_debut_date']}「{r['csv_debut_track']}」と違う")
    elif st == "wrong":
        if not cd or not cw:
            errs.append("wrong なのに correct_debut_date か correct_debut_work がない")
        elif cd == r["csv_debut_date"] and norm_work(cw) == norm_work(r["csv_debut_track"]):
            errs.append("wrong なのに日付もデビュー作も一覧と同じ（ok では？）")
    return [e for e in errs if e]


NORM_COLS = {"status", "release_type", "confidence", "debut_kind", "correct_date", "prerelease_date", "song_original_date",
             "correct_debut_date", "major_debut_date", "indie_debut_date", "checked_at", "source_url", "source_url2"}


def check_file(path: Path) -> tuple[str | None, list[dict], list[str]]:
    """返ってきた CSV を渡したシートと突き合わせて検証する。戻り値は (種類, 記入済みの行, 誤り)"""
    kind = next((k for k in SHEETS if path.name.startswith(k + "_")), None)
    if not kind:
        return None, [], [f"ファイル名が releases_NNN.csv・debuts_NNN.csv の形ではない: {path.name}"]
    sent = OUTBOX / path.name
    if not sent.exists():
        return kind, [], [f"渡したシート {sent} がない（取り込み済み？）"]
    spec = SHEETS[kind]
    header, rows = read_csv(path)
    sent_header, sent_rows = read_csv(sent)
    if [h.strip() for h in header] != sent_header:
        return kind, [], [f"列名が渡したものと違う: {header}"]
    if len(rows) != len(sent_rows):
        return kind, [], [f"行の数が渡したもの（{len(sent_rows)}）と違う: {len(rows)}"]
    errs, filled = [], []
    for i, (r, s) in enumerate(zip(rows, sent_rows), start=2):
        label = f"{i}行目（{s[spec['key']]}）"
        changed = [c for c in spec["given"] if norm(r.get(c)) != norm(s.get(c))]
        if changed:
            errs.append(f"{label}: 渡す値の列が書き換わっている: {changed}")
            continue
        row = {c: s[c] for c in spec["given"]}
        row.update({c: (norm(r.get(c)) if c in NORM_COLS else (r.get(c) or "").strip()) for c in spec["fill"]})
        row["status"] = row["status"].lower()
        if row["status"] == "":
            if any(row[c] for c in spec["fill"]):
                errs.append(f"{label}: status が空欄なのにほかの列に記入がある")
            continue
        if row["status"] not in STATUSES:
            errs.append(f"{label}: status が ok・wrong・unknown のどれでもない: {row['status']!r}")
            continue
        errs += [f"{label}: {e}" for e in (validate_release(row) if kind == "releases" else validate_debut(row))]
        filled.append(row)
    return kind, filled, errs


def audit_row(kind: str, r: dict, today: str) -> dict:
    """スケジュール済みタスクの記録（data/audit/*.csv）の形にする"""
    if kind == "releases":
        extra = [f"{r['release_type']}/{r['confidence']}" if r["release_type"] else "",
                 f"元: {r['original_title']}" if r["original_title"] else "",
                 f"先行配信 {r['prerelease_date']}" if r["prerelease_date"] else "",
                 f"曲の初出 {r['song_original_date']}" if r["song_original_date"] else "", r["note"]]
        return {"track_id": r["track_id"], "artist": r["artist"], "title": r["title"], "db_date": r["db_date"],
                "verified_date": r["correct_date"], "status": r["status"], "source_url": r["source_url"],
                "checked_at": r["checked_at"] or today, "checked_by": "muse", "note": " / ".join(x for x in extra if x)}
    extra = [r["confidence"],
             f"メジャー {r['major_debut_date']} {r['major_debut_work']}".strip() if r["major_debut_date"] else "",
             f"インディーズ {r['indie_debut_date']} {r['indie_debut_work']}".strip() if r["indie_debut_date"] else "", r["note"]]
    return {"artist": r["artist"], "csv_debut_date": r["csv_debut_date"], "csv_debut_track": r["csv_debut_track"],
            "verified_date": r["correct_debut_date"], "verified_track": r["correct_debut_work"],
            "major_or_indie": r["debut_kind"], "status": r["status"], "source_url": r["source_url"],
            "checked_at": r["checked_at"] or today, "checked_by": "muse", "note": " / ".join(x for x in extra if x)}


def merge(kind: str, filled: list[dict], source: str, dry_run: bool) -> list[str]:
    """結果の累積と data/audit の記録に書く。戻り値は既存の確認結果との食い違い"""
    spec, today = SHEETS[kind], today_jst()
    key = spec["key"]
    res_header = spec["given"] + spec["fill"] + ["imported_at", "source_file"]
    _, results = read_csv(spec["results"])
    by_key = {r[key]: r for r in results}
    for r in filled:
        by_key[r[key]] = {**r, "imported_at": today, "source_file": source}

    audit_header, audit = read_csv(spec["audit"])
    audit_header = audit_header or AUDIT_HEADERS[kind]
    index = {r[key]: i for i, r in enumerate(audit)}
    conflicts = []
    for r in filled:
        new = audit_row(kind, r, today)
        i = index.get(r[key])
        old = audit[i] if i is not None else None
        if old and new["status"] == "unknown":
            continue  # 分からなかった結果で、これまでの記録（unknown でもメモが残っている）を消さない
        if old and old.get("status") in ("ok", "wrong") and old.get("checked_by") != "muse":
            if (old["status"], old.get("verified_date")) != (new["status"], new["verified_date"]):
                label = f"「{r['title']}」" if kind == "releases" else ""
                conflicts.append(f"{r[key]}{label}: これまでの記録 {old['status']} {old.get('verified_date')}"
                                 f"（{old.get('checked_by')}）／ Muse {new['status']} {new['verified_date']}")
            continue
        if i is None:
            index[r[key]] = len(audit)
            audit.append(new)
        else:
            audit[i] = new
    if not dry_run:
        write_csv(spec["results"], res_header, list(by_key.values()))
        write_csv(spec["audit"], audit_header, audit)
    return conflicts


def cmd_import(args) -> None:
    files = [Path(p) for p in args.files] or sorted(INBOX.glob("*.csv"))
    if not files:
        print(f"取り込む CSV がありません（{INBOX} に置いてください）")
        return
    for path in files:
        kind, filled, errs = check_file(path)
        print(f"\n■ {path.name}")
        if errs:
            print(f"  誤り {len(errs)} 件 → このファイルは取り込みません")
            for e in errs[:50]:
                print(f"  - {e}")
            continue
        counts = Counter(r["status"] for r in filled)
        print(f"  記入 {len(filled)} 件（ok {counts['ok']}・wrong {counts['wrong']}・unknown {counts['unknown']}）"
              f"・未記入 {len(read_csv(path)[1]) - len(filled)} 件")
        for r in filled:
            if r["status"] != "wrong":
                continue
            if kind == "releases":
                print(f"  wrong {r['artist']}「{r['title']}」 {r['db_date']} → {r['correct_date']}"
                      f"（{r['release_type']}・{r['confidence']}）{r['source_url']}")
            else:
                print(f"  wrong {r['artist']} {r['csv_debut_date']}「{r['csv_debut_track']}」→ "
                      f"{r['correct_debut_date']}「{r['correct_debut_work']}」（{r['debut_kind']}・{r['confidence']}）{r['source_url']}")
        for c in merge(kind, filled, path.name, args.dry_run):
            print(f"  ⚠ 食い違い（上書きしていません）: {c}")
        if not args.dry_run:
            DONE.mkdir(parents=True, exist_ok=True)
            shutil.move(str(OUTBOX / path.name), DONE / f"sent_{path.name}")
            shutil.move(str(path), DONE / path.name)
    if args.dry_run:
        print("\n（--dry-run: 何も書いていません）")


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("export")
    e.add_argument("--releases", type=int, default=5, help="作品のシートの数（0 は残り全部）")
    e.add_argument("--debuts", type=int, default=0, help="デビューのシートの数（0 は残り全部）")
    e.set_defaults(func=cmd_export)
    i = sub.add_parser("import")
    i.add_argument("--dry-run", action="store_true")
    i.add_argument("files", nargs="*")
    i.set_defaults(func=cmd_import)
    args = p.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
