"""
collect.py — Wikipedia から紹介文の出典を集める
================================================
曲数の多い邦楽アーティストから順に、DBの曲と Wikipedia の記事
（「Category:◯◯の楽曲」「Category:◯◯のアルバム」の記事）を照合し、
出典テキストを track_note_drafts に保存する。

- 曲名は正規化した完全一致でのみ照合する（あいまい一致はしない）
- 記事の発売日（Infobox の最初の日付）とDBの release_date が同じ年でなければ date_mismatch
- 記事が見つからない曲も no_article として記録し、次回以降は調べ直さない
- 未執筆（sourced）の記事が --articles 件に満たない分だけ集める（毎日の積み残しを増やさない）
- アーティストと Wikipedia 記事の対応は artists.csv に保存する（人が見て直せる）

使い方:
    python3 scripts/notes/collect.py --dry-run --artist "中森明菜"   # 書き込みなしで確認
    python3 scripts/notes/collect.py --articles 20                   # 毎日の実行
"""

import csv, re, sys
from argparse import ArgumentParser
from collections import Counter, defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (ARTISTS_CSV, build_source_text, date_matches, key, now_iso, sb_select,
                    sb_select_in, sb_upsert, title_keys, wiki_get, wiki_title_key, wiki_url)

CSV_FIELDS = ["db_artist", "wiki_title", "is_japanese", "categories", "status", "checked_at"]

MUSICIAN = r"(歌手|バンド|グループ|アイドル|ミュージシャン|シンガーソングライター|ユニット|ラッパー|作曲家|音楽家|演歌|DJ|ピアニスト|ギタリスト|ボーカリスト|ヴォーカリスト|声優)"
RE_MUSICIAN = re.compile(r"^Category:.*(" + MUSICIAN[1:-1] + r"|のアーティスト)")
RE_JAPANESE = re.compile(r"^Category:(\d+世紀)?日本の.*" + MUSICIAN)
# 海外と判定するのは、国名の付いた音楽家のカテゴリ（例:「アメリカ合衆国の男性ラッパー」）があるときだけ。
# 「7人組の音楽グループ」「演歌歌手」のように国名のないカテゴリしかない記事は日本の音楽家として扱う
FOREIGN_COUNTRIES = (
    "大韓民国|韓国|朝鮮民主主義人民共和国|中華民国|台湾|中華人民共和国|中国|香港|マカオ|モンゴル|"
    "アメリカ合衆国|アメリカ|イギリス|イングランド|スコットランド|ウェールズ|北アイルランド|アイルランド|"
    "カナダ|オーストラリア|ニュージーランド|フランス|ドイツ|イタリア|スペイン|ポルトガル|オランダ|ベルギー|"
    "スイス|オーストリア|スウェーデン|ノルウェー|デンマーク|フィンランド|アイスランド|ロシア|ウクライナ|"
    "ポーランド|チェコ|ハンガリー|ルーマニア|ギリシャ|トルコ|イスラエル|ブラジル|アルゼンチン|チリ|ペルー|"
    "メキシコ|コロンビア|ベネズエラ|キューバ|プエルトリコ|ジャマイカ|ドミニカ共和国|バルバドス|トリニダード・トバゴ|"
    "フィリピン|タイ|インドネシア|マレーシア|シンガポール|ベトナム|インド|南アフリカ共和国|ナイジェリア"
)
RE_FOREIGN = re.compile(r"^Category:(\d+世紀)?(" + FOREIGN_COUNTRIES + r")の.*" + MUSICIAN)
SUFFIXES = ["バンド", "歌手", "音楽グループ", "グループ", "ユニット", "アイドルグループ", "ミュージシャン",
            "フォークグループ", "ロックバンド", "音楽ユニット", "歌手グループ"]


# ── artists.csv ───────────────────────────────────────────────────
def load_artists() -> dict[str, dict]:
    if not ARTISTS_CSV.exists():
        return {}
    with open(ARTISTS_CSV, encoding="utf-8", newline="") as f:
        return {r["db_artist"]: r for r in csv.DictReader(f)}


def save_artists(rows: dict[str, dict]) -> None:
    with open(ARTISTS_CSV, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=CSV_FIELDS)
        w.writeheader()
        for r in rows.values():
            w.writerow({k: r.get(k, "") for k in CSV_FIELDS})


