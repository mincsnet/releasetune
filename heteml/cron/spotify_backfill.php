#!/usr/local/bin/php8.3
<?php
// Spotify 直リンクの補完（毎日 JST 7:00、ヘテムルの cron から実行）。app/api/cron/spotify-backfill/route.ts からの移植。
// Spotify Web API の上限: Vercel 時代（2026-08-17〜18）は約200〜260リクエストで QUOTA_EXCEEDED になった。
// ヘテムルでは1日200曲で一度も429が出なかった（2026-10-15〜11-01）が、11-02 に上限を1000曲にしたら
// 299曲目で429・約24時間の停止になった。そのため1日200曲に戻し、問い合わせの数と429の時点を毎回ログに残す。
//
// 1曲あたりの問い合わせを減らすため、2段階で探す（tracks.spotify_search_stage）:
//   第1パス（stage 0 → 1）: 最初の厳密な検索の1回だけ
//   第2パス（stage 1 → 2）: 第1パスで見つからなかった曲を、残りの検索で探す。第1パスの残りがなくなってから
//   探し直し（stage 2）: すべての検索で見つからなかった曲は RECHECK_DAYS 日たってから、もう一度すべての検索で探す
// 第1パスの順番（2026-11-03 ユーザー承認の S4）: 最近30日の新着 → ピック（注目曲を含む）に選ばれる作品 → 次のリリース記念日が近い順 → id 順。
// 第2パス・探し直しは id 順（新着が先）。
// 429 で止められている間（src/spotify.php の spotify_blocked_until）は1回も問い合わせずに終わる。
// 停止の解除が WAIT_MAX_SEC 以内なら、解除まで待ってから始める（7:00 の実行が解除の直前に始まる場合）。
//
//   php heteml/cron/spotify_backfill.php                     本実行
//   php heteml/cron/spotify_backfill.php --dry-run --limit=5 5曲だけ検索して結果を表示する（DB に書かない。クォータは使う）

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';
require_once __DIR__ . '/../src/spotify.php';
require_once __DIR__ . '/../src/releases.php';

const DAILY_LIMIT = 200;      // 1日に探す曲数（2026-11-03 に1000から戻した。429 なしの実績がある数）
const TIME_BUDGET_SEC = 1500; // 問い合わせの間隔（1秒）を入れても200曲は約4分で終わる
const RECHECK_DAYS = 30;      // すべての検索で見つからなかった曲を探し直すまでの日数
const WAIT_MAX_SEC = 900;     // 停止の解除がこれ以内なら待ってから始める

// 直リンク（曲かアルバム）がまだ入っていない曲
const NOT_DIRECT = "(spotify IS NULL OR (spotify NOT LIKE '%open.spotify.com/track/%' AND spotify NOT LIKE '%open.spotify.com/album/%'))";
// 探す順の待ち行列（上から順に、DAILY_LIMIT に達するまで取る）。最近のリリース（新着）を先に、あとは id 順
const QUEUES = [
    'first'   => ['pass' => 'first', 'where' => NOT_DIRECT . ' AND spotify_search_stage = 0', 'nextStage' => 1],
    'rest'    => ['pass' => 'rest', 'where' => NOT_DIRECT . ' AND spotify_search_stage = 1', 'nextStage' => 2],
    'recheck' => ['pass' => 'all', 'where' => NOT_DIRECT . ' AND spotify_search_stage = 2 AND spotify_checked_at < UTC_TIMESTAMP() - INTERVAL ' . RECHECK_DAYS . ' DAY', 'nextStage' => 2],
];

