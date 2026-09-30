"""
scripts/notes 共通処理
======================
- .env の読み込み、Supabase REST、Wikipedia API（ja）
- 曲名・アーティスト名の正規化
- wikitext の整形（Infobox の抽出、ref・テンプレート・表の除去）

各スクリプトからは `from common import ...` で使う（scripts/notes/ で実行する前提ではなく、
各スクリプトが自分のディレクトリを sys.path に入れてから import する）。
"""

import os, re, time, unicodedata
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import quote

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SERVICE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SITE_URL     = os.getenv("SITE_URL", "https://www.releasetune.com")
CRON_SECRET  = os.getenv("CRON_SECRET", "")

NOTES_DIR   = Path(__file__).resolve().parent
DATA_DIR    = ROOT / "data" / "notes"
ARTISTS_CSV = NOTES_DIR / "artists.csv"

JST = timezone(timedelta(hours=9))

# 下書きの状態
#   no_article    : Wikipediaに対応する記事なし
#   date_mismatch : 記事はあるが発売日がDBと合わない（再発・別バージョン等の可能性）
#   sourced       : 出典テキスト取得済み・未執筆
#   drafted       : 下書き済み・レビュー待ち
#   rewrite       : レビューで書き直し依頼
#   insufficient  : 執筆時に「出典の情報が足りない」と判断して見送り
#   rejected      : レビューで「掲載しない」
#   published     : 承認して tracks に反映済み


def today_jst() -> str:
    return datetime.now(JST).strftime("%Y-%m-%d")


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ── HTTP（一時的なネットワーク断に対するリトライ付き） ──────────────
def http_request(method: str, url: str, retries: int = 3, backoff: float = 2.0, **kwargs):
    last_exc = None
    for attempt in range(retries):
        try:
            return requests.request(method, url, **kwargs)
        except requests.exceptions.RequestException as e:
            last_exc = e
            wait = backoff * (attempt + 1)
            print(f"    [HTTP] {method} {url.split('?')[0]} 失敗 ({e.__class__.__name__})。{wait:.0f}秒後にリトライ ({attempt + 1}/{retries})")
            time.sleep(wait)
    raise last_exc


