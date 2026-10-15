#!/bin/bash
# heteml/ をヘテムルの ~/releasetune/heteml/ に反映する（rsync）。
# サーバー上だけにあるもの（config.php・logs/・cache/）は送らず、消しもしない。
# ヘテムルの git は 1.8 と古いので、git pull ではなく手元から rsync で送る。
#   scripts/heteml/deploy.sh          反映
#   scripts/heteml/deploy.sh --dry-run 送る内容の確認だけ
set -eu
cd "$(dirname "$0")/../.."
if [ -n "$(git status --porcelain -- heteml/)" ]; then
  echo "⚠ heteml/ にコミットしていない変更があります（そのまま反映します）:"
  git status --short -- heteml/ | sed 's/^/   /'
fi
opts=(-az --delete --exclude config.php --exclude logs/ --exclude cache/ --exclude .DS_Store -e "ssh -o BatchMode=yes")
[ "${1:-}" = "--dry-run" ] && opts+=(--dry-run --itemize-changes)
# ヘテムルの SSH はまれにホームが見えない状態でつながるので、失敗したら数回つなぎ直す（remote.sh と同じ）
for i in 1 2 3; do
  if rsync "${opts[@]}" heteml/ heteml:releasetune/heteml/; then break; fi
  [ "$i" = 3 ] && { echo "rsync に失敗しました"; exit 1; }
  echo "（rsync に失敗したので、つなぎ直します $i/3）"; sleep 2
done
[ "${1:-}" = "--dry-run" ] && exit 0
# cron の実行ファイルは 700（ヘテムルの cron の指定）、設定ファイルは 600
"$(dirname "$0")/remote.sh" 'chmod 700 ~/releasetune/heteml/cron/*.php && chmod 600 ~/releasetune/heteml/config.php && echo "反映しました"'