cron_main('spotify_backfill', function (array $args): array {
    $dryRun = in_array('--dry-run', $args, true);
    $limit = DAILY_LIMIT;
    foreach ($args as $a) {
        if (preg_match('/^--limit=(\d+)$/', $a, $m)) {
            $limit = max(1, min((int) $m[1], DAILY_LIMIT));
        }
    }

    $pdo = db();
    $queued = [];
    foreach (QUEUES as $name => $q) {
        $queued[$name] = (int) $pdo->query('SELECT COUNT(*) FROM tracks WHERE ' . $q['where'])->fetchColumn();
    }

    // 停止中は問い合わせない。解除が近ければ待つ
    $waitedSec = 0;
    $resumeAt = spotify_blocked_until();
    if ($resumeAt !== null && $resumeAt - time() <= WAIT_MAX_SEC) {
        $waitedSec = $resumeAt - time();
        sleep($waitedSec);
        $resumeAt = spotify_blocked_until();
    }
    if ($resumeAt !== null) {
        return ['message' => 'Skipped: Spotify is blocked (429) until ' . date('c', $resumeAt), 'queued' => $queued, 'spotify' => spotify_stats()];
    }

    $token = spotify_token();
    if ($token === null) {
        throw new RuntimeException('Spotify token unavailable');
    }

    $targets = [];
    foreach (QUEUES as $name => $q) {
        if (count($targets) >= $limit) {
            break;
        }
        $rows = $name === 'first' ? first_pass_order($pdo->query('SELECT id, title, artist, release_date, track_count FROM tracks WHERE ' . $q['where'])->fetchAll())
            : $pdo->query('SELECT id, title, artist, release_date, track_count FROM tracks WHERE ' . $q['where']
                . ' ORDER BY release_date >= CURDATE() - INTERVAL 30 DAY DESC, id LIMIT ' . ($limit - count($targets)))->fetchAll();
        foreach (array_slice($rows, 0, $limit - count($targets)) as $t) {
            $targets[] = ['queue' => $name] + $t;
        }
    }

    $update = $pdo->prepare('UPDATE tracks SET spotify = ? WHERE id = ?');
    $markSearched = $pdo->prepare('UPDATE tracks SET spotify_search_stage = ?, spotify_checked_at = UTC_TIMESTAMP() WHERE id = ?');
    $startedAt = microtime(true);
    $byQueue = array_fill_keys(array_keys(QUEUES), ['processed' => 0, 'found' => 0]);
    $byPriority = []; // 第1パスの優先順の段（recent・pick・anniversary）ごとの件数
    $byStep = []; // 何番目の検索で見つかったか（1 が最初の厳密な検索）
    $processed = $updated = $notFound = 0;
    $retryAfter = null;
    $timeBudgetExceeded = false;
    $found = [];

    foreach ($targets as $t) {
        if (microtime(true) - $startedAt > TIME_BUDGET_SEC) {
            $timeBudgetExceeded = true;
            break;
        }
        $q = QUEUES[$t['queue']];
        $result = spotify_search($token, $t['title'], $t['artist'], $t['release_date'], release_kind($t) === 'album', $q['pass']);
        if ($result['retry_after'] !== null) {
            $retryAfter = $result['retry_after'];
            break;
        }
        $processed++;
        $byQueue[$t['queue']]['processed']++;
        if (isset($t['priority'])) {
            $byPriority[$t['priority']]['processed'] = ($byPriority[$t['priority']]['processed'] ?? 0) + 1;
        }
        if ($result['url'] !== null) {
            if ($dryRun) {
                $found[] = "{$t['artist']} | {$t['title']} → {$result['url']}";
            } else {
                $update->execute([$result['url'], $t['id']]);
            }
            $updated++;
            $byQueue[$t['queue']]['found']++;
            if (isset($t['priority'])) {
                $byPriority[$t['priority']]['found'] = ($byPriority[$t['priority']]['found'] ?? 0) + 1;
            }
            $byStep[$result['step']] = ($byStep[$result['step']] ?? 0) + 1;
        } else {
            if (!$dryRun) {
                $markSearched->execute([$q['nextStage'], $t['id']]);
            }
            $notFound++;
        }
    }

    $stats = spotify_stats();
    ksort($byStep);
    $message = $retryAfter !== null ? 'Stopped: Spotify quota exceeded'
        : ($timeBudgetExceeded ? 'Stopped: time budget reached' : 'Batch complete');
    return [
        'message'   => $dryRun ? "Dry run (nothing written): {$message}" : $message,
        'waitedSec' => $waitedSec,
        'queued'    => $queued,
        'fetched'   => count($targets),
        'processed' => $processed,
        'updated'   => $updated,
        'notFound'  => $notFound,
        'byQueue'   => $byQueue,
        'byPriority' => $byPriority,
        'foundByStep' => $byStep,
        // token を除いた検索だけの平均
        'searchRequestsPerTrack' => $processed > 0 ? round(($stats['byEndpoint']['search'] ?? 0) / $processed, 2) : null,
        'spotify'   => $stats,
        'quotaExceededRetryAfterSeconds' => $retryAfter,
        'found'     => $dryRun ? $found : null,
        'revalidated' => $updated > 0 && !$dryRun ? revalidate_site() : false,
    ];
});

// 第1パスの並べ替え。priority は段の名前（ログの byPriority）
function first_pass_order(array $rows): array
{
    $picks = pick_track_ids();
    $today = new DateTimeImmutable('today');
    $recentFrom = $today->modify('-30 days')->format('Y-m-d');
    foreach ($rows as &$t) {
        $t['priority'] = $t['release_date'] >= $recentFrom ? 'recent' : (isset($picks[$t['id']]) ? 'pick' : 'anniversary');
        $next = next_anniversary($t['release_date'], $today);
        $t['sortKey'] = [['recent' => 0, 'pick' => 1, 'anniversary' => 2][$t['priority']], (int) $today->diff($next['date'])->days, $t['id']];
    }
    unset($t);
    usort($rows, fn($a, $b) => $a['sortKey'] <=> $b['sortKey']);
    return $rows;
}
