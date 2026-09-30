"""
scripts/titles/fix_ja_titles.py — 英語・ローマ字表記の曲名を Apple Music 日本版のタイトルに直す
================================================================================================
背景:
  過去の一括収集（collect_itunes.py）は iTunes Lookup API を entity=album で呼んでいた。
  このときアルバム（collection）の名前は lang=ja_jp を指定しても英語・ローマ字表記で返る
  （例: 「おじいちゃんちへいこう - Single」→「Ojiichanchi E Ikou - Single」）。
  同じ API でも entity=song で引いた「曲」側の collectionName は日本版の表記で返るので、それを使う。

  曲側の collectionName はボックスセットだとディスク単位の名前になることがある
  （例: 「Five Years 1969-1973」の曲 →「David Bowie (AKA Space Oddity)」）。
  曲側とアルバム側で収録曲数が違うときは、Apple Music の oEmbed（ページに表示されるタイトル）で確かめる。

使い方（リポジトリのルートで実行）:
  python3 scripts/titles/fix_ja_titles.py fetch          # 日本版タイトルを取得（中断・再開可、約15分）
  python3 scripts/titles/fix_ja_titles.py propose        # 修正候補を data/titles/proposals.csv に出力（DBは変更しない）
  python3 scripts/titles/fix_ja_titles.py apply --dry-run --limit 20
  python3 scripts/titles/fix_ja_titles.py apply          # 候補をSupabaseに反映（既定は kind=ja のみ）
  python3 scripts/titles/fix_ja_titles.py revert data/titles/applied_YYYYmmdd-HHMMSS.jsonl

proposals.csv の kind:
  ja     : 今の曲名に日本語がなく、日本版タイトルには日本語がある（例: Massugu - EP → 真っ直ぐ - EP）
  latin  : どちらも日本語なしで表記だけ違う（例: Kaela → KAELA、Nikki (Diary) → NIKKI）
  changed: DBの曲名が Apple の今の英語名とも違う（Apple側で作品名が変わった可能性）。個別に確認する
  apply は proposals.csv を読むので、反映したくない行はCSVから消してから実行すればよい。

apply は曲名と一緒に、保存済みの検索URL（spotify / amazon / youtube 列のうち直リンクでないもの）の
検索語に含まれる旧曲名も新しい曲名に置き換える。変更前の値は data/titles/applied_*.jsonl に残す。
"""

import csv, json, re, sys, time
from argparse import ArgumentParser
from datetime import datetime
from pathlib import Path
from urllib.parse import quote, unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "notes"))
from common import ROOT, http_request, sb_select, sb_select_in, sb_update  # noqa: E402

DATA_DIR       = ROOT / "data" / "titles"
LOOKUP_FILE    = DATA_DIR / "lookup.json"
PROPOSALS_FILE = DATA_DIR / "proposals.csv"

ITUNES_LOOKUP = "https://itunes.apple.com/lookup"
OEMBED        = "https://music.apple.com/api/oembed"
BATCH         = 100   # Lookup API に一度に渡す collectionId の数
ITUNES_SLEEP  = 3.0   # iTunes API は約20回/分が目安
OEMBED_SLEEP  = 1.0

_JA = re.compile(r"[぀-ヿ㐀-鿿ｦ-ﾟ]")

# 検索URLの接頭辞（この後ろが検索語）
SEARCH_PREFIXES = {
    "spotify": "https://open.spotify.com/search/",
    "amazon":  "https://music.amazon.co.jp/search/",
    "youtube": "https://www.youtube.com/results?search_query=",
}


def has_ja(s: str | None) -> bool:
    return bool(s and _JA.search(s))


def load_json(path: Path, default):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else default


def save_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    tmp.replace(path)


def english_title_tracks() -> list[dict]:
    rows = sb_select("tracks", {"select": "id,title,artist,release_date", "order": "id.asc"})
    return [r for r in rows if not has_ja(r["title"])]


# ── fetch ─────────────────────────────────────────────────────────
def itunes_lookup(ids: list[str]) -> list[dict]:
    params = {"id": ",".join(ids), "country": "JP", "lang": "ja_jp", "entity": "song", "limit": 1}
    for attempt in range(5):
        resp = http_request("get", ITUNES_LOOKUP, params=params, timeout=60)
        if resp.ok:
            return resp.json().get("results", [])
        wait = 30 * (attempt + 1)
        print(f"    [iTunes] {resp.status_code}。{wait}秒待って再試行")
        time.sleep(wait)
    raise RuntimeError("iTunes Lookup API: リトライ上限")


