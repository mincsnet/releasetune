<?php
// 既存の作品の収録曲数（track_count）を iTunes Lookup API で埋める（新着は cron/new_releases.php が入れる）。
// track_count が空の作品を id 順に200件ずつ Lookup に渡し、返ってきた作品の trackCount を入れる。
// 見つからない作品（配信が終わったものなど）は空のまま残す（サイトは曲名の末尾で種類を判定する）。
// 途中で止まっても、もう一度実行すれば続きから処理する。bin/backfill_genre.php と同じ作り。
//
//   php8.3 heteml/bin/backfill_track_count.php                       本実行
//   php8.3 heteml/bin/backfill_track_count.php --dry-run --limit=400 400件だけ Lookup して結果を表示する（DB に書かない）

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';
require_once __DIR__ . '/../src/itunes.php';

const SLEEP_SEC = 3; // 呼び出しの間隔（Apple の目安は1分あたり約20回まで）

cron_main('backfill_track_count', function (array $args): array {
    $dryRun = in_array('--dry-run', $args, true);
    $limit = PHP_INT_MAX;
    foreach ($args as $a) {
        if (preg_match('/^--limit=(\d+)$/', $a, $m)) {
            $limit = max(1, (int) $m[1]);
        }
    }

    $pdo = db();
    $select = $pdo->prepare('SELECT id, title, artist, apple FROM tracks WHERE track_count IS NULL AND id > ? ORDER BY id LIMIT ?');
    // cron が入れた値は上書きしない
    $update = $pdo->prepare('UPDATE tracks SET track_count = ? WHERE id = ? AND track_count IS NULL');

    $lastId = '';
    $scanned = $updated = $notFound = $calls = 0;
    $sizes = ['1' => 0, '2-3' => 0, '4-6' => 0, '7+' => 0];
    $found = $notFoundSample = [];
    $stopped = null;

    while ($scanned < $limit) {
        $select->execute([$lastId, min(ITUNES_LOOKUP_BATCH, $limit - $scanned)]);
        $rows = $select->fetchAll();
        if (!$rows) {
            break;
        }
        $lastId = end($rows)['id'];
        $albumIds = array_combine(array_column($rows, 'id'), array_map('itunes_album_id', $rows));

        if ($calls > 0) {
            sleep(SLEEP_SEC);
        }
        $collections = itunes_lookup_collections($albumIds);
        $calls++;
        if ($collections === null) {
            $stopped = 'Stopped: Lookup failed. Run again to continue';
            break;
        }

        if (!$dryRun) {
            $pdo->beginTransaction();
        }
        foreach ($rows as $r) {
            $scanned++;
            $count = $collections[$albumIds[$r['id']]]['trackCount'] ?? null;
            if (!is_int($count) || $count < 1) {
                $notFound++;
                if (count($notFoundSample) < 5) {
                    $notFoundSample[] = "{$r['id']} | {$r['artist']} | {$r['title']}";
                }
                continue;
            }
            $sizes[$count === 1 ? '1' : ($count <= 3 ? '2-3' : ($count <= 6 ? '4-6' : '7+'))]++;
            if ($dryRun) {
                if (count($found) < 10) {
                    $found[] = "{$r['artist']} | {$r['title']} → {$count}";
                }
                $updated++;
            } else {
                $update->execute([$count, $r['id']]);
                $updated += $update->rowCount();
            }
        }
        if (!$dryRun) {
            $pdo->commit();
        }
    }

    $message = $stopped ?? ($scanned >= $limit ? 'Stopped: --limit reached' : 'Batch complete');
    return [
        'message'        => $dryRun ? "Dry run (nothing written): {$message}" : $message,
        'scanned'        => $scanned,
        'updated'        => $updated,
        'notFound'       => $notFound,
        'calls'          => $calls,
        'remaining'      => (int) $pdo->query('SELECT COUNT(*) FROM tracks WHERE track_count IS NULL')->fetchColumn(),
        'sizes'          => $sizes,
        'found'          => $dryRun ? $found : null,
        'notFoundSample' => $notFoundSample,
    ];
});
