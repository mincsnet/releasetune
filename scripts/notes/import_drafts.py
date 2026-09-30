"""
import_drafts.py — 下書きを機械チェックして track_note_drafts に保存する
=======================================================================
data/notes/drafts.json（Claude が STYLE.md に従って書いたもの）を読み、
機械チェックの結果と抜き取りレビューの対象を付けて status=drafted で保存する。

drafts.json の形式:
    [
      {"wiki_title": "少女A", "note_short": "…", "note_long": "…",
       "facts": [{"claim": "オリコン週間最高5位", "source": "（出典テキストの該当箇所）"}]},
      {"wiki_title": "…", "skip": true, "skip_reason": "出典に発売日以外の情報がない"}
    ]

抜き取り（review_required=true）:
    - 機械チェックに引っかかったもの、書き直し依頼への再提出 → 全件
    - 人がレビューを終えた記事が PILOT_ARTICLES 件になるまで（試作期間） → 全件
    - それ以外 → 1割（最低3件）を無作為に

使い方:
    python3 scripts/notes/import_drafts.py --dry-run   # チェックだけ（保存しない）
    python3 scripts/notes/import_drafts.py             # data/notes/drafts.json を保存
"""

import json, math, random, re, sys, unicodedata
from argparse import ArgumentParser
from collections import defaultdict
from difflib import SequenceMatcher
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from common import (DATA_DIR, key, now_iso, sb_in, sb_select, sb_select_in, sb_update, today_jst)

PILOT_ARTICLES = 50
SAMPLE_RATE    = 0.1
SAMPLE_MIN     = 3
SHORT_MAX      = 60
LONG_MIN, LONG_MAX = 150, 400
VERBATIM_MAX   = 20

UNITS       = set("位枚年月日万億千回週作曲周目人名組度分秒本部倍番期代歳作公演局")
# 文末は体言止めか「ます」形（STYLE.md）。常体（だ・である・した など）の文末だけを指摘する
MASU_END    = re.compile(r"(です|でした|ます|ました|ません|ませんでした|でしょう)$")
PLAIN_END   = re.compile(r"(である|であった|だ|だった|した|しない|する|している|していた|なった|なる|いる|いた|"
                         r"ある|あった|ない|なかった|れた|れる|せた|せる|った|んだ|いだ|という|とされる)$")
FORBIDDEN   = ["Wikipedia", "ウィキペディア", "によると", "年前"]
EVALUATIVE  = ["名曲", "代表曲", "不朽", "伝説", "大ヒット", "名盤", "傑作", "国民的", "珠玉"]


def nfkc(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "")


def compact(s: str) -> str:
    return re.sub(r"\s+", "", nfkc(s))


def check(short: str, long_: str, facts: list, source: str, tracks: list[dict]) -> list[dict]:
    issues: list[dict] = []
    add = lambda t, d: issues.append({"type": t, "detail": d})

    if not short:
        add("short_empty", "短文がありません")
    elif len(short) > SHORT_MAX:
        add("short_length", f"短文が{len(short)}字（{SHORT_MAX}字以内）")
    if long_ and not (LONG_MIN <= len(long_) <= LONG_MAX):
        add("long_length", f"長文が{len(long_)}字（{LONG_MIN}〜{LONG_MAX}字、または空）")

    for label, text in (("短文", short), ("長文", long_)):
        if not text:
            continue
        if not text.endswith("。"):
            add("style", f"{label}が「。」で終わっていません")
        # 作品名の中の「。」（例:『心が叫びたがってるんだ。』）で文を区切らないよう、『』「」の中身を伏せてから分ける
        masked = re.sub(r"[『「][^』」]*[』」]", "『』", text)
        for sent in [s for s in masked.split("。") if s.strip()]:
            tail = sent.rstrip("」』）)").strip()
            if not MASU_END.search(tail) and PLAIN_END.search(tail):
                add("style", f"{label}: 常体の文末「…{sent[-12:]}。」")

    body = short + long_
    src = compact(source)
    src_nums = src.replace(",", "")
    db_nums = set()
    for t in tracks:
        y, m, d = t["release_date"].split("-")
        db_nums |= {y, str(int(m)), str(int(d))}
    # 数字は直後の単位1文字（位・枚・年・万 など）まで含めて照合する（数字だけだと緩すぎるため）。
    # 「AKB48」「TOP5」のように英字に続く数字は英字ごと照合し、助詞（「48が」の「が」）は単位として扱わない
    for prefix, num, unit in re.findall(r"([A-Za-z]*)(\d+(?:[.,]\d+)*)(.?)", nfkc(body)):
        n = num.replace(",", "")
        if prefix:
            ok = (prefix + n).lower() in src_nums.lower()
        elif unit in UNITS:
            ok = n + unit in src_nums or (n in db_nums and unit in "年月日")
        else:
            ok = n in src_nums or n in db_nums
        if not ok:
            add("number", f"出典にない数字「{prefix}{num}{unit if unit in UNITS else ''}」")

    names_ok = key(source) + "".join(key(t["title"]) + key(t["artist"]) for t in tracks)
    for q in re.findall(r"[『「]([^』」]+)[』」]", body):
        if key(q) not in names_ok:
            add("quote", f"出典にない名前「{q}」")

    plain = compact(re.sub(r"[『「][^』」]*[』」]", "", body))
    if plain and src:
        m = SequenceMatcher(None, plain, src, autojunk=False).find_longest_match(0, len(plain), 0, len(src))
        if m.size > VERBATIM_MAX:
            add("verbatim", f"出典と{m.size}字一致「{plain[m.a:m.a + m.size]}」")

    for w in FORBIDDEN:
        if w in body:
            add("forbidden", f"使わない表現「{w}」")
    for w in EVALUATIVE:
        if w in body and w not in source:
            add("evaluative", f"出典にない評価語「{w}」")

    if not facts:
        add("no_facts", "根拠（facts）がありません")
    return issues


