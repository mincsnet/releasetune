<?php
// すべての PHP（公開ページ・API・cron・コマンド）の最初に読み込む

declare(strict_types=1);

date_default_timezone_set('Asia/Tokyo');
mb_internal_encoding('UTF-8');

require_once __DIR__ . '/db.php';
require_once __DIR__ . '/schema.php';

// 設定（heteml/config.php）。テストなどで別の設定を使うときは環境変数 RELEASETUNE_CONFIG にパスを入れる
function config(string $key)
{
    static $config = null;
    if ($config === null) {
        $path = getenv('RELEASETUNE_CONFIG') ?: __DIR__ . '/../config.php';
        if (!is_file($path)) {
            throw new RuntimeException("設定ファイルがありません: {$path}");
        }
        $config = require $path;
    }
    if (!array_key_exists($key, $config)) {
        throw new RuntimeException("設定に {$key} がありません");
    }
    return $config[$key];
}
