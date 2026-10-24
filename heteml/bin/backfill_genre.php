<?php
// 既存の曲のジャンル（genre）を iTunes Lookup API で埋める（新着は cron/new_releases.php が RSS のジャンルを入れる）。
// genre が空の曲を id 順に200件ずつ Lookup に渡し、返ってきたアルバムのジャンル名（primaryGenreName）を入れる。
// Lookup は曲の id ではなく Apple の URL のアルバム ID で引く（ほぼ同じだが、id が違う曲が1件ある。2026-10-24 調査）。
// 見つからない曲（配信が終わったアルバムなど、約1.5%）は空のまま残す。途中で止まっても、もう一度実行すれば続きから処理する。
//
//   php8.3 heteml/bin/backfill_genre.php                       本実行
//   php8.3 heteml/bin/backfill_genre.php --dry-run --limit=400 400曲だけ Lookup して結果を表示する（DB に書かない）

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';

const BATCH = 200;   // Lookup に1回で渡す件数（200件で約1秒・約200KB、2026-10-24 実測）
const SLEEP_SEC = 3; // 呼び出しの間隔（Apple の目安は1分あたり約20回まで）

cron_main('backfill_genre', function (array $args): array {
    $dryRun = in_array('--dry-run', $args, true);
    $limit = PHP_INT_MAX;
    foreach ($args as $a) {
        if (preg_match('/^--limit=(\d+)$/', $a, $m)) {
            $limit = max(1, (int) $m[1]);
        }
    }

    $pdo = db();
    $select = $pdo->prepare('SELECT id, title, artist, apple FROM tracks WHERE genre IS NULL AND id > ? ORDER BY id LIMIT ?');
    // cron が入れた値は上書きしない
    $update = $pdo->prepare('UPDATE tracks SET genre = ? WHERE id = ? AND genre IS NULL');

    $lastId = '';
    $scanned = $updated = $notFound = $calls = 0;
    $genres = $found = $notFoundSample = [];
    $stopped = null;

    while ($scanned < $limit) {
        $select->execute([$lastId, min(BATCH, $limit - $scanned)]);
        $rows = $select->fetchAll();
        if (!$rows) {
            break;
        }
        $lastId = end($rows)['id'];

        // Apple の URL（…/album/曲名/1526094901?i=…&uo=4）のアルバム ID。取れなければ id
        $albumIds = [];
        foreach ($rows as $r) {
            $albumIds[$r['id']] = preg_match('#/album/(?:[^/?]+/)?(\d+)#', (string) $r['apple'], $m) ? $m[1] : $r['id'];
        }

        if ($calls > 0) {
            sleep(SLEEP_SEC);
        }
        $res = http_request('GET', 'https://itunes.apple.com/lookup?country=jp&id=' . implode(',', array_unique($albumIds)), [], null, 60);
        $calls++;
        $data = $res['status'] === 200 ? http_json($res) : null;
        if (!is_array($data) || !isset($data['results'])) {
            $stopped = "Stopped: Lookup failed (HTTP {$res['status']}). Run again to continue";
            break;
        }

        // 照合はアルバム ID の一致だけで行う（一致しなければ「見つからない」とし、推測で埋めない）
        $genreByAlbum = [];
        foreach ($data['results'] as $item) {
            if (($item['wrapperType'] ?? '') === 'collection' && ($item['primaryGenreName'] ?? '') !== '') {
                $genreByAlbum[(string) $item['collectionId']] = $item['primaryGenreName'];
            }
        }

        if (!$dryRun) {
            $pdo->beginTransaction();
        }
        foreach ($rows as $r) {
            $scanned++;
            $genre = $genreByAlbum[$albumIds[$r['id']]] ?? null;
            if ($genre === null) {
                $notFound++;
                if (count($notFoundSample) < 5) {
                    $notFoundSample[] = "{$r['id']} | {$r['artist']} | {$r['title']}";
                }
                continue;
            }
            $genres[$genre] = ($genres[$genre] ?? 0) + 1;
            if ($dryRun) {
                if (count($found) < 10) {
                    $found[] = "{$r['artist']} | {$r['title']} → {$genre}";
                }
                $updated++;
            } else {
                $update->execute([$genre, $r['id']]);
                $updated += $update->rowCount();
            }
        }
        if (!$dryRun) {
            $pdo->commit();
        }
    }

    arsort($genres);
    $message = $stopped ?? ($scanned >= $limit ? 'Stopped: --limit reached' : 'Batch complete');
    return [
        'message'        => $dryRun ? "Dry run (nothing written): {$message}" : $message,
        'scanned'        => $scanned,
        'updated'        => $updated,
        'notFound'       => $notFound,
        'calls'          => $calls,
        'remaining'      => (int) $pdo->query('SELECT COUNT(*) FROM tracks WHERE genre IS NULL')->fetchColumn(),
        'genres'         => array_slice($genres, 0, 15, true),
        'found'          => $dryRun ? $found : null,
        'notFoundSample' => $notFoundSample,
    ];
});
