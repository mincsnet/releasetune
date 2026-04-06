"""
clean_duplicates.py — tracks.json の重複データをクリーニング
================================================================
同じ日付・同じアーティスト・同じ曲名（表記揺れを含む）の
重複エントリを1件に絞る。

優先順位:
  1. 日本語タイトル（ひらがな・カタカナ・漢字を含む）
  2. タイトルが短いもの（"- EP" "- Single" "(Special Edition)" などを除いた）
  3. より古いID（先に収集されたもの）

使い方:
  python3 clean_duplicates.py

出力: data/tracks.json を上書き（バックアップは data/tracks_backup.json）
"""

import json, re, unicodedata, shutil
from pathlib import Path
from collections import defaultdict

DATA_FILE   = Path("data/tracks.json")
BACKUP_FILE = Path("data/tracks_backup.json")

# タイトルから余分なサフィックスを除去して核心部分を取得
SUFFIX_PATTERNS = [
    r'\s*[-–]\s*EP$',
    r'\s*[-–]\s*Single$',
    r'\s*[-–]\s*Album$',
    r'\s*\(Special Edition\)$',
    r'\s*\(Complete Edition\)$',
    r'\s*\(TYPE[-–]?[A-Z]\)$',
    r'\s*\(Type[-–]?[A-Z]\)$',
    r'\s*\(通常盤\)$',
    r'\s*\(初回限定盤\)$',
    r'\s*\(初回盤\)$',
    r'\s*\(通常版\)$',
    r'\s*[-–]\s*From THE FIRST TAKE$',
    r'\s*[-–]\s*Remastered$',
    r'\s*[-–]\s*REMASTER$',
    r'\s*\s*Remaster$',
]

def strip_suffix(title: str) -> str:
    """タイトルからサフィックスを除去して核心部分を返す"""
    t = title.strip()
    for pat in SUFFIX_PATTERNS:
        t = re.sub(pat, '', t, flags=re.IGNORECASE).strip()
    return t

def normalize(s: str) -> str:
    """比較用に正規化（全角→半角、大文字→小文字、空白除去）"""
    s = unicodedata.normalize("NFKC", s)
    return s.lower().strip().replace('\u3000', ' ').replace('　', ' ')

def has_japanese(s: str) -> bool:
    """日本語文字（ひらがな・カタカナ・漢字）を含むか"""
    return bool(re.search(r'[\u3040-\u9FFF]', s))

def title_score(track: dict) -> tuple:
    """
    タイトルの優先スコアを返す（小さいほど優先）
    (日本語フラグ逆, サフィックス除去後の長さ)
    """
    title = track.get("title", "")
    core  = strip_suffix(title)
    japanese_bonus = 0 if has_japanese(title) else 1  # 日本語タイトルを優先
    return (japanese_bonus, len(core), len(title))


def clean():
    # バックアップ
    shutil.copy(DATA_FILE, BACKUP_FILE)
    print(f"バックアップ: {BACKUP_FILE}")

    with open(DATA_FILE, encoding="utf-8") as f:
        db = json.load(f)

    total_before = sum(len(v) for v in db.values())
    total_removed = 0

    new_db = {}
    for mmdd, tracks in db.items():
        # アーティスト + 正規化タイトル核心部でグループ化
        groups = defaultdict(list)
        for t in tracks:
            artist_key = normalize(t.get("artist", ""))
            title_key  = normalize(strip_suffix(t.get("title", "")))
            key = f"{artist_key}|||{title_key}"
            groups[key].append(t)

        cleaned = []
        for key, group in groups.items():
            if len(group) == 1:
                cleaned.append(group[0])
            else:
                # 最も優先度の高いものを選ぶ
                best = min(group, key=title_score)
                # リンクは最も情報が多いものをマージ
                for t in group:
                    for svc in ["spotify", "apple", "youtube", "amazon"]:
                        existing = best["links"].get(svc, "")
                        candidate = t["links"].get(svc, "")
                        # 検索URLより直接URLを優先
                        if candidate and (
                            not existing or
                            ("search" in existing and "search" not in candidate)
                        ):
                            best["links"][svc] = candidate
                cleaned.append(best)
                total_removed += len(group) - 1

        # リリース日でソート
        cleaned.sort(key=lambda x: x.get("releaseDate", ""))
        new_db[mmdd] = cleaned

    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(new_db, f, ensure_ascii=False, indent=2)

    total_after = sum(len(v) for v in new_db.values())
    print(f"\nクリーニング完了:")
    print(f"  処理前: {total_before:,} 件")
    print(f"  削除数: {total_removed:,} 件")
    print(f"  処理後: {total_after:,} 件")
    print(f"  ファイル: {DATA_FILE}")


if __name__ == "__main__":
    clean()