# ── Supabase ──────────────────────────────────────────────────────
def supabase_headers(prefer: str | None = None) -> dict:
    h = {
        "apikey":        SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type":  "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def sb_select(table: str, params: dict, page_size: int = 1000) -> list[dict]:
    """全件取得（limit/offset でページング）"""
    rows: list[dict] = []
    offset = 0
    while True:
        p = {**params, "limit": str(page_size), "offset": str(offset)}
        resp = http_request("get", f"{SUPABASE_URL}/rest/v1/{table}",
                            headers=supabase_headers(), params=p, timeout=60)
        resp.raise_for_status()
        page = resp.json()
        rows.extend(page)
        if len(page) < page_size:
            return rows
        offset += page_size


def sb_in(values: list[str]) -> str:
    """PostgREST の in.(...) 用。値はダブルクォートで囲む"""
    return "in.(" + ",".join('"' + v.replace('"', '\\"') + '"' for v in values) + ")"


def sb_select_in(table: str, column: str, values: list[str], select: str, chunk: int = 100) -> list[dict]:
    rows: list[dict] = []
    for i in range(0, len(values), chunk):
        rows.extend(sb_select(table, {"select": select, column: sb_in(values[i:i + chunk])}))
    return rows


def sb_upsert(table: str, rows: list[dict], on_conflict: str, chunk: int = 200) -> None:
    for i in range(0, len(rows), chunk):
        resp = http_request(
            "post", f"{SUPABASE_URL}/rest/v1/{table}",
            headers=supabase_headers("resolution=merge-duplicates,return=minimal"),
            params={"on_conflict": on_conflict},
            json=rows[i:i + chunk], timeout=60,
        )
        if not resp.ok:
            raise RuntimeError(f"upsert {table} 失敗: {resp.status_code} {resp.text[:300]}")


def sb_update(table: str, filters: dict, patch: dict) -> None:
    resp = http_request(
        "patch", f"{SUPABASE_URL}/rest/v1/{table}",
        headers=supabase_headers("return=minimal"),
        params=filters, json=patch, timeout=60,
    )
    if not resp.ok:
        raise RuntimeError(f"update {table} 失敗: {resp.status_code} {resp.text[:300]}")


def revalidate_site() -> bool:
    """公開した紹介文がすぐ表示されるよう、本番サイトのデータ取得キャッシュを消す（/api/revalidate）。
    失敗しても処理は止めない（キャッシュの期限切れ＝最大24時間で自然に反映される）"""
    if not CRON_SECRET:
        print("  ⚠ CRON_SECRET がないため、サイトのキャッシュを消せませんでした（最大24時間で反映されます）")
        return False
    try:
        r = requests.post(f"{SITE_URL}/api/revalidate", headers={"Authorization": f"Bearer {CRON_SECRET}"}, timeout=30)
    except requests.exceptions.RequestException as e:
        print(f"  ⚠ サイトのキャッシュを消せませんでした（{e.__class__.__name__}）。最大24時間で反映されます")
        return False
    if not r.ok:
        print(f"  ⚠ サイトのキャッシュを消せませんでした（HTTP {r.status_code}）。最大24時間で反映されます")
        return False
    print("  サイトのキャッシュを消しました（公開した紹介文がすぐ表示されます）")
    return True


# ── Wikipedia API ─────────────────────────────────────────────────
WIKI_API   = "https://ja.wikipedia.org/w/api.php"
WIKI_UA    = "ReleaseTuneNoteBot/1.0 (https://releasetune.com/)"
WIKI_SLEEP = 0.5


def wiki_get(params: dict) -> dict:
    """逐次アクセス・maxlag 付き。maxlag エラー時は待って再試行"""
    p = {"format": "json", "formatversion": "2", "maxlag": "5", **params}
    for attempt in range(5):
        resp = http_request("get", WIKI_API, params=p, headers={"User-Agent": WIKI_UA}, timeout=30)
        time.sleep(WIKI_SLEEP)
        if resp.status_code == 429 or resp.status_code >= 500:
            time.sleep(5 * (attempt + 1))
            continue
        resp.raise_for_status()
        data = resp.json()
        if data.get("error", {}).get("code") == "maxlag":
            time.sleep(int(resp.headers.get("Retry-After", "5")))
            continue
        if "error" in data:
            raise RuntimeError(f"Wikipedia API エラー: {data['error']}")
        return data
    raise RuntimeError("Wikipedia API: リトライ上限")


def wiki_url(title: str) -> str:
    return "https://ja.wikipedia.org/wiki/" + quote(title.replace(" ", "_"), safe="()_,'!-.:")


# ── 正規化 ────────────────────────────────────────────────────────
_PUNCT = re.compile(r"[\s　・･\-‐‑–—―ー~〜～_'\"“”‘’`!！?？.,，、。:：;；/／\\&＆+＋*＊#＃()（）\[\]［］{}｛｝〈〉《》<>＜＞「」『』【】]")


def key(s: str) -> str:
    """照合用キー: NFKC・小文字化し、空白と記号を除く（長音「ー」も除く）"""
    return _PUNCT.sub("", unicodedata.normalize("NFKC", s or "").lower())


_BRACKETS = re.compile(r"\s*[\(\[（［<＜][^\)\]）］>＞]*[\)\]）］>＞]")


def title_keys(db_title: str) -> list[str]:
    """DBの曲名（iTunes表記）から照合候補キーを作る。精度優先で完全一致のみに使う"""
    t0 = re.sub(r"\s+-\s+(Single|EP)$", "", db_title.strip())
    cands = [t0]
    t1 = _BRACKETS.sub("", t0).strip()          # (2014 Remaster)・[Type-A]・(+3) 等
    cands.append(t1)
    t2 = re.sub(r"\s+-[^-]+-$", "", t1).strip()  # 「飾りじゃないのよ涙は -JAZZ-」等
    cands.append(t2)
    t3 = re.sub(r"\s*(feat\.|ft\.|featuring)\s.*$", "", t2, flags=re.I).strip()
    cands.append(t3)
    out: list[str] = []
    for c in cands:
        k = key(c)
        if k and k not in out:
            out.append(k)
    return out


def wiki_title_key(title: str) -> str:
    """記事名から曖昧さ回避の括弧（例:「SOLITUDE (中森明菜の曲)」）を除いたキー"""
    return key(re.sub(r"\s*\([^)]*\)$", "", title))


# ── wikitext 整形 ─────────────────────────────────────────────────
def _find_close(text: str, start: int, open_s: str, close_s: str) -> int:
    """text[start:] が open_s で始まる前提で、対応する close_s の終端位置を返す（見つからなければ -1）"""
    depth, i = 0, start
    while i < len(text):
        if text.startswith(open_s, i):
            depth += 1
            i += len(open_s)
        elif text.startswith(close_s, i):
            depth -= 1
            i += len(close_s)
            if depth == 0:
                return i
        else:
            i += 1
    return -1


def _split_params(inner: str) -> list[str]:
    """テンプレート内側をトップレベルの | で分割"""
    parts, buf, depth_t, depth_l, i = [], [], 0, 0, 0
    while i < len(inner):
        two = inner[i:i + 2]
        if two == "{{":
            depth_t += 1; buf.append(two); i += 2; continue
        if two == "}}":
            depth_t -= 1; buf.append(two); i += 2; continue
        if two == "[[":
            depth_l += 1; buf.append(two); i += 2; continue
        if two == "]]":
            depth_l -= 1; buf.append(two); i += 2; continue
        if inner[i] == "|" and depth_t == 0 and depth_l == 0:
            parts.append("".join(buf)); buf = []; i += 1; continue
        buf.append(inner[i]); i += 1
    parts.append("".join(buf))
    return parts


_KEEP_INNER = {"plainlist", "flatlist", "ubl", "unbulleted list", "hlist", "small", "nowrap",
               "lang", "nihongo", "ruby", "読み仮名", "読み仮名 ruby不使用", "smaller", "big",
               "start date", "start date and age", "release date", "release date and age", "dts",
               "分数", "frac", "sfrac"}


def _render_template(inner: str) -> str:
    parts = _split_params(inner)
    name = parts[0].strip().lower()
    args = [p for p in parts[1:] if "=" not in p.split("|")[0] or name in ("plainlist", "flatlist")]
    if name in ("plainlist", "flatlist"):
        return "\n".join(parts[1:])
    if name in ("ubl", "unbulleted list", "hlist"):
        return "、".join(a.strip() for a in args)
    if name in ("start date", "start date and age", "release date", "release date and age", "dts"):
        nums = [a.strip() for a in args if a.strip().isdigit()]
        return "".join(f"{n}{u}" for n, u in zip(nums, ("年", "月", "日")))
    if name in ("分数", "frac", "sfrac"):
        return "/".join(a.strip() for a in args[:2])
    if name in ("lang",):
        return args[1] if len(args) >= 2 else ""
    if name in ("ruby", "読み仮名", "読み仮名 ruby不使用", "nihongo", "small", "smaller", "big", "nowrap"):
        return args[0] if args else ""
    return ""


def strip_templates(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text.startswith("{{", i):
            end = _find_close(text, i, "{{", "}}")
            if end == -1:
                break
            inner = text[i + 2:end - 2]
            name = inner.split("|", 1)[0].strip().lower()
            if name in _KEEP_INNER:
                out.append(strip_templates(_render_template(inner)))
            i = end
        else:
            out.append(text[i]); i += 1
    return "".join(out)


def strip_tables(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text.startswith("{|", i):
            end = _find_close(text, i, "{|", "|}")
            if end == -1:
                break
            i = end
        else:
            out.append(text[i]); i += 1
    return "".join(out)


_FILE_LINK = re.compile(r"^\[\[\s*(file|image|ファイル|画像|category|カテゴリ)\s*:", re.I)


def strip_links(text: str) -> str:
    out, i = [], 0
    while i < len(text):
        if text.startswith("[[", i):
            end = _find_close(text, i, "[[", "]]")
            if end == -1:
                out.append(text[i:]); break
            link = text[i:end]
            if not _FILE_LINK.match(link):
                inner = strip_links(link[2:-2])
                out.append(inner.split("|")[-1])
            i = end
        else:
            out.append(text[i]); i += 1
    s = "".join(out)
    s = re.sub(r"\[https?://\S+\s+([^\]]+)\]", r"\1", s)   # [URL ラベル]
    s = re.sub(r"\[https?://\S+\]", "", s)
    return s


def clean_inline(text: str) -> str:
    s = re.sub(r"<!--.*?-->", "", text, flags=re.S)
    s = re.sub(r"<ref[^>]*/>", "", s)
    s = re.sub(r"<ref[^>]*>.*?</ref>", "", s, flags=re.S)
    s = re.sub(r"<references[^>]*/?>", "", s)
    s = re.sub(r"<br\s*/?>", "、", s)
    s = strip_templates(s)
    s = strip_tables(s)
    s = strip_links(s)
    s = re.sub(r"<[^>]+>", "", s)            # 残りのHTMLタグ（中身は残す）
    s = s.replace("'''", "").replace("''", "")
    s = re.sub(r"__[A-Z]+__", "", s)          # __NOTOC__ 等
    return s


INFOBOX_KEEP = [
    ("Released", "発売日"), ("Recorded", "録音"), ("Format", "規格"), ("Genre", "ジャンル"),
    ("Length", "時間"), ("Label", "レーベル"), ("Lyricist", "作詞"), ("Composer", "作曲"),
    ("Writer", "作詞・作曲"), ("Arranger", "編曲"), ("Producer", "プロデュース"),
    ("Album", "収録アルバム"), ("B-side", "カップリング"),
    ("Chart position", "チャート最高順位"), ("Certification", "認定"),
    ("Last single", "前作"), ("Next single", "次作"),
    ("Last album", "前作"), ("Next album", "次作"),
]


def extract_infobox(wikitext: str) -> tuple[dict, str]:
    """最初の {{Infobox ...}} を取り出して (パラメータ辞書, 残りの本文) を返す"""
    m = re.search(r"\{\{\s*Infobox", wikitext, flags=re.I)
    if not m:
        return {}, wikitext
    end = _find_close(wikitext, m.start(), "{{", "}}")
    if end == -1:
        return {}, wikitext
    inner = wikitext[m.start() + 2:end - 2]
    params: dict[str, str] = {}
    for part in _split_params(inner)[1:]:
        if "=" not in part:
            continue
        k, v = part.split("=", 1)
        params[k.strip()] = v.strip()
    return params, wikitext[:m.start()] + wikitext[end:]


_DATE_FULL  = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月\s*(\d{1,2})\s*日")
_DATE_MONTH = re.compile(r"(\d{4})\s*年\s*(\d{1,2})\s*月")
_DATE_YEAR  = re.compile(r"(\d{4})\s*年")


def first_release_date(infobox: dict) -> str | None:
    """Infobox の Released の最初の日付を 'YYYY-MM-DD' / 'YYYY-MM' / 'YYYY' で返す"""
    raw = infobox.get("Released") or infobox.get("発売日") or infobox.get("リリース") or ""
    raw = unicodedata.normalize("NFKC", clean_inline(raw))
    hits = []
    for rx, fmt in ((_DATE_FULL, 3), (_DATE_MONTH, 2), (_DATE_YEAR, 1)):
        m = rx.search(raw)
        if m:
            hits.append((m.start(), fmt, m))
    if not hits:
        return None
    # いちばん先頭に出てくる日付（同位置なら詳しい方）
    _, fmt, m = sorted(hits, key=lambda h: (h[0], -h[1]))[0]
    g = m.groups()
    if fmt == 3:
        return f"{g[0]}-{int(g[1]):02d}-{int(g[2]):02d}"
    if fmt == 2:
        return f"{g[0]}-{int(g[1]):02d}"
    return g[0]


def date_matches(wiki_date: str | None, db_date: str) -> bool:
    """同じ年ならOK（配信日と原盤の日付が数日〜数か月ずれることがあるため）"""
    return bool(wiki_date) and wiki_date[:4] == db_date[:4]


SKIP_SECTIONS = re.compile(
    r"(収録曲|収録内容|曲目|トラック|参加ミュージシャン|参加メンバー|クレジット|スタッフ|脚注|注釈|出典|"
    r"参考文献|関連項目|外部リンク|収録作品|収録アルバム|映像|発売日|リリース日|リリース履歴|作品|演奏者|パーソネル|規格|フォーマット)"
)


def build_source_text(wikitext: str, limit: int = 4000) -> tuple[str, str | None]:
    """執筆用の出典テキスト（Infoboxの主要項目＋冒頭＋主要な節）と、Infoboxの最初の発売日を返す"""
    infobox, body = extract_infobox(wikitext)
    release = first_release_date(infobox)

    ib_lines = []
    for k, label in INFOBOX_KEEP:
        if k in infobox:
            v = clean_inline(infobox[k])
            v = re.sub(r"\s*\n\s*\*?\s*", "、", v).strip("、 \n*")
            v = re.sub(r"、\s*\*+\s*", "、", v)
            v = re.sub(r"、{2,}", "、", v)
            if v:
                ib_lines.append(f"{label}: {v}")

    body = clean_inline(body)
    sections: list[tuple[str, str]] = []
    cur_title, buf = "冒頭", []
    for line in body.split("\n"):
        m = re.match(r"^(=+)\s*(.+?)\s*\1\s*$", line)
        if m:
            sections.append((cur_title, "\n".join(buf)))
            cur_title, buf = m.group(2), []
        else:
            buf.append(line)
    sections.append((cur_title, "\n".join(buf)))

    parts = ["[基本情報]\n" + "\n".join(ib_lines)] if ib_lines else []
    for title, text in sections:
        if title != "冒頭" and SKIP_SECTIONS.search(title):
            continue
        t = re.sub(r"\n{2,}", "\n", text).strip()
        t = "\n".join(l for l in t.split("\n") if l.strip() and not l.strip().startswith("|"))
        if len(t) < 10:
            continue
        parts.append(f"[{title}]\n{t}")

    out = "\n\n".join(parts)
    if len(out) > limit:
        out = out[:limit].rsplit("\n", 1)[0] + "\n（以下略）"
    return out, release
