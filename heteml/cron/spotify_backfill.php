#!/usr/local/bin/php8.3
<?php
// Spotify 直リンクの補完（毎日 JST 7:00、ヘテムルの cron から実行）。app/api/cron/spotify-backfill/route.ts からの移植。
// Spotify Web API の上限: Vercel 時代（2026-08-17〜18）は約200〜260リクエストで QUOTA_EXCEEDED になったが、
// ヘテムルに移ってからは1日200曲（数百リクエスト）で一度も429が出ていない（2026-10-15〜11-01）。
// 1日の件数を増やし、429を検出したらそこで打ち切る。件数ではなく経過時間でも打ち切る（tasks/lessons.md）。
// 見つからなかった曲は spotify_checked_at に日時を入れ、RECHECK_DAYS 日は探し直さない（毎日の枠を未検索の曲に使う）。
// アルバムはアルバムへの直リンクを探す（src/spotify.php の spotify_search）。
//
//   php heteml/cron/spotify_backfill.php                     本実行
//   php heteml/cron/spotify_backfill.php --dry-run --limit=5 5曲だけ検索して結果を表示する（DB に書かない。クォータは使う）

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';
require_once __DIR__ . '/../src/spotify.php';
require_once __DIR__ . '/../src/releases.php';

const FETCH_LIMIT = 1000;     // 一度に取得する候補件数の上限（2026-11-01 に200から増やした）
const TIME_BUDGET_SEC = 1500; // 1曲あたり約0.6秒（2026-10 のログ: 200曲で約120秒）なので、1000曲に足りる長さ
const RECHECK_DAYS = 30;      // 見つからなかった曲を探し直すまでの日数
const SLEEP_MS = 80;       // Spotify 検索リクエスト間の間隔

// 直リンク（曲かアルバム）がまだ入っておらず、最近探していない曲
const PENDING_WHERE = "(spotify IS NULL OR (spotify NOT LIKE '%open.spotify.com/track/%' AND spotify NOT LIKE '%open.spotify.com/album/%')) AND (spotify_checked_at IS NULL OR spotify_checked_at < UTC_TIMESTAMP() - INTERVAL " . RECHECK_DAYS . " DAY)";

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

    // 見つからなかった曲は spotify_checked_at で対象から外れるので、まだ探していない曲から id 順に進める
    // （以前は外せなかったので、同じ曲で枠を使い切らないよう開始位置をランダムにずらしていた）
    $pdo = db();
    $pendingCount = (int) $pdo->query('SELECT COUNT(*) FROM tracks WHERE ' . PENDING_WHERE)->fetchColumn();
    $stmt = $pdo->prepare('SELECT id, title, artist, release_date, track_count FROM tracks WHERE ' . PENDING_WHERE
        . ' ORDER BY spotify_checked_at IS NOT NULL, id LIMIT ?');
    $stmt->execute([$fetchLimit]);
    $pending = $stmt->fetchAll();

    $update = $pdo->prepare('UPDATE tracks SET spotify = ? WHERE id = ?');
    $markChecked = $pdo->prepare('UPDATE tracks SET spotify_checked_at = UTC_TIMESTAMP() WHERE id = ?');
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
        $result = spotify_search($token, $t['title'], $t['artist'], $t['release_date'], release_kind($t) === 'album');
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
            if (!$dryRun) {
                $markChecked->execute([$t['id']]);
            }
            $notFound++;
        }
        usleep(SLEEP_MS * 1000);
    }

    $message = $retryAfter !== null ? 'Stopped: Spotify quota exceeded'
        : ($timeBudgetExceeded ? 'Stopped: time budget reached' : 'Batch complete');
    return [
        'message'   => $dryRun ? "Dry run (nothing written): {$message}" : $message,
        'pending'   => $pendingCount,
        'fetched'   => count($pending),
        'processed' => $processed,
        'updated'   => $updated,
        'notFound'  => $notFound,
        'quotaExceededRetryAfterSeconds' => $retryAfter,
        'found'     => $dryRun ? $found : null,
        'revalidated' => $updated > 0 && !$dryRun ? revalidate_site() : false,
    ];
});
