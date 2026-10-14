#!/usr/local/bin/php8.3
<?php
// Spotify 直リンクの補完（毎日 JST 7:00、ヘテムルの cron から実行）。app/api/cron/spotify-backfill/route.ts からの移植。
// Spotify Web API はアプリ単位で1日あたり数百リクエスト程度しか使えない
// （2026-08-17〜18に実測: 約200〜260リクエストでQUOTA_EXCEEDEDになり、Retry-Afterから逆算すると
//  直近の初回呼び出しから約24時間のローリングウィンドウ）。そのため429を検出したら即座に打ち切る。
// Vercel では60秒の制限があり45秒で打ち切っていたが、ヘテムルにはその制限がないので、クォータを使い切れる長さにする。
// それでも件数ではなく経過時間で打ち切る（tasks/lessons.md）。
//
//   php heteml/cron/spotify_backfill.php                     本実行
//   php heteml/cron/spotify_backfill.php --dry-run --limit=5 5曲だけ検索して結果を表示する（DB に書かない。クォータは使う）

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';
require_once __DIR__ . '/../src/spotify.php';

const FETCH_LIMIT = 200;   // 一度に取得する候補件数の上限
const TIME_BUDGET_SEC = 300; // 1曲あたり約1.3秒（2026-09-23 実測）なので、クォータ（約200〜260リクエスト）を使い切れる長さ
const SLEEP_MS = 80;       // Spotify 検索リクエスト間の間隔

// 直リンク（open.spotify.com/track/）がまだ入っていない曲
const PENDING_WHERE = "(spotify IS NULL OR spotify NOT LIKE '%open.spotify.com/track/%')";

cron_main('spotify_backfill', function (array $args): array {
    $dryRun = in_array('--dry-run', $args, true);
    $fetchLimit = FETCH_LIMIT;
    foreach ($args as $a) {
        if (preg_match('/^--limit=(\d+)$/', $a, $m)) {
            $fetchLimit = max(1, min((int) $m[1], FETCH_LIMIT));
        }
    }

    $token = spotify_token();
    if ($token === null) {
        throw new RuntimeException('Spotify token unavailable');
    }

    // Spotifyで一致する曲が見つからない行は検索URLのまま対象に残り続ける。毎回id昇順の先頭から取ると
    // そうした行だけで1回分の処理時間を使い切って先に進めなくなるため、開始位置を毎回ランダムにずらす。
    $pdo = db();
    $pendingCount = (int) $pdo->query('SELECT COUNT(*) FROM tracks WHERE ' . PENDING_WHERE)->fetchColumn();
    $offset = random_int(0, max(0, $pendingCount - $fetchLimit));
    $stmt = $pdo->prepare('SELECT id, title, artist, release_date FROM tracks WHERE ' . PENDING_WHERE . ' ORDER BY id LIMIT ? OFFSET ?');
    $stmt->execute([$fetchLimit, $offset]);
    $pending = $stmt->fetchAll();

    $update = $pdo->prepare('UPDATE tracks SET spotify = ? WHERE id = ?');
    $startedAt = microtime(true);
    $processed = $updated = $notFound = 0;
    $retryAfter = null;
    $timeBudgetExceeded = false;
    $found = [];

    foreach ($pending as $t) {
        if (microtime(true) - $startedAt > TIME_BUDGET_SEC) {
            $timeBudgetExceeded = true;
            break;
        }
        $result = spotify_search($token, $t['title'], $t['artist'], $t['release_date']);
        if ($result['retry_after'] !== null) {
            $retryAfter = $result['retry_after'];
            break;
        }
        $processed++;
        if ($result['url'] !== null) {
            if ($dryRun) {
                $found[] = "{$t['artist']} | {$t['title']} → {$result['url']}";
            } else {
                $update->execute([$result['url'], $t['id']]);
            }
            $updated++;
        } else {
            $notFound++;
        }
        usleep(SLEEP_MS * 1000);
    }

    $message = $retryAfter !== null ? 'Stopped: Spotify quota exceeded'
        : ($timeBudgetExceeded ? 'Stopped: time budget reached (next run starts from another random offset)' : 'Batch complete');
    return [
        'message'   => $dryRun ? "Dry run (nothing written): {$message}" : $message,
        'pending'   => $pendingCount,
        'offset'    => $offset,
        'fetched'   => count($pending),
        'processed' => $processed,
        'updated'   => $updated,
        'notFound'  => $notFound,
        'quotaExceededRetryAfterSeconds' => $retryAfter,
        'found'     => $dryRun ? $found : null,
        'revalidated' => $updated > 0 && !$dryRun ? revalidate_site() : false,
    ];
});