def oembed_title(track_id: str) -> str | None:
    resp = http_request("get", OEMBED, params={"url": f"https://music.apple.com/jp/album/{track_id}"}, timeout=30)
    time.sleep(OEMBED_SLEEP)
    if not resp.ok:
        return None
    return (resp.json().get("title") or "").strip() or None


def cmd_fetch(_args) -> None:
    lookup: dict = load_json(LOOKUP_FILE, {})
    targets = english_title_tracks()
    todo = [r["id"] for r in targets if r["id"] not in lookup]
    print(f"日本語を含まない曲名: {len(targets):,}件（未取得 {len(todo):,}件）")

    for i in range(0, len(todo), BATCH):
        chunk = todo[i:i + BATCH]
        found = {tid: {"en": None, "en_count": None, "ja": None, "ja_count": None} for tid in chunk}
        for x in itunes_lookup(chunk):
            e = found.get(str(x.get("collectionId")))
            if e is None:
                continue
            if x.get("wrapperType") == "collection":
                e["en"], e["en_count"] = x.get("collectionName"), x.get("trackCount")
            elif x.get("wrapperType") == "track":
                e["ja"], e["ja_count"] = x.get("collectionName"), x.get("trackCount")
        lookup.update(found)
        save_json(LOOKUP_FILE, lookup)
        print(f"  iTunes {i + len(chunk):,} / {len(todo):,}")
        time.sleep(ITUNES_SLEEP)

    # 曲側の名前が使えない（曲が取れない・収録曲数が違う）ものは Apple Music のページのタイトルで確かめる
    need = [tid for tid, e in lookup.items()
            if e["en"] and "oembed" not in e and (e["ja"] is None or e["ja_count"] != e["en_count"])]
    print(f"oEmbed で確認: {len(need):,}件")
    for n, tid in enumerate(need, 1):
        lookup[tid]["oembed"] = oembed_title(tid)
        if n % 50 == 0 or n == len(need):
            save_json(LOOKUP_FILE, lookup)
            print(f"  oEmbed {n:,} / {len(need):,}")
    print("取得完了")


# ── propose ───────────────────────────────────────────────────────
def japan_title(e: dict) -> tuple[str | None, str]:
    """日本版タイトルと、その取得元"""
    if e.get("oembed"):
        return e["oembed"], "oembed"
    if e.get("ja") and e["ja_count"] == e["en_count"]:
        return e["ja"].strip(), "itunes"
    return None, ""


