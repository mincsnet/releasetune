#!/usr/local/bin/php8.3
<?php
// X の予約投稿（毎日 JST 6:00、ヘテムルの cron から実行）。その日がリリース日の作品を Buffer に予約する。
// 作品は日付ページのピック（src/releases.php の day_view）の上位から SLOTS の数まで、文面は楽曲ページの「X でシェア」と同じ（src/share.php）。
// 予約した枠は buffer_posts に残し、同じ日にもう一度動いたときは残りの枠だけ入れる。時刻を過ぎた枠は飛ばす。
// Buffer の無料プランは予約が1チャンネル10件までだが、6:00 の時点で前日分（最後は 18:45）は投稿済みなので8件は入る。
//
//   php heteml/cron/buffer_schedule.php                         本実行（今日の分）
//   php heteml/cron/buffer_schedule.php --dry-run               予約する作品と文面を表示するだけ（Buffer も DB も書かない。時刻を過ぎた枠も出す）
//   php heteml/cron/buffer_schedule.php --dry-run --date=2026-12-24  ほかの日で試す（文面の「今日」もその日になる）
//   php heteml/cron/buffer_schedule.php --channels              Buffer につないだチャンネルの ID を表示する（config.php の buffer_channel_id 用）

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';
require_once __DIR__ . '/../src/buffer.php';
require_once __DIR__ . '/../src/share.php';

// 投稿する時刻（JST）。ここの数がその日の上限
const SLOTS = ['07:00', '07:15', '07:30', '07:45', '18:00', '18:15', '18:30', '18:45'];
const MIN_LEAD_SEC = 300; // これより近い時刻の枠は予約しない（Buffer に届く前に時刻を過ぎないように）

cron_main('buffer_schedule', function (array $args): array {
    if (in_array('--channels', $args, true)) {
        return ['channels' => buffer_channels()];
    }
    $dryRun = in_array('--dry-run', $args, true);
    $date = date('Y-m-d');
    foreach ($args as $a) {
        if (preg_match('/^--date=(\d{4}-\d{2}-\d{2})$/', $a, $m)) {
            $date = $m[1];
        }
    }
    $mmdd = substr($date, 5);
    if (!is_valid_mmdd($mmdd)) {
        throw new InvalidArgumentException("日付が正しくありません: {$date}");
    }

    $pdo = db();
    $select = $pdo->prepare('SELECT slot, track_id FROM buffer_posts WHERE post_date = ?');
    $select->execute([$date]);
    $done = array_column($select->fetchAll(), 'track_id', 'slot');

    // 予約済みの作品を除いたピックを、空いている枠に上から順に入れる
    $picks = array_slice(day_view($mmdd, tracks_by_mmdd($mmdd))['picks'], 0, count(SLOTS));
    $tracks = array_values(array_filter(array_column($picks, 'track'), fn($t) => !in_array($t['id'], $done, true)));
    // --dry-run では時刻を見ない（ほかの日の文面も確かめられるように）
    $now = $dryRun ? PHP_INT_MIN : time();
    $slots = array_values(array_filter(SLOTS, fn($s) => !isset($done[$s]) && strtotime("{$date} {$s}") >= $now + MIN_LEAD_SEC));
    $skipped = array_values(array_filter(SLOTS, fn($s) => !isset($done[$s]) && !in_array($s, $slots, true)));

    $insert = $pdo->prepare('INSERT INTO buffer_posts (post_date, slot, track_id, buffer_post_id) VALUES (?, ?, ?, ?)');
    $channelId = $dryRun ? '' : config('buffer_channel_id');
    $scheduled = [];
    foreach (array_slice($slots, 0, count($tracks)) as $i => $slot) {
        $t = $tracks[$i];
        $text = share_text($t, $date, x_share_tags($t));
        $row = ['slot' => $slot, 'id' => $t['id'], 'artist' => $t['artist'], 'title' => $t['title'], 'xLength' => x_post_length($text)];
        if ($dryRun) {
            $row['text'] = $text;
        } else {
            // 1件ずつ記録する（途中で失敗しても、もう一度動かせば残りから続く）
            $insert->execute([$date, $slot, $t['id'], buffer_schedule_post($channelId, $text, strtotime("{$date} {$slot}"))]);
        }
        $scheduled[] = $row;
    }

    return [
        'message'   => $dryRun ? 'Dry run (nothing written)' : 'Scheduled',
        'date'      => $date,
        'picks'     => count($picks),
        'already'   => count($done),
        'scheduled' => $scheduled,
        'skipped'   => $skipped,
    ];
});
