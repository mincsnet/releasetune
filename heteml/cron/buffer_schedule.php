#!/usr/local/bin/php8.3
<?php
// X の予約投稿（Buffer）。2026-11-02 から承認制: 自動では予約せず、人が承認した作品だけを予約する（tasks/todo.md）。
// 手元の Claude のスケジュール済みタスクが前日に --candidates で候補を取り、リリース日・デビュー日を調べてユーザーに見せ、
// 承認された分を --plan で予約する。デビュー記念日は 0:00・0:05、ほかは 7:00〜18:45。
// 予約した枠は buffer_posts に残し、同じ枠には二度予約しない。時刻を過ぎた枠は予約しない。
// Buffer の無料プランは予約が1チャンネル10件まで。前日の夜に翌日分（最大10件）を入れる時点で、前日分（最後は 18:45）は投稿済み。
//
//   php8.3 heteml/cron/buffer_schedule.php --candidates --date=2026-11-03   候補（デビュー・ピック・ほかの作品）と文面を JSON で表示
//   php8.3 heteml/cron/buffer_schedule.php --plan=<base64> --date=2026-11-03 [--dry-run]
//       承認した計画を予約する。<base64> は [{"slot":"07:00","id":"作品ID","text":"文面（省略するとシェア文）"}, ...] の JSON を base64 にしたもの
//       （SSH 越しに引用符を渡さずに済むように）。--dry-run は確かめるだけで Buffer も DB も書かない
//   php8.3 heteml/cron/buffer_schedule.php --channels                        Buffer につないだチャンネルの ID（config.php の buffer_channel_id 用）

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';
require_once __DIR__ . '/../src/buffer.php';
require_once __DIR__ . '/../src/share.php';

// 投稿する時刻（JST）。デビュー記念日はその日の始まりに、ほかは朝と夕方に
const DEBUT_SLOTS = ['00:00', '00:05'];
const PICK_SLOTS = ['07:00', '07:15', '07:30', '07:45', '18:00', '18:15', '18:30', '18:45'];
const MIN_LEAD_SEC = 300;    // これより近い時刻の枠は予約しない（Buffer に届く前に時刻を過ぎないように）
const OTHER_CANDIDATES = 30; // --candidates でピック以外に出す作品の数

cron_main('buffer_schedule', function (array $args): array {
    if (in_array('--channels', $args, true)) {
        return ['channels' => buffer_channels()];
    }
    $dryRun = in_array('--dry-run', $args, true);
    $date = null;
    $plan = null;
    foreach ($args as $a) {
        if (preg_match('/^--date=(\d{4}-\d{2}-\d{2})$/', $a, $m)) {
            $date = $m[1];
        } elseif (preg_match('/^--plan=([A-Za-z0-9+\/=]+)$/', $a, $m)) {
            $plan = json_decode(base64_decode($m[1], true) ?: '', true);
            if (!is_array($plan)) {
                throw new InvalidArgumentException('--plan の JSON が読めません');
            }
        }
    }
    if ($date === null || !is_valid_mmdd(substr($date, 5)) || !checkdate((int) substr($date, 5, 2), (int) substr($date, 8, 2), (int) substr($date, 0, 4))) {
        throw new InvalidArgumentException('--date=YYYY-MM-DD で正しい日付を指定してください');
    }
    if (in_array('--candidates', $args, true)) {
        return buffer_candidates($date);
    }
    if ($plan === null) {
        throw new InvalidArgumentException('承認制なので --candidates か --plan が必要です（自動では予約しない）');
    }
    return buffer_schedule_plan($date, $plan, $dryRun);
});