def cmd_propose(_args) -> None:
    lookup: dict = load_json(LOOKUP_FILE, {})
    if not lookup:
        sys.exit("先に fetch を実行してください")

    proposals, stats = [], {"ja": 0, "latin": 0, "changed": 0, "same": 0, "not_found": 0, "not_fetched": 0}
    for r in english_title_tracks():
        e = lookup.get(r["id"])
        if e is None:
            stats["not_fetched"] += 1
            continue
        new, source = japan_title(e)
        if not new:
            stats["not_found"] += 1
            continue
        if new == r["title"]:
            stats["same"] += 1
            continue
        # DBの曲名が Apple の今の英語名と違うのに日本語化でもないものは、Apple側で作品名自体が
        # 変わった可能性がある（例: Cruel Angel (feat. Yoko Takahashi) → Call From The Sky）
        kind = "ja" if has_ja(new) else "latin" if e["en"] == r["title"] else "changed"
        stats[kind] += 1
        proposals.append({
            "id": r["id"], "kind": kind, "artist": r["artist"], "release_date": r["release_date"],
            "old_title": r["title"], "new_title": new, "source": source,
            # DBの曲名が Apple の英語名と違う＝手で直した可能性がある
            "note": "" if e["en"] == r["title"] else f"Appleの英語名: {e['en']}",
        })

    proposals.sort(key=lambda p: (p["kind"], p["artist"], p["release_date"]))
    PROPOSALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(PROPOSALS_FILE, "w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(proposals[0].keys()) if proposals else ["id"])
        w.writeheader()
        w.writerows(proposals)
    print(f"修正候補 {len(proposals):,}件 → {PROPOSALS_FILE.relative_to(ROOT)}")
    print("  " + " / ".join(f"{k}: {v:,}" for k, v in stats.items()))


# ── apply / revert ────────────────────────────────────────────────
def rewrite_search_url(url: str | None, old: str, new: str) -> str | None:
    """検索URLの検索語に含まれる旧曲名を置き換える。直リンクや旧曲名を含まないURLは None

    検索語の「/」は空白にする。Amazon Music の検索URLは「/」をそのまま入れるとトップページに、
    %2F にすると404になる（例: 「星野源 Crazy Crazy/桜の森 - EP」）
    """
    if not url:
        return None
    for prefix in SEARCH_PREFIXES.values():
        if url.startswith(prefix):
            q = unquote(url[len(prefix):])
            if old not in q:
                return None
            q = re.sub(r"\s+", " ", q.replace(old, new).replace("/", " ")).strip()
            return prefix + quote(q, safe="")
    return None


def cmd_apply(args) -> None:
    kinds = set(args.kinds.split(","))
    with open(PROPOSALS_FILE, encoding="utf-8-sig") as f:
        proposals = [p for p in csv.DictReader(f) if p["kind"] in kinds]
    if args.ids:
        ids = set(args.ids.split(","))
        proposals = [p for p in proposals if p["id"] in ids]
    if args.limit:
        proposals = proposals[:args.limit]
    print(f"対象: {len(proposals):,}件（kind: {','.join(sorted(kinds))}）{' ※ドライラン' if args.dry_run else ''}")

    current = {r["id"]: r for r in sb_select_in(
        "tracks", "id", [p["id"] for p in proposals], "id,title,spotify,amazon,youtube")}

    log_path = DATA_DIR / f"applied_{datetime.now():%Y%m%d-%H%M%S}.jsonl"
    log = None if args.dry_run else open(log_path, "w", encoding="utf-8")
    done = skipped = links = 0
    try:
        for n, p in enumerate(proposals, 1):
            row = current.get(p["id"])
            if not row or row["title"] != p["old_title"]:
                print(f"  - スキップ（候補作成後に曲名が変わった）: {p['id']} {p['old_title']}")
                skipped += 1
                continue
            patch = {"title": p["new_title"]}
            for col in SEARCH_PREFIXES:
                url = rewrite_search_url(row[col], p["old_title"], p["new_title"])
                if url:
                    patch[col] = url
            links += len(patch) - 1
            if args.dry_run:
                print(f"  {p['artist']} | {p['old_title']} → {p['new_title']}（検索URL {len(patch) - 1}件）")
            else:
                sb_update("tracks", {"id": f"eq.{p['id']}"}, patch)
                before = {k: row[k] for k in patch}
                log.write(json.dumps({"id": p["id"], "before": before, "after": patch}, ensure_ascii=False) + "\n")
                log.flush()
            done += 1
            if n % 200 == 0:
                print(f"  {n:,} / {len(proposals):,}")
    finally:
        if log:
            log.close()
    print(f"{'反映予定' if args.dry_run else '反映'}: {done:,}件（検索URLの更新 {links:,}件） / スキップ: {skipped:,}件")
    if log:
        print(f"変更前の値: {log_path.relative_to(ROOT)}（戻すときは revert に渡す）")


def cmd_revert(args) -> None:
    entries = [json.loads(line) for line in open(args.log, encoding="utf-8") if line.strip()]
    current = {r["id"]: r for r in sb_select_in("tracks", "id", [e["id"] for e in entries], "id,title")}
    reverted = skipped = 0
    for e in entries:
        if current.get(e["id"], {}).get("title") != e["after"]["title"]:
            print(f"  - スキップ（反映後に曲名が変わった）: {e['id']}")
            skipped += 1
            continue
        sb_update("tracks", {"id": f"eq.{e['id']}"}, e["before"])
        reverted += 1
    print(f"元に戻した: {reverted:,}件 / スキップ: {skipped:,}件")


def main() -> None:
    parser = ArgumentParser(description="英語・ローマ字表記の曲名を Apple Music 日本版のタイトルに直す")
    sub = parser.add_subparsers(dest="cmd", required=True)
    sub.add_parser("fetch").set_defaults(func=cmd_fetch)
    sub.add_parser("propose").set_defaults(func=cmd_propose)
    p = sub.add_parser("apply")
    p.add_argument("--kinds", default="ja", help="反映する kind（カンマ区切り、例: ja,latin）")
    p.add_argument("--ids", default="", help="反映する曲のID（カンマ区切り、試験反映用）")
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
