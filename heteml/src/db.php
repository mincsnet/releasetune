<?php
// MySQL への接続（1リクエスト・1プロセスにつき1つ）

function db(): PDO
{
    static $pdo = null;
    if ($pdo !== null) {
        return $pdo;
    }
    $c = config('db');
    $pdo = new PDO(
        "mysql:host={$c['host']};dbname={$c['name']};charset=utf8mb4",
        $c['user'],
        $c['pass'],
        [
            PDO::ATTR_ERRMODE            => PDO::ERRMODE_EXCEPTION,
            PDO::ATTR_DEFAULT_FETCH_MODE => PDO::FETCH_ASSOC,
            // 本物のプリペアドステートメントを使う（数値列が数値のまま返り、LIMIT にも値を渡せる）
            PDO::ATTR_EMULATE_PREPARES   => false,
        ]
    );
    // updated_at は UTC で保存・比較する
    $pdo->exec("SET time_zone = '+00:00'");
    return $pdo;
}