# ── アーティスト記事の特定 ────────────────────────────────────────
def page_info(titles: list[str]) -> list[dict]:
    """titles を順に解決し [{asked, title, missing, disambiguation, categories}] を返す"""
    data = wiki_get({
        "action": "query", "titles": "|".join(titles), "redirects": "1",
        "prop": "categories|pageprops", "clshow": "!hidden", "cllimit": "max",
        "ppprop": "disambiguation",
    })
    q = data.get("query", {})
    alias = {}
    for n in q.get("normalized", []):
        alias[n["from"]] = n["to"]
    for r in q.get("redirects", []):
        alias[r["from"]] = r["to"]
    pages = {p["title"]: p for p in q.get("pages", [])}
    out = []
    for t in titles:
        final = t
        while final in alias:
            final = alias[final]
        p = pages.get(final, {"missing": True})
        out.append({
            "asked": t,
            "title": final,
            "missing": bool(p.get("missing") or p.get("invalid")),
            "disambiguation": "disambiguation" in p.get("pageprops", {}),
            "categories": [c["title"] for c in p.get("categories", [])],
        })
    return out


def judge(info: dict) -> str | None:
    """'jp' / 'foreign' / None（音楽家の記事ではない）"""
    if info["missing"] or info["disambiguation"]:
        return None
    cats = info["categories"]
    if any(RE_JAPANESE.match(c) for c in cats):
        return "jp"
    if any(RE_FOREIGN.match(c) for c in cats):
        return "foreign"
    if any(RE_MUSICIAN.match(c) for c in cats):
        return "jp"
    return None


def music_categories(wiki_title: str) -> list[str]:
    base = re.sub(r"\s*\([^)]*\)$", "", wiki_title)
    names = []
    for b in dict.fromkeys([base, wiki_title]):
        names += [f"Category:{b}の楽曲", f"Category:{b}のアルバム"]
    data = wiki_get({"action": "query", "titles": "|".join(names), "prop": "categoryinfo"})
    return [p["title"] for p in data["query"]["pages"]
            if not p.get("missing") and p.get("categoryinfo", {}).get("pages", 0) > 0]


def resolve_artist(name: str) -> dict:
    row = {"db_artist": name, "wiki_title": "", "is_japanese": "", "categories": "",
           "status": "unresolved", "checked_at": now_iso()[:10]}

    bases = [name.strip()]
    if re.search(r"[぀-ヿ一-鿿]", name) and re.search(r"\s", name):
        bases.append(re.sub(r"\s+", "", name))          # 「福山 雅治」→「福山雅治」
    tries = [bases, [f"{b} ({s})" for b in bases for s in SUFFIXES]]

    found = None
    for titles in tries:
        for info in page_info(titles):
            verdict = judge(info)
            if verdict:
                found = (info, verdict)
                break
        if found:
            break

    if not found:
        # 検索で候補を探し、記事名（曖昧さ回避の括弧を除く）がアーティスト名と一致するものだけ採用
        hits = wiki_get({"action": "query", "list": "search", "srsearch": name,
                         "srlimit": "10", "srnamespace": "0"})["query"]["search"]
        names = {key(b) for b in bases}
        titles = [h["title"] for h in hits if wiki_title_key(h["title"]) in names]
        if titles:
            for info in page_info(titles):
                verdict = judge(info)
                if verdict:
                    found = (info, verdict)
                    break

    if not found:
        return row

    info, verdict = found
    row["wiki_title"] = info["title"]
    if verdict == "foreign":
        row["is_japanese"], row["status"] = "0", "skip"
        return row
    row["is_japanese"] = "1"
    row["categories"] = ";".join(music_categories(info["title"]))
    row["status"] = "pending"
    return row


# ── 曲と記事の照合 ────────────────────────────────────────────────
def category_members(cat: str) -> list[str]:
    out, cont = [], None
    while True:
        p = {"action": "query", "list": "categorymembers", "cmtitle": cat,
             "cmlimit": "500", "cmnamespace": "0", "cmtype": "page"}
        if cont:
            p["cmcontinue"] = cont
        data = wiki_get(p)
        out += [m["title"] for m in data["query"]["categorymembers"]]
        cont = data.get("continue", {}).get("cmcontinue")
        if not cont:
            return out