def main():
    ap = ArgumentParser(description="下書きを機械チェックして保存する")
    ap.add_argument("path", nargs="?", default=str(DATA_DIR / "drafts.json"))
    ap.add_argument("--batch", default=today_jst(), help="バッチID（デフォルト: 今日の日付）")
    ap.add_argument("--dry-run", action="store_true", help="チェック結果を表示するだけで保存しない")
    ap.add_argument("--seed", type=int, help="抜き取りの乱数シード（テスト用）")
    args = ap.parse_args()

    drafts = json.loads(Path(args.path).read_text(encoding="utf-8"))
    if not isinstance(drafts, list):
        sys.exit("drafts.json はリストである必要があります")

    titles = [d.get("wiki_title", "") for d in drafts]
    rows = [r for r in sb_select_in("track_note_drafts", "wiki_title", titles,
                                    "track_id,status,wiki_title,source_text", chunk=30)
            if r["status"] in ("sourced", "rewrite")]
    groups: dict[str, list[dict]] = defaultdict(list)
    for r in rows:
        groups[r["wiki_title"]].append(r)
    tracks = {t["id"]: t for t in sb_select_in("tracks", "id", [r["track_id"] for r in rows],
                                               "id,title,artist,release_date")}

    # 試作期間は「人がレビューを終えた記事」が PILOT_ARTICLES 件になるまで（書いただけの記事は数えない）
    reviewed = {r["wiki_title"] for r in sb_select("track_note_drafts", {
        "select": "wiki_title", "status": "in.(published,rewrite,rejected)"})}
    pilot = len(reviewed) < PILOT_ARTICLES

    results = []   # (title, ids, patch)
    errors = []
    for d in drafts:
        title = d.get("wiki_title", "")
        g = groups.get(title)
        if not g:
            errors.append(f"「{title}」は執筆待ち（sourced / rewrite）にありません")
            continue
        ids = [r["track_id"] for r in g]
        if d.get("skip"):
            results.append((title, ids, {"status": "insufficient", "note_short": None, "note_long": None,
                                         "facts": None, "review_required": False,
                                         "issues": [{"type": "skipped", "detail": d.get("skip_reason", "")}]}))
            continue
        short = (d.get("note_short") or "").strip()
        long_ = (d.get("note_long") or "").strip()
        facts = d.get("facts") or []
        issues = check(short, long_, facts, g[0]["source_text"] or "", [tracks[i] for i in ids if i in tracks])
        results.append((title, ids, {"status": "drafted", "note_short": short, "note_long": long_ or None,
                                     "facts": facts, "issues": issues,
                                     "review_required": bool(issues) or pilot or g[0]["status"] == "rewrite"}))

    # 抜き取り: まだ要確認になっていない記事から1割（最低3件）
    rest = [r for r in results if r[2]["status"] == "drafted" and not r[2]["review_required"]]
    if rest:
        rng = random.Random(args.seed)
        k = min(len(rest), max(SAMPLE_MIN, math.ceil(len(rest) * SAMPLE_RATE)))
        for r in rng.sample(rest, k):
            r[2]["review_required"] = True

    for title, ids, patch in results:
        mark = "要確認" if patch["review_required"] else "抜き取り外"
        if patch["status"] == "insufficient":
            mark = "見送り"
        print(f"[{mark}] {title}（{len(ids)}曲）")
        for i in patch.get("issues") or []:
            print(f"    ⚠ {i['detail']}")

    for e in errors:
        print(f"❌ {e}")

    n_draft = sum(r[2]["status"] == "drafted" for r in results)
    n_review = sum(r[2]["review_required"] for r in results)
    n_issue = sum(bool(r[2].get("issues")) and r[2]["status"] == "drafted" for r in results)
    print(f"\n下書き {n_draft}記事（うち要確認 {n_review}、チェック指摘あり {n_issue}）/ 見送り {len(results) - n_draft} / エラー {len(errors)}"
          + ("（試作期間: 全件確認）" if pilot else ""))

    if args.dry_run:
        print("（ドライラン: 保存していません）")
        return
    for title, ids, patch in results:
        sb_update("track_note_drafts", {"track_id": sb_in(ids)},
                  {**patch, "batch_id": args.batch, "updated_at": now_iso()})
    print(f"保存しました（バッチ {args.batch}）")


if __name__ == "__main__":
    main()
