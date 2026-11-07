<?php
// 照合で確かめたリリース日（data/date_corrections.csv）を tracks に反映する。
// 直すのは DB の値が照合したときの値（db_date）のままの作品だけ。違う値になっていたら飛ばして一覧に出す（その後に誰かが直した可能性があるため）。
// 直す前の値は track_date_corrections に残し、--revert で戻せる。release_date と一緒に mmdd も変わるので、作品が出る日付ページが変わる。
// 1つのトランザクションで行うので、途中で失敗したら何も変えない。
//
//   php8.3 heteml/bin/apply_date_corrections.php --dry-run           直す件数と、照合時と値が違う作品を表示する（DB に書かない）
//   php8.3 heteml/bin/apply_date_corrections.php                     反映する
//   php8.3 heteml/bin/apply_date_corrections.php --revert --dry-run  戻す件数を表示する
//   php8.3 heteml/bin/apply_date_corrections.php --revert            track_date_corrections の全作品を直す前の値に戻す

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';

const CORRECTIONS_CSV = __DIR__ . '/../data/date_corrections.csv';
const CORRECTION_COLUMNS = ['track_id', 'artist', 'title', 'db_date', 'correct_date', 'release_type', 'confidence', 'source_url', 'checked_by'];

cron_main('apply_date_corrections', function (array $args): array {
    $dryRun = in_array('--dry-run', $args, true);
    return in_array('--revert', $args, true) ? revert_corrections($dryRun) : apply_corrections($dryRun);
});

function is_ymd(string $s): bool
{
    return (bool) preg_match('/^(\d{4})-(\d{2})-(\d{2})$/', $s, $m) && checkdate((int) $m[2], (int) $m[3], (int) $m[1]);
}

// CSV を読み、形の正しくない行が1つでもあれば何もせず止める
function read_corrections(): array
{
    $fh = fopen(CORRECTIONS_CSV, 'r');
    if (!$fh) {
        throw new RuntimeException('Cannot open ' . CORRECTIONS_CSV);
    }
    $header = fgetcsv($fh, null, ',', '"', '');
    if ($header !== CORRECTION_COLUMNS) {
        throw new RuntimeException('Unexpected header: ' . implode(',', $header ?: []));
    }
    $rows = [];
    $line = 1;
    while (($cols = fgetcsv($fh, null, ',', '"', '')) !== false) {
        $line++;
        $r = array_combine(CORRECTION_COLUMNS, array_pad($cols, count(CORRECTION_COLUMNS), ''));
        $bad = match (true) {
            $r['track_id'] === '' => 'track_id is empty',
            isset($rows[$r['track_id']]) => 'duplicate track_id',
            !is_ymd($r['db_date']) || !is_ymd($r['correct_date']) => 'date is not YYYY-MM-DD',
            $r['db_date'] === $r['correct_date'] => 'db_date equals correct_date',
            !in_array($r['confidence'], ['high', 'medium'], true) => 'confidence must be high or medium',
            $r['source_url'] === '' || $r['checked_by'] === '' || $r['release_type'] === '' => 'source_url, checked_by and release_type are required',
            default => null,
        };
        if ($bad !== null) {
            throw new RuntimeException("Line {$line}: {$bad}");
        }
        $rows[$r['track_id']] = $r;
    }
    fclose($fh);
    return $rows;
}