def fetch_wikitext(titles: list[str]) -> dict[str, dict]:
    """{指定した記事名: {title: 転送を解決した記事名, revid, wikitext}}
    カテゴリには転送ページ（例:「恋人 (福山雅治の曲)」→「All My Loving/恋人」）も入っているため転送を解決する"""
    out = {}
    for i in range(0, len(titles), 50):
        chunk = titles[i:i + 50]
        data = wiki_get({"action": "query", "titles": "|".join(chunk), "redirects": "1",
                         "prop": "revisions", "rvprop": "content|ids", "rvslots": "main"})
        q = data["query"]
        alias = {r["from"]: r["to"] for r in q.get("normalized", []) + q.get("redirects", [])}
        pages = {p["title"]: p for p in q["pages"] if not p.get("missing") and p.get("revisions")}
        for t in chunk:
            final = t
            while final in alias:
                final = alias[final]
            if final in pages:
                rev = pages[final]["revisions"][0]
                out[t] = {"title": final, "revid": rev["revid"], "wikitext": rev["slots"]["main"]["content"]}
    return out


def draft_row(track_id: str, status: str, **kw) -> dict:
    # upsert は全行が同じ列を持つ必要があるため、使わない列も None で揃える
    return {
        "track_id": track_id, "status": status,
        "wiki_title": kw.get("wiki_title"), "wiki_url": kw.get("wiki_url"),
        "wiki_revid": kw.get("wiki_revid"), "source_text": kw.get("source_text"),
        "issues": kw.get("issues", []), "updated_at": now_iso(),
    }


def process_artist(artist: dict, need: int, dry_run: bool, mmdd: str | None = None) -> tuple[list[dict], set[str], bool]:
    """(書き込む行, 今回 sourced にした記事名, このアーティストの曲をすべて処理したか)
    mmdd を指定すると、その日付（例: "09-30"）の曲だけを対象にする"""
    name = artist["db_artist"]
    params = {"select": "id,title,release_date", "artist": f"eq.{name}", "order": "release_date.asc"}
    if mmdd:
        params["mmdd"] = f"eq.{mmdd}"
    tracks = sb_select("tracks", params)
    try:
        done_ids = {r["track_id"] for r in
                    sb_select_in("track_note_drafts", "track_id", [t["id"] for t in tracks], "track_id")}
    except Exception:
        if not dry_run:
            raise
        done_ids = set()  # ドライランはテーブル作成前でも確認できるようにする
    todo = [t for t in tracks if t["id"] not in done_ids]
    if not todo:
        return [], set(), True

    keymap: dict[str, list[str]] = defaultdict(list)
    for cat in filter(None, artist["categories"].split(";")):
        for title in category_members(cat):
            k = wiki_title_key(title)
            if title not in keymap[k]:
                keymap[k].append(title)

    rows: list[dict] = []
    cands: dict[str, list[str]] = {}
    for t in todo:
        c: list[str] = []
        for k in title_keys(t["title"]):
            for title in keymap.get(k, []):
                if title not in c:
                    c.append(title)
            if c:
                break
        if c:
            cands[t["id"]] = c
        else:
            # 照合した時点の曲名を残す（曲名がローマ字表記などで、後で直ったときに照合し直せるように）
            rows.append(draft_row(t["id"], "no_article", issues=[{"type": "no_article", "title": t["title"]}]))

    pages = fetch_wikitext(sorted({title for c in cands.values() for title in c}))
    parsed = {title: build_source_text(p["wikitext"]) for title, p in pages.items()}

    # 曲ごとに、発売日が合う記事を選ぶ
    chosen: dict[str, str] = {}
    for t in todo:
        if t["id"] not in cands:
            continue
        ok = [title for title in cands[t["id"]] if title in parsed and date_matches(parsed[title][1], t["release_date"])]
        if ok:
            chosen[t["id"]] = ok[0]
        else:
            first = cands[t["id"]][0]
            final = pages.get(first, {}).get("title", first)
            rows.append(draft_row(t["id"], "date_mismatch", wiki_title=final, wiki_url=wiki_url(final),
                                  issues=[{"type": "date_mismatch", "db_date": t["release_date"],
                                           "wiki_date": parsed.get(first, (None, None))[1]}]))

    # 記事単位（転送を解決した記事名）でまとめ、必要数に達したら残りは次回へ回す
    groups: dict[str, list[dict]] = defaultdict(list)
    for t in todo:
        if t["id"] in chosen:
            groups[pages[chosen[t["id"]]]["title"]].append(t)
    asked = {pages[req]["title"]: req for req in chosen.values()}
    sourced: set[str] = set()
    complete = True
    for title, ts in sorted(groups.items(), key=lambda g: g[1][0]["release_date"]):
        if len(sourced) >= need:
            complete = False
            break
        req = asked[title]
        text, _ = parsed[req]
        for t in ts:
            rows.append(draft_row(t["id"], "sourced", wiki_title=title, wiki_url=wiki_url(title),
                                  wiki_revid=pages[req]["revid"], source_text=text))
        sourced.add(title)

    if dry_run:
        n = Counter(r["status"] for r in rows)
        print(f"  曲 {len(todo)}件: sourced {n['sourced']} / date_mismatch {n['date_mismatch']} / no_article {n['no_article']}（記事 {len(sourced)}件）")
        for title in list(sourced)[:5]:
            print(f"    ✓ {title}: " + " / ".join(f"{t['title']}（{t['release_date']}）" for t in groups[title]))
        for r in [r for r in rows if r["status"] == "date_mismatch"][:5]:
            print(f"    △ {r['wiki_title']}: DB {r['issues'][0]['db_date']} / 記事 {r['issues'][0]['wiki_date']}")
    return rows, sourced, complete


