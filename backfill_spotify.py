"""
backfill_spotify.py
====================
Supabaseの `tracks` テーブルを直接対象に、Spotify直リンクを一括バックフィルする。
ロジックは `app/api/cron/new-releases/route.ts` の searchSpotify と同一。

対象: spotify カラムが NULL、または `open.spotify.com/track/` 形式でない行
（= 検索URLのまま、または未設定の行）

id昇順にカーソル方式でページングするため、中断しても --state-file に保存された
カーソルから再開できる（重複処理を避けつつ、全件を確実に一巡する）。

使い方:
    # まず少件数でドライラン（Supabaseへの書き込みなし）
    python3 backfill_spotify.py --dry-run --limit 20

    # 本実行（デフォルトで500件処理して終了。続きは再実行で自動的に続きから）
    python3 backfill_spotify.py

    # 件数を指定して実行
    python3 backfill_spotify.py --limit 5000

    # 最初からやり直す（カーソルをリセット）
    python3 backfill_spotify.py --reset
"""

import os, sys, time, unicodedata, base64, signal
from pathlib import Path
from argparse import ArgumentParser

import requests
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent / ".env")

SUPABASE_URL = os.getenv("NEXT_PUBLIC_SUPABASE_URL", "")
SERVICE_KEY  = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
SPOTIFY_ID     = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

STATE_FILE_DEFAULT = Path("spotify_backfill_cursor.txt")
PAGE_SIZE = 200
PENDING_FILTER = "(spotify.is.null,spotify.not.like.*open.spotify.com/track/*)"


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
def supabase_headers():
    return {
        "apikey":        SERVICE_KEY,
        "Authorization": f"Bearer {SERVICE_KEY}",
        "Content-Type":  "application/json",
    }


