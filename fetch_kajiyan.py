"""
fetch_kajiyan.py — kajiyan-net の年間チャートからアーティスト名を抽出
Shift-JIS でエンコードされているため requests で直接取得して処理する
"""
import csv, re, time
from pathlib import Path
import requests
from html.parser import HTMLParser

YEARS = list(range(1980, 2008))  # 1980〜2007
BASE_URL = "https://www.kajiyan-net.jp/nenkan/{year}nenkan.htm"
OUT_FILE = Path("kajiyan_artists.csv")
SLEEP    = 1.0

class TableParser(HTMLParser):
    """HTMLテーブルからアーティスト列（3列目）を抽出"""
    def __init__(self):
        super().__init__()
        self.in_td   = False
        self.td_count = 0
        self.col_idx  = 0  # 現在のカラム位置
        self.artists  = []
        self.current  = ""
        self.in_row   = False

    def handle_starttag(self, tag, attrs):
        if tag == "tr":
            self.in_row  = True
            self.col_idx = 0
        elif tag == "td" and self.in_row:
            self.in_td   = True
            self.current = ""

    def handle_endtag(self, tag):
        if tag == "td" and self.in_row:
            self.in_td = False
            self.col_idx += 1
            # 3列目（0-indexed: 2）がアーティスト列
            if self.col_idx == 3:
                text = self.current.strip()
                # ヘッダー行やNoデータを除外
                if text and text not in ("アーティスト", "歌手名"):
                    self.artists.append(text)
            self.current = ""
        elif tag == "tr":
            self.in_row = False

    def handle_data(self, data):
        if self.in_td:
            self.current += data


def fetch_artists(year: int) -> list[str]:
    url = BASE_URL.format(year=year)
    try:
        resp = requests.get(url, timeout=15)
        resp.encoding = "shift_jis"
        html = resp.text
        time.sleep(SLEEP)
    except Exception as e:
        print(f"  [{year}] 取得失敗: {e}")
        return []

    parser = TableParser()
    parser.feed(html)
    artists = parser.artists

    # 不要なノイズを除去
    cleaned = []
    for a in artists:
        # 数字のみ、空欄、ポイント数などは除外
        a = a.strip()
        if not a:
            continue
        if re.match(r"^[\d,，．.]+$", a):
            continue
        if a in ("タイトル", "トータルポイント", "最高位", "順位"):
            continue
        cleaned.append(a)

    print(f"  [{year}] {len(cleaned)} 件取得")
    return cleaned


def main():
    all_artists = {}  # name -> 初出年

    for year in YEARS:
        print(f"\n{year}年...")
        artists = fetch_artists(year)
        for a in artists:
            if a not in all_artists:
                all_artists[a] = year

    # 重複排除・コラボ系除外
    skip_keywords = [
        "feat.", "feat ", " & ", "×", " x ", "featuring",
        "with ", "ｗｉｔｈ", "ＷＩＴＨと", "他", "Various",
    ]
    final = []
    seen  = set()
    for name, year in sorted(all_artists.items(), key=lambda x: x[1]):
        if any(k.lower() in name.lower() for k in skip_keywords):
            continue
        if name in seen:
            continue
        seen.add(name)
        final.append(name)

    with open(OUT_FILE, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["artist"])
        for name in final:
            w.writerow([name])

    print(f"\n✅ 完了: {len(final)} アーティスト → {OUT_FILE}")


if __name__ == "__main__":
    main()