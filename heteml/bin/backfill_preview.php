<?php
// 既存の作品の試聴（apple_track_id・preview_url）を iTunes Lookup API（entity=song）で埋める（新着は cron/new_releases.php が入れる）。
// preview_url が空の作品を id 順に LOOKUP_BATCH 件ずつ Lookup に渡し、収録曲から試聴に使う曲を選んで入れる（src/itunes.php の itunes_preview_song）。
// 見つからない作品（配信が終わったものなど）は空のまま残す（サイトは試聴ボタンを出さない）。
// 途中で止まっても、もう一度実行すれば続きから処理する。bin/backfill_track_count.php と同じ作り。
//
//   php8.3 heteml/bin/backfill_preview.php                       本実行
//   php8.3 heteml/bin/backfill_preview.php --dry-run --limit=200 200件だけ Lookup して結果を表示する（DB に書かない）

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';
require_once __DIR__ . '/../src/itunes.php';

const LOOKUP_BATCH = 100; // 収録曲も返るので1回が重い（200作品で約17秒・約5MB）。タイムアウト（60秒）に余裕を持たせる
const SLEEP_SEC = 3;      // 呼び出しの間隔（Apple の目安は1分あたり約20回まで）

cron_main('backfill_preview', function (array $args): array {
    $dryRun = in_array('--dry-run', $args, true);
    $limit = PHP_INT_MAX;
    foreach ($args as $a) {
        if (preg_match('/^--limit=(\d+)$/', $a, $m)) {
            $limit = max(1, (int) $m[1]);
        }
    }

    $pdo = db();
    $select = $pdo->prepare('SELECT id, title, artist, apple FROM tracks WHERE preview_url IS NULL AND id > ? ORDER BY id LIMIT ?');
    // cron が入れた値は上書きしない
    $update = $pdo->prepare('UPDATE tracks SET apple_track_id = ?, preview_url = ? WHERE id = ? AND preview_url IS NULL');

    $lastId = '';
    $scanned = $updated = $notFound = $titleMatched = $calls = 0;
    $found = $notFoundSample = [];
    $stopped = null;

    while ($scanned < $limit) {
        $select->execute([$lastId, min(LOOKUP_BATCH, $limit - $scanned)]);
        $rows = $select->fetchAll();
        if (!$rows) {
            break;
        }
        $lastId = end($rows)['id'];
        $albumIds = array_combine(array_column($rows, 'id'), array_map('itunes_album_id', $rows));

        if ($calls > 0) {
            sleep(SLEEP_SEC);
        }
        $songs = itunes_lookup_songs($albumIds);
        $calls++;
        if ($songs === null) {
            $stopped = 'Stopped: Lookup failed. Run again to continue';
            break;
        }

        if (!$dryRun) {
            $pdo->beginTransaction();
        }
        foreach ($rows as $r) {
            $scanned++;
            $list = $songs[$albumIds[$r['id']]] ?? [];
            $song = itunes_preview_song($list, $r['title']);
            if ($song === null) {
                $notFound++;
                if (count($notFoundSample) < 5) {
                    $notFoundSample[] = "{$r['id']} | {$r['artist']} | {$r['title']}";
                }
                continue;
            }
            // 1曲目以外を選んだ数（曲名が作品名と一致した）。1曲目が一致した場合は数えない
            $first = $list ? min(array_map(fn($s) => [$s['discNumber'] ?? 1, $s['trackNumber'] ?? 0], $list)) : null;
            if ([$song['discNumber'] ?? 1, $song['trackNumber'] ?? 0] !== $first) {
                $titleMatched++;
            }
            if ($dryRun) {
                if (count($found) < 10) {
                    $found[] = "{$r['artist']} | {$r['title']} → {$song['trackNumber']}. {$song['trackName']}";
                }
                $updated++;
            } else {
                $update->execute([$song['trackId'], $song['previewUrl'], $r['id']]);
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
        'notFirstTrack'  => $titleMatched,
        'calls'          => $calls,
        'remaining'      => (int) $pdo->query('SELECT COUNT(*) FROM tracks WHERE preview_url IS NULL')->fetchColumn(),
        'found'          => $dryRun ? $found : null,
        'notFoundSample' => $notFoundSample,
    ];
});