def fetch_pending_page(cursor: str, page_size: int) -> list[dict]:
    params = {
        "select": "id,title,artist",
        "order":  "id.asc",
        "limit":  str(page_size),
        "or":     PENDING_FILTER,
    }
    if cursor:
        params["id"] = f"gt.{cursor}"
    resp = http_request(
        "get",
        f"{SUPABASE_URL}/rest/v1/tracks",
        headers=supabase_headers(),
        params=params,
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()


def update_spotify(track_id: str, url: str) -> bool:
    resp = http_request(
        "patch",
        f"{SUPABASE_URL}/rest/v1/tracks",
        headers=supabase_headers(),
        params={"id": f"eq.{track_id}"},
        json={"spotify": url},
        timeout=30,
    )
    return resp.status_code in (200, 204)


# ── Spotify ───────────────────────────────────────────────────────
_token_cache = {"token": None, "expires_at": 0}


def get_spotify_token() -> str | None:
    if _token_cache["token"] and _token_cache["expires_at"] > time.time():
        return _token_cache["token"]

    basic = base64.b64encode(f"{SPOTIFY_ID}:{SPOTIFY_SECRET}".encode()).decode()
    resp = http_request(
        "post",
        "https://accounts.spotify.com/api/token",
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "Authorization": f"Basic {basic}",
        },
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    if not resp.ok:
        print(f"❌ Spotifyトークン取得失敗: {resp.status_code} {resp.text[:200]}")
        return None
    data = resp.json()
    _token_cache["token"] = data["access_token"]
    _token_cache["expires_at"] = time.time() + data["expires_in"] - 60
    return _token_cache["token"]


def normalize(s: str) -> str:
    return unicodedata.normalize("NFKC", s or "").lower().strip()


def artist_match(sp_artists: list[dict], query_artist: str) -> bool:
    q = normalize(query_artist)
    for a in sp_artists:
        n = normalize(a.get("name", ""))
        if n and (q in n or n in q):
            return True
    return False


MAX_RETRY_AFTER = 60  # これを超えるRetry-Afterはアプリ単位のクォータ超過とみなし即座に中断する


class QuotaExceeded(Exception):
    def __init__(self, retry_after: int):
        self.retry_after = retry_after
        super().__init__(f"Spotify quota exceeded, retry after {retry_after}s")


def spotify_search_request(token: str, query: str, sleep_s: float) -> list[dict] | None:
    """1回分の検索リクエスト。短時間の429は待機してリトライ。長時間ブロックはQuotaExceededで即中断。"""
    for attempt in range(2):
        try:
            resp = http_request(
                "get",
                "https://api.spotify.com/v1/search",
                headers={"Authorization": f"Bearer {token}"},
                params={"q": query, "type": "track", "market": "JP", "limit": "10"},
                timeout=30,
            )
        except requests.RequestException as e:
            print(f"    [Spotify] リクエスト例外（リトライ済み）: {e}")
            return None

        if resp.status_code == 429:
            retry_after = int(resp.headers.get("Retry-After", "5"))
            if retry_after > MAX_RETRY_AFTER:
                raise QuotaExceeded(retry_after)
            print(f"    [Spotify] 429 レート制限。{retry_after}秒待機...")
            time.sleep(retry_after + 1)
            continue
        if not resp.ok:
            return None
        time.sleep(sleep_s)
        return resp.json().get("tracks", {}).get("items", [])
    return None


def search_spotify(token: str, title: str, artist: str, sleep_s: float) -> str | None:
    """cron route.ts の searchSpotify と同一ロジック（最初にヒットしたクエリで確定）。"""
    queries = [
        f'track:"{title}" artist:"{artist}"',
        f"track:{title} artist:{artist}",
        f"{artist} {title}",
    ]

    for query in queries:
        items = spotify_search_request(token, query, sleep_s)
        if items is None:
            continue
        if not items:
            continue

        title_norm = normalize(title)
        for item in items:
            sp_title = normalize(item.get("name", ""))
            sp_url = (item.get("external_urls") or {}).get("spotify")
            if sp_url and (title_norm in sp_title or sp_title in title_norm) and artist_match(item.get("artists") or [], artist):
                return sp_url

        first_url = (items[0].get("external_urls") or {}).get("spotify")
        if first_url:
            return first_url

    return None


# ── メイン ───────────────────────────────────────────────────────
def load_cursor(state_file: Path) -> str:
    if state_file.exists():
        return state_file.read_text().strip()
    return ""


def save_cursor(state_file: Path, cursor: str):
    state_file.write_text(cursor)


def main():
    parser = ArgumentParser(description="Supabase tracksテーブルにSpotify直リンクを一括バックフィル")
    parser.add_argument("--dry-run", action="store_true", help="Supabaseへの書き込みを行わず結果だけ表示")
    parser.add_argument("--limit", type=int, default=500, help="この実行で処理する最大トラック数（0=無制限）")
    parser.add_argument("--sleep", type=float, default=0.12, help="Spotify検索リクエスト間のスリープ秒数")
    parser.add_argument("--state-file", default=str(STATE_FILE_DEFAULT), help="カーソル保存ファイル")
    parser.add_argument("--reset", action="store_true", help="カーソルをリセットして最初から処理する")
    args = parser.parse_args()

    if not SUPABASE_URL or not SERVICE_KEY:
        print("❌ NEXT_PUBLIC_SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY が未設定です")
        sys.exit(1)
    if not SPOTIFY_ID or not SPOTIFY_SECRET:
        print("❌ SPOTIFY_CLIENT_ID / SPOTIFY_CLIENT_SECRET が未設定です")
        sys.exit(1)

    state_file = Path(args.state_file)
    if args.reset and state_file.exists():
        state_file.unlink()
        print("🔄 カーソルをリセットしました")

    token = get_spotify_token()
    if not token:
        sys.exit(1)
    print("✅ Spotify認証成功")

    cursor = load_cursor(state_file)
    if cursor:
        print(f"▶️  カーソルから再開: id > {cursor}")
    else:
        print("▶️  最初から処理します")

    processed = 0
    updated   = 0
    not_found = 0
    last_id   = cursor

    def flush_and_exit(*_):
        if not args.dry_run and last_id:
            save_cursor(state_file, last_id)
        print(f"\n⏹ 中断: 処理={processed} 更新={updated} 未ヒット={not_found}")
        sys.exit(0)

    signal.signal(signal.SIGINT, flush_and_exit)

    quota_exceeded: QuotaExceeded | None = None

    try:
        while True:
            if args.limit and processed >= args.limit:
                break

            page_size = PAGE_SIZE
            if args.limit:
                page_size = min(PAGE_SIZE, args.limit - processed)
            page = fetch_pending_page(last_id, page_size)
            if not page:
                print("\n✨ 対象がなくなりました（全件処理完了）")
                if not args.dry_run:
                    save_cursor(state_file, last_id)
                break

            for track in page:
                if args.limit and processed >= args.limit:
                    break

                track_id = track["id"]
                title    = track.get("title", "")
                artist   = track.get("artist", "")

                try:
                    token = get_spotify_token()  # 期限切れなら自動更新
                    url = search_spotify(token, title, artist, args.sleep)

                    if url:
                        updated += 1
                        tag = "✅"
                        if not args.dry_run:
                            ok = update_spotify(track_id, url)
                            if not ok:
                                tag = "❌(DB更新失敗)"
                        print(f"  {tag} [{track_id}] {artist} 「{title[:40]}」 → {url}")
                    else:
                        not_found += 1
                        print(f"  ⚠️  [{track_id}] {artist} 「{title[:40]}」 → 見つからず")
                except QuotaExceeded as e:
                    # このトラックは処理未完了のまま中断（processed/last_idを進めない → 次回再試行される）
                    quota_exceeded = e
                    break
                except Exception as e:
                    not_found += 1
                    print(f"  ❌ [{track_id}] {artist} 「{title[:40]}」 → 予期しないエラーのためスキップ: {e}")

                processed += 1
                last_id = track_id

                if processed % 50 == 0:
                    if not args.dry_run:
                        save_cursor(state_file, last_id)
                    print(f"  --- 進捗: {processed}件処理 / 直リンク取得{updated} / 未ヒット{not_found} ---")

            if quota_exceeded:
                break

    finally:
        if not args.dry_run and last_id:
            save_cursor(state_file, last_id)

    if quota_exceeded:
        resume_at = time.strftime("%H:%M", time.localtime(time.time() + quota_exceeded.retry_after))
        print(f"""
🛑 Spotify APIのクォータ超過（QUOTA_EXCEEDED）で中断しました。
   Retry-After: {quota_exceeded.retry_after}秒（約{quota_exceeded.retry_after / 3600:.1f}時間）
   {resume_at}頃以降に同じコマンドを再実行してください（カーソルはこのトラックの手前で保存済み）。
""")
        sys.exit(2)

    print(f"""
━━━━━━━━━━━━━━━━━━━━━━━━━━━
📊 バックフィル結果
━━━━━━━━━━━━━━━━━━━━━━━━━━━
処理件数     : {processed:,}
直リンク取得 : {updated:,}
未ヒット     : {not_found:,}
━━━━━━━━━━━━━━━━━━━━━━━━━━━
{"※ ドライランのためSupabaseへの書き込みは行っていません" if args.dry_run else f"次回はカーソル(id > {last_id})から再開します"}
    """)


if __name__ == "__main__":
    main()
