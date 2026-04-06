"""
cleanup.py — 誤ってマッチしたアーティストのデータを削除する
"""
import json
from pathlib import Path

DATA_FILE = Path("data/tracks.json")

# 削除対象のアーティスト名（誤マッチしたもの）
REMOVE_ARTISTS = {
    "Omoinotake",       # Mrs.GREEN APPLEの代わりに取得
    "Fukase",           # Vaundyの代わりに取得
    "Kazutoshi Sakurai", # ちゃんみなの代わりに取得
    "歌っちゃ王",        # ちゃんみな誤取得に関連
    "livetune adding Fukase (from SEKAI NO OWARI)",
    "JEONGHAN",         # Omoinotakeのフィーチャリング
}

with open(DATA_FILE, encoding="utf-8") as f:
    db = json.load(f)

total_before = sum(len(v) for v in db.values())
removed = 0

for mmdd in list(db.keys()):
    before = len(db[mmdd])
    db[mmdd] = [
        t for t in db[mmdd]
        if t.get("artist", "") not in REMOVE_ARTISTS
    ]
    removed += before - len(db[mmdd])
    # 空になったキーは削除
    if not db[mmdd]:
        del db[mmdd]

with open(DATA_FILE, "w", encoding="utf-8") as f:
    json.dump(db, f, ensure_ascii=False, indent=2)

total_after = sum(len(v) for v in db.values())
print(f"削除前: {total_before} 件 / {len(db)+len([k for k in db])} 日分")
print(f"削除数: {removed} 件")
print(f"削除後: {total_after} 件 / {len(db)} 日分")