def main():
    ap = ArgumentParser(description="Wikipedia から紹介文の出典を集める")
    ap.add_argument("--articles", type=int, default=20, help="未執筆の記事をこの件数まで補充する（デフォルト: 20）")
    ap.add_argument("--artist", help="このアーティストだけ処理する（テスト用。補充件数の上限は無視）")
    ap.add_argument("--per-artist", type=int, default=10**9, help="1アーティストあたりの新しい記事の上限（試作で幅広く集めたいとき用）")
    ap.add_argument("--mmdd", help="この日付（例: 09-30）にリリースされた曲だけを処理する（補充件数の上限は無視）")
    ap.add_argument("--dry-run", action="store_true", help="Supabase と artists.csv に書き込まない")
    args = ap.parse_args()

    artists = load_artists()

    if args.artist:
        order = [args.artist]
        need = 10**9
    elif args.mmdd:
        counts = Counter(r["artist"] for r in sb_select("tracks", {"select": "artist", "mmdd": f"eq.{args.mmdd}"}))
        order = [a for a, _ in counts.most_common()]
        need = 10**9
        print(f"{args.mmdd} の曲: {sum(counts.values())}曲 / {len(order)}アーティスト")
    else:
        backlog = {r["wiki_title"] for r in sb_select("track_note_drafts",
                   {"select": "wiki_title", "status": "eq.sourced"})}
        need = args.articles - len(backlog)
        print(f"未執筆の記事: {len(backlog)}件 → 今回の補充: {max(need, 0)}件")
        if need <= 0:
            return
        counts = Counter(r["artist"] for r in sb_select("tracks", {"select": "artist"}))
        order = [a for a, _ in counts.most_common()]

    total_rows, total_sourced = 0, 0
    for name in order:
        if name not in artists:
            print(f"[解決] {name}")
            artists[name] = resolve_artist(name)
            a = artists[name]
            print(f"  → {a['wiki_title'] or '見つからず'} / {a['status']} / {a['categories'] or '-'}")
            if not args.dry_run:
                save_artists(artists)
        a = artists[name]
        # 日付指定のときは、ほかの日付の曲を処理済みのアーティスト（done）も対象にする
        if a["status"] != "pending" and not (args.mmdd and a["status"] == "done"):
            if args.artist:
                print(f"  対象外（status={a['status']}）")
            continue

        print(f"[収集] {name}")
        rows, sourced, complete = process_artist(a, min(need - total_sourced, args.per_artist), args.dry_run, args.mmdd)
        if args.mmdd:
            complete = False   # 日付の曲しか見ていないので、アーティストの完了とはみなさない
        if not args.dry_run:
            if rows:
                sb_upsert("track_note_drafts", rows, on_conflict="track_id")
            if complete:
                a["status"] = "done"
                save_artists(artists)
        total_rows += len(rows)
        total_sourced += len(sourced)
        print(f"  記録 {len(rows)}曲 / 新しい記事 {len(sourced)}件{'（このアーティストは完了）' if complete else ''}")
        if total_sourced >= need:
            break

    print(f"\n完了: 記録 {total_rows}曲 / 新しい記事 {total_sourced}件{'（ドライラン）' if args.dry_run else ''}")


if __name__ == "__main__":
    main()
