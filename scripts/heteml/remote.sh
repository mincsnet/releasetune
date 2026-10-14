#!/bin/bash
# ヘテムルで SSH のコマンドを実行する（例: scripts/heteml/remote.sh 'php8.3 -v'）。
# ヘテムルの SSH は、まれに PHP とホームディレクトリが見えない状態でつながる（2026-10-14 に6回に1回ほど発生）。
# その場合はつなぎ直す。ssh の接続先は ~/.ssh/config の Host heteml。
set -u
for i in 1 2 3 4 5; do
  ssh -o BatchMode=yes heteml "test -x /usr/local/bin/php8.3 && test -d ~/releasetune || exit 99; $*"
  code=$?
  [ "$code" -ne 99 ] && exit "$code"
  echo "（ヘテムルの SSH が PHP とホームを見られない状態でつながったので、つなぎ直します $i/5）" >&2
  sleep 2
done
exit 99