function apply_corrections(bool $dryRun): array
{
    $rows = read_corrections();
    $pdo = db();
    $current = [];
    foreach (array_chunk(array_keys($rows), 500) as $ids) {
        $stmt = $pdo->prepare('SELECT id, release_date FROM tracks WHERE id IN (' . implode(',', array_fill(0, count($ids), '?')) . ')');
        $stmt->execute($ids);
        foreach ($stmt->fetchAll() as $t) {
            $current[$t['id']] = $t['release_date'];
        }
    }

    $targets = $already = $changed = $missing = [];
    foreach ($rows as $id => $r) {
        $now = $current[$id] ?? null;
        if ($now === null) {
            $missing[] = $id;
        } elseif ($now === $r['correct_date']) {
            $already[] = $id;
        } elseif ($now !== $r['db_date']) {
            $changed[] = "{$id} {$r['artist']}「{$r['title']}」 DB {$now} / 照合時 {$r['db_date']} / 照合 {$r['correct_date']}";
        } else {
            $targets[] = $r;
        }
    }

    if (!$dryRun && $targets) {
        $update = $pdo->prepare('UPDATE tracks SET release_date = ?, mmdd = ? WHERE id = ? AND release_date = ?');
        // 直し直したときも、最初の値（old_release_date）は残す
        $record = $pdo->prepare('INSERT INTO track_date_corrections (track_id, old_release_date, new_release_date, release_type, confidence, source_url, checked_by)
            VALUES (?, ?, ?, ?, ?, ?, ?) AS n
            ON DUPLICATE KEY UPDATE new_release_date = n.new_release_date, release_type = n.release_type, confidence = n.confidence,
                source_url = n.source_url, checked_by = n.checked_by, applied_at = CURRENT_TIMESTAMP');
        $pdo->beginTransaction();
        try {
            foreach ($targets as $r) {
                $update->execute([$r['correct_date'], substr($r['correct_date'], 5), $r['track_id'], $r['db_date']]);
                if ($update->rowCount() !== 1) {
                    throw new RuntimeException("Update failed: {$r['track_id']}");
                }
                $record->execute([$r['track_id'], $r['db_date'], $r['correct_date'], $r['release_type'], $r['confidence'], $r['source_url'], $r['checked_by']]);
            }
            $pdo->commit();
        } catch (Throwable $e) {
            $pdo->rollBack();
            throw $e;
        }
    }

    return [
        'mode' => 'apply',
        'csvRows' => count($rows),
        ($dryRun ? 'wouldUpdate' : 'updated') => count($targets),
        'movesDatePage' => count(array_filter($targets, fn($r) => substr($r['db_date'], 5) !== substr($r['correct_date'], 5))),
        'alreadyCorrect' => count($already),
        'changedSinceCheck' => $changed,
        'notInDb' => $missing,
        'sample' => array_map(fn($r) => "{$r['track_id']} {$r['artist']}「{$r['title']}」 {$r['db_date']} → {$r['correct_date']}", array_slice($targets, 0, 5)),
    ];
}

function revert_corrections(bool $dryRun): array
{
    $pdo = db();
    $rows = $pdo->query('SELECT c.track_id, c.old_release_date, c.new_release_date, t.release_date
        FROM track_date_corrections c LEFT JOIN tracks t ON t.id = c.track_id ORDER BY c.track_id')->fetchAll();
    $targets = $changed = [];
    foreach ($rows as $r) {
        if ($r['release_date'] === $r['new_release_date']) {
            $targets[] = $r;
        } else {
            $changed[] = "{$r['track_id']} DB " . ($r['release_date'] ?? '（なし）') . " / 照合 {$r['new_release_date']}";
        }
    }
    if (!$dryRun && $targets) {
        $update = $pdo->prepare('UPDATE tracks SET release_date = ?, mmdd = ? WHERE id = ? AND release_date = ?');
        $delete = $pdo->prepare('DELETE FROM track_date_corrections WHERE track_id = ?');
        $pdo->beginTransaction();
        try {
            foreach ($targets as $r) {
                $update->execute([$r['old_release_date'], substr($r['old_release_date'], 5), $r['track_id'], $r['new_release_date']]);
                $delete->execute([$r['track_id']]);
            }
            $pdo->commit();
        } catch (Throwable $e) {
            $pdo->rollBack();
            throw $e;
        }
    }
    // DB の値が照合後に変わった作品は戻さない（記録も残す）
    return ['mode' => 'revert', 'records' => count($rows), ($dryRun ? 'wouldRevert' : 'reverted') => count($targets), 'changedSinceApply' => $changed];
}
