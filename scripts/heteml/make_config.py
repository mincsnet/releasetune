"""
ヘテムルのサーバー用設定ファイル（heteml/config.php）を作ってサーバーに置く
=======================================================================

.env の値（API トークン、Spotify・YouTube のキー、CRON_SECRET）と、ここで入力する DB の接続情報から
config.php を作り、SSH でサーバーに直接書き込む（手元にファイルは残さない。パスワードは画面に出さない）。

  python3 scripts/heteml/make_config.py --ssh heteml --remote releasetune/heteml/config.php \
      --db-host mysqlXXX.heteml.jp --db-name _releasetune --db-user _releasetune

--remote はサーバーのホームからの相対パスで書く（「~/」で始めると手元の Mac のホームに展開されてしまう）。
DB のパスワードは実行中に聞かれるので入力する。
"""

import getpass, os, subprocess, sys
from argparse import ArgumentParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_env() -> dict:
    env = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.strip().startswith("#"):
            k, v = line.split("=", 1)
            env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def php_str(s: str) -> str:
    return "'" + s.replace("\\", "\\\\").replace("'", "\\'") + "'"


def main() -> None:
    ap = ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--ssh", required=True, help="SSH の接続先（~/.ssh/config の Host 名）")
    ap.add_argument("--remote", required=True, help="サーバー上の config.php のパス")
    ap.add_argument("--db-host", required=True)
    ap.add_argument("--db-name", required=True)
    ap.add_argument("--db-user", required=True)
    ap.add_argument("--revalidate-url", default="https://www.releasetune.com/api/revalidate",
                    help="データ更新後に呼ぶ Vercel のキャッシュ削除（第2段階で空にする）")
    # ヘテムルには「php」コマンドがなく、バージョン付きで呼ぶ。Web（Apache）と同じ 8.3 に揃える
    ap.add_argument("--php", default="/usr/local/bin/php8.3", help="サーバー上の PHP")
    args = ap.parse_args()

    env = load_env()
    required = ["HETEML_DB_TOKEN", "HETEML_READ_TOKEN", "SPOTIFY_CLIENT_ID", "SPOTIFY_CLIENT_SECRET", "YOUTUBE_API_KEY", "CRON_SECRET"]
    missing = [k for k in required if not env.get(k)]
    if missing:
        sys.exit(f".env にありません: {', '.join(missing)}")

    password = getpass.getpass(f"MySQL のパスワード（{args.db_user}）: ")
    config = f"""<?php
// サーバー用の設定（scripts/heteml/make_config.py が作成。git 管理外）
return [
    'db' => [
        'host' => {php_str(args.db_host)},
        'name' => {php_str(args.db_name)},
        'user' => {php_str(args.db_user)},
        'pass' => {php_str(password)},
    ],
    'db_api_token'   => {php_str(env['HETEML_DB_TOKEN'])},
    'read_api_token' => {php_str(env['HETEML_READ_TOKEN'])},
    'spotify_client_id'     => {php_str(env['SPOTIFY_CLIENT_ID'])},
    'spotify_client_secret' => {php_str(env['SPOTIFY_CLIENT_SECRET'])},
    'youtube_api_key'       => {php_str(env['YOUTUBE_API_KEY'])},
    'revalidate_url' => {php_str(args.revalidate_url)},
    'cron_secret'    => {php_str(env['CRON_SECRET'])},
    'log_dir' => __DIR__ . '/logs',
];
"""
    # 標準入力で渡してサーバー側で書き込む（所有者だけが読める権限にする）
    remote = args.remote.replace("'", "'\\''")
    subprocess.run(["ssh", args.ssh, f"umask 077 && cat > '{remote}' && {args.php} -r 'require \"{remote}\";' && echo 'config.php を置きました'"],
                   input=config.encode(), check=True)
    # 接続できるか確かめる
    subprocess.run(["ssh", args.ssh, f"{args.php} -r '$c = (require \"{remote}\")[\"db\"]; new PDO(\"mysql:host={{$c[\"host\"]}};dbname={{$c[\"name\"]}};charset=utf8mb4\", $c[\"user\"], $c[\"pass\"]); echo \"MySQL に接続できました\\n\";'"],
                   check=True)


if __name__ == "__main__":
    main()