// その日の候補。デビュー（デビュー記念日の一覧のデビュー日に出た作品）・ピック（日付ページと同じ順）・ほかの作品
function buffer_candidates(string $date): array
{
    $mmdd = substr($date, 5);
    $view = day_view($mmdd, tracks_by_mmdd($mmdd));
    $item = function (array $t) use ($date): array {
        $text = share_text($t, $date, x_share_tags($t));
        $debut = debut_db()[$t['artist']] ?? null;
        return [
            'id' => $t['id'], 'artist' => $t['artist'], 'title' => $t['title'], 'releaseDate' => $t['release_date'],
            'kind' => release_kind($t), 'trackCount' => $t['track_count'] ?? null,
            'debutDate' => $debut['debutDate'] ?? null, 'debutTrack' => $debut['debutTrack'] ?? null,
            'page' => 'https://releasetune.com/track/' . $t['id'], 'apple' => $t['apple'] ?? null,
            'text' => $text, 'xLength' => x_post_length($text),
        ];
    };
    // rest には一括配信をまとめた枠（['batch' => [unit, ...]]）が混ざる。デビューは中も見る。ほかの作品には一括配信を出さない（配信日の可能性が高い）
    $units = array_merge($view['picks'], ...array_map(fn($u) => $u['batch'] ?? [$u], $view['rest']));
    $debuts = array_values(array_filter(array_column($units, 'track'), 'is_debut_track'));
    $others = array_slice(array_values(array_filter($view['rest'], fn($u) => isset($u['track']))), 0, OTHER_CANDIDATES);
    return [
        'date'      => $date,
        'count'     => $view['count'],
        'scheduled' => buffer_scheduled($date),
        'slots'     => ['debut' => DEBUT_SLOTS, 'pick' => PICK_SLOTS],
        'debuts'    => array_map($item, $debuts),
        'picks'     => array_map(fn($u) => $item($u['track']) + ['score' => $u['score'], 'reasons' => $u['reasons']], $view['picks']),
        'others'    => array_map(fn($u) => $item($u['track']), $others),
    ];
}

// 予約済みの枠 => 作品 ID
function buffer_scheduled(string $date): array
{
    $select = db()->prepare('SELECT slot, track_id FROM buffer_posts WHERE post_date = ?');
    $select->execute([$date]);
    return array_column($select->fetchAll(), 'track_id', 'slot');
}

// 承認した計画を予約する。全体を先に確かめ、1つでもおかしければ何も予約しない
function buffer_schedule_plan(string $date, array $plan, bool $dryRun): array
{
    $done = buffer_scheduled($date);
    $items = [];
    $skipped = [];
    foreach ($plan as $p) {
        $slot = (string) ($p['slot'] ?? '');
        $id = (string) ($p['id'] ?? '');
        if (!in_array($slot, [...DEBUT_SLOTS, ...PICK_SLOTS], true)) {
            throw new InvalidArgumentException("使えない枠です: {$slot}");
        }
        if (isset($items[$slot])) {
            throw new InvalidArgumentException("同じ枠が2回あります: {$slot}");
        }
        if (isset($done[$slot])) {
            $skipped[] = ['slot' => $slot, 'reason' => "予約済み（{$done[$slot]}）"];
            continue;
        }
        $t = track_by_id($id);
        if ($t === null) {
            throw new InvalidArgumentException("作品がありません: {$id}");
        }
        $text = isset($p['text']) && trim((string) $p['text']) !== '' ? (string) $p['text'] : share_text($t, $date, x_share_tags($t));
        if (x_post_length($text) > X_MAX_LENGTH) {
            throw new InvalidArgumentException("{$slot} の文面が " . X_MAX_LENGTH . ' 字を超えています（' . x_post_length($text) . '）');
        }
        $dueAt = strtotime("{$date} {$slot}");
        if (!$dryRun && $dueAt < time() + MIN_LEAD_SEC) {
            $skipped[] = ['slot' => $slot, 'reason' => '時刻を過ぎている'];
            continue;
        }
        $items[$slot] = ['slot' => $slot, 'id' => $t['id'], 'artist' => $t['artist'], 'title' => $t['title'], 'text' => $text, 'xLength' => x_post_length($text), 'dueAt' => $dueAt];
    }

    if (!$dryRun) {
        $insert = db()->prepare('INSERT INTO buffer_posts (post_date, slot, track_id, buffer_post_id) VALUES (?, ?, ?, ?)');
        $channelId = config('buffer_channel_id');
        foreach ($items as $it) {
            // 1件ずつ記録する（途中で失敗しても、もう一度同じ計画を渡せば残りから続く）
            $insert->execute([$date, $it['slot'], $it['id'], buffer_schedule_post($channelId, $it['text'], $it['dueAt'])]);
        }
    }
    return [
        'message'   => $dryRun ? 'Dry run (nothing written)' : 'Scheduled',
        'date'      => $date,
        'scheduled' => array_values(array_map(fn($it) => array_diff_key($it, ['dueAt' => 0]), $items)),
        'skipped'   => $skipped,
    ];
}
