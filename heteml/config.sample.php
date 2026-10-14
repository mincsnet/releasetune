<?php
// 設定の見本。本物は同じフォルダの config.php（git 管理外。リポジトリは公開なので秘密情報を置かない）。
// サーバー用の config.php は scripts/heteml/make_config.py で .env から作る。

return [
    // ヘテムルのコントロールパネルで作った MySQL（外部からは接続できない）
    'db' => [
        'host' => 'localhost',
        'name' => 'releasetune',
        'user' => 'root',
        'pass' => '',
    ],

    // 手元のスクリプトが api/db.php を使うときのトークン（読み書きできる。.env の HETEML_DB_TOKEN と同じ値）
    'db_api_token' => '',
    // 第1段階の間、Vercel のサイトが api/tracks.php を読むときのトークン（読み取りのみ。.env の HETEML_READ_TOKEN）
    'read_api_token' => '',

    // cron（新着取得・Spotify補完）で使う外部 API
    'spotify_client_id'     => '',
    'spotify_client_secret' => '',
    'youtube_api_key'       => '',

    // データを書き換えた後に呼ぶ、Vercel のキャッシュ削除（/api/revalidate）。第2段階で空にする
    'revalidate_url' => 'https://www.releasetune.com/api/revalidate',
    'cron_secret'    => '',

    // cron のログの置き場所（公開フォルダの外）
    'log_dir' => __DIR__ . '/logs',
];
