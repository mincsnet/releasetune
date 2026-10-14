<?php
// Supabase から書き出したデータ（scripts/heteml/migrate_from_supabase.py export が作る JSON Lines）を MySQL に入れる。
// 両テーブルを空にしてから入れ直すので、何度実行しても同じ結果になる。途中で失敗したら何も変えない（1つのトランザクション）。
//
// 使い方: php heteml/bin/import_snapshot.php data/backup/supabase_YYYYMMDD-HHMMSS.jsonl

require_once __DIR__ . '/../src/bootstrap.php';

if (PHP_SAPI !== 'cli') {
    exit(1);
}
$path = $argv[1] ?? '';
if (!is_file($path)) {
    fwrite(STDERR, "使い方: php heteml/bin/import_snapshot.php <JSON Lines ファイル>\n");
    exit(1);
}

$pdo = db();

// テーブルがなければ作る（schema.sql の CREATE TABLE IF NOT EXISTS）
$schema = preg_replace('/^--.*$/m', '', file_get_contents(__DIR__ . '/../schema.sql'));
foreach (array_filter(array_map('trim', explode(';', $schema))) as $stmt) {
    $pdo->exec($stmt);
}

const BATCH = 500;
$buffers = array_fill_keys(array_keys(TABLES), []);
$counts = array_fill_keys(array_keys(TABLES), 0);

function flush_rows(PDO $pdo, string $table, array $rows): void
{
    if (!$rows) {
        return;
    }
    $cols = array_keys(TABLES[$table]['columns']);
    $placeholders = '(' . implode(', ', array_fill(0, count($cols), '?')) . ')';
    $sql = "INSERT INTO `{$table}` (" . implode(', ', array_map(fn($c) => "`{$c}`", $cols)) . ') VALUES '
        . implode(', ', array_fill(0, count($rows), $placeholders));
    $values = [];
    foreach ($rows as $row) {
        $extra = array_diff(array_keys($row), $cols);
        if ($extra) {
            throw new RuntimeException("{$table} に知らない列があります: " . implode(', ', $extra));
        }
        foreach ($cols as $col) {
            $values[] = encode_value(TABLES[$table]['columns'][$col], $row[$col] ?? null);
        }
    }
    $pdo->prepare($sql)->execute($values);
}

$pdo->beginTransaction();
try {
    foreach (array_keys(TABLES) as $table) {
        $pdo->exec("DELETE FROM `{$table}`");
    }
    $fh = fopen($path, 'r');
    $lineNo = 0;
    while (($line = fgets($fh)) !== false) {
        $lineNo++;
        if (trim($line) === '') {
            continue;
        }
        // JSON 列の {} が [] に化けないよう、オブジェクトのまま読む
        $item = json_decode($line, false, 512, JSON_THROW_ON_ERROR);
        $table = $item->t ?? '';
        if (!isset(TABLES[$table])) {
            throw new RuntimeException("{$lineNo}行目: 知らないテーブルです: {$table}");
        }
        $buffers[$table][] = get_object_vars($item->r);
        $counts[$table]++;
        if (count($buffers[$table]) >= BATCH) {
            flush_rows($pdo, $table, $buffers[$table]);
            $buffers[$table] = [];
        }
    }
    fclose($fh);
    foreach ($buffers as $table => $rows) {
        flush_rows($pdo, $table, $rows);
    }
    // 入れた件数とファイルの行数が一致することを確かめてから確定する
    foreach ($counts as $table => $n) {
        $inDb = (int) $pdo->query("SELECT COUNT(*) FROM `{$table}`")->fetchColumn();
        if ($inDb !== $n) {
            throw new RuntimeException("{$table}: ファイル {$n} 行に対して DB は {$inDb} 行です");
        }
    }
    $pdo->commit();
} catch (Throwable $e) {
    $pdo->rollBack();
    fwrite(STDERR, "失敗したので何も変更していません: {$e->getMessage()}\n");
    exit(1);
}

foreach ($counts as $table => $n) {
    echo "{$table}: {$n} 行\n";
}
