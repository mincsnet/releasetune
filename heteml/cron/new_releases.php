#!/usr/local/bin/php8.3
<?php
// 新着の取得（毎日 JST 0:00、ヘテムルの cron から実行）。app/api/cron/new-releases/route.ts からの移植。
// iTunes RSS から新着100件を取得 → まだ無い曲だけ追加 → 追加した曲だけ Spotify・YouTube の直リンクを補完
// （既存曲の API クォータ消費を避けるため）。
//
//   php heteml/cron/new_releases.php            本実行
//   php heteml/cron/new_releases.php --dry-run  追加される曲を表示するだけ（DB に書かず、Spotify・YouTube も呼ばない）

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/cron.php';
require_once __DIR__ . '/../src/spotify.php';
require_once __DIR__ . '/../src/youtube.php';

cron_main('new_releases', function (array $args): array {
    $dryRun = in_array('--dry-run', $args, true);

    $res = http_request('GET', 'https://itunes.apple.com/jp/rss/topalbums/limit=100/json');
    if ($res['status'] !== 200) {
        throw new RuntimeException("iTunes RSS fetch failed: {$res['status']}");
    }
    $entries = http_json($res)['feed']['entry'] ?? [];
    if (!$entries) {
        return ['message' => 'No entries found', 'added' => 0];
    }

    $rows = [];
    foreach ($entries as $e) {
        $releaseDate = substr($e['im:releaseDate']['label'], 0, 10);
        // RSSの画像は最大でも170x170bb.pngなので、URL末尾を600x600bb.jpgに差し替える
        // （既存データと同じ形式。600x600のPNGはJPGの約5倍の容量で、ジャケットはそのまま配信される）
        $images = $e['im:image'];
        usort($images, fn($a, $b) => (int) $b['attributes']['height'] <=> (int) $a['attributes']['height']);
        $jacket = isset($images[0]) ? preg_replace('/\/\d+x\d+bb\.\w+$/', '/600x600bb.jpg', $images[0]['label']) : '';
        $rows[] = [
            'id'           => $e['id']['attributes']['im:id'],
            'title'        => $e['im:name']['label'],
            'artist'       => $e['im:artist']['label'],
            'release_date' => $releaseDate,
            'mmdd'         => substr($releaseDate, 5, 5),
            'jacket'       => $jacket,
            'apple'        => $e['link']['attributes']['href'],
        ];
    }

    // 既にある曲は何も変えない（ON DUPLICATE KEY UPDATE id = id は行数0、新規追加は行数1を返す）
    $pdo = db();
    $exists = $pdo->prepare('SELECT 1 FROM tracks WHERE id = ?');
    $insert = $pdo->prepare(
        'INSERT INTO tracks (id, title, artist, release_date, mmdd, jacket, apple,
                             spotify, amazon, youtube, youtube_id, youtube_verified, note, note_verified)
         VALUES (?, ?, ?, ?, ?, ?, ?, NULL, NULL, NULL, NULL, 0, NULL, 0)
         ON DUPLICATE KEY UPDATE id = id'
    );
    $newRows = [];
    foreach ($rows as $r) {
        if ($dryRun) {
            $exists->execute([$r['id']]);
            $isNew = $exists->fetchColumn() === false;
        } else {
            $insert->execute(array_values($r));
            $isNew = $insert->rowCount() === 1;
        }
        if ($isNew) {
            $newRows[] = $r;
        }
    }

    $enriched = 0;
    if ($newRows && !$dryRun) {
        $token = spotify_token();
        $update = fn(array $set, string $id) => $pdo
            ->prepare('UPDATE tracks SET ' . implode(', ', array_map(fn($c) => "`{$c}` = ?", array_keys($set))) . ' WHERE id = ?')
            ->execute([...array_values($set), $id]);
        foreach ($newRows as $r) {
            $set = [];
            if ($token !== null) {
                $sp = spotify_search($token, $r['title'], $r['artist'], $r['release_date']);
                if ($sp['url'] !== null) {
                    $set['spotify'] = $sp['url'];
                }
            }
            $yt = youtube_search($r['title'], $r['artist']);
            if ($yt !== null) {
                $set['youtube'] = "https://music.youtube.com/watch?v={$yt['id']}";
                $set['youtube_id'] = $yt['id'];
                $set['youtube_verified'] = $yt['verified'] ? 1 : 0;
            }
            if ($set) {
                $update($set, $r['id']);
                $enriched++;
            }
        }
    }

    return [
        'message'     => $dryRun ? 'Dry run (nothing written)' : 'New releases fetched',
        'fetched'     => count($entries),
        'added'       => count($newRows),
        'enriched'    => $enriched,
        'sample'      => array_map(fn($r) => "{$r['artist']} | {$r['title']}", array_slice($newRows, 0, 3)),
        'revalidated' => $newRows && !$dryRun ? revalidate_site() : false,
    ];
});
