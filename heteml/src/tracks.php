<?php
// サイト表示用のデータ取得（lib/tracks.ts と同じ問い合わせ）。
// 第1段階は api/tracks.php 経由で Vercel のサイトが使い、第2段階は PHP 版のページがそのまま使う。
// 返す行の形は DB の列名のまま（Supabase と同じ形。lib/tracks.ts の rowToTrack がそのまま使える）。

// 一覧系（日付・アーティスト・検索）で取得する列。楽曲詳細でしか使わない長文（note_long）と出典は含めない
const LIST_COLUMNS = [
    'id', 'title', 'artist', 'release_date', 'mmdd', 'jacket', 'note',
    'spotify', 'apple', 'amazon', 'youtube', 'youtube_id', 'youtube_verified', 'track_count', 'preview_url',
];

// 日付・アーティストの最大件数。Supabase の1回あたりの上限（1000行）で表示していた件数と揃える
// （1月1日は仮の日付の曲が集まって2,223曲あるが、これまでも1000曲だけ表示していた）
const LIST_LIMIT = 1000;

// 同じ発売日の曲の並びが毎回変わらないよう、id を2番目の並び順にする
const LIST_ORDER = 'release_date DESC, id ASC';

function tracks_by_mmdd(string $mmdd): array
{
    return tracks_query('WHERE mmdd = ?', [$mmdd], LIST_LIMIT);
}

function track_by_id(string $id): ?array
{
    $cols = implode(', ', array_map(fn($c) => "`{$c}`", array_keys(TABLES['tracks']['columns'])));
    $stmt = db()->prepare("SELECT {$cols} FROM tracks WHERE id = ?");
    $stmt->execute([$id]);
    $row = $stmt->fetch();
    return $row ? decode_row('tracks', $row) : null;
}

// アーティスト名は大文字小文字を区別せずに一致させる（これまでの ilike と同じ）
function tracks_by_artist(string $name): array
{
    return tracks_query('WHERE artist_lc = LOWER(?)', [$name], LIST_LIMIT);
}

// 名義の中で共演を表す区切り（& × , 、 / + と feat. with）。and と空白だけの「CHAGE and ASKA」のような名義は1つの名義として扱い、
// その中の名前（ASKA）を参加名義にしない。名義を区切りで分割はせず、既にあるアーティスト名がこの区切りに挟まれて出てくるかだけを見る
const PARTICIPATION_SEPARATOR = '(?:[&＆×✕,，、\\/／+＋と]|\\sx\\s|feat\\.?|ft\\.|featuring|with)';

// 参加名義か（$artist が $name そのものでなく、$name を共演の区切り・括弧（役名(本人)）に挟まれた形で含む）。大文字小文字は区別しない
function is_participation(string $artist, string $name): bool
{
    $a = mb_strtolower($artist);
    $n = mb_strtolower(trim($name));
    if ($n === '' || $a === $n) {
        return false;
    }
    $sep = PARTICIPATION_SEPARATOR;
    return (bool) preg_match('/(?:^|' . $sep . '\\s*|[(（])' . preg_quote($n, '/') . '(?:\\s*' . $sep . '|[)）]|$)/u', $a);
}

// アーティストページの「参加作品」。名義に名前を含む曲（部分一致）から is_participation のものだけ
function tracks_with_participation(string $name): array
{
    return array_values(array_filter(
        tracks_query('WHERE artist_lc LIKE LOWER(?) AND artist_lc <> LOWER(?)', [like_pattern($name), $name], LIST_LIMIT),
        fn($t) => is_participation($t['artist'], $name)
    ));
}

// 検索語の % と _ は文字そのものとして探す
function like_pattern(string $q): string
{
    return '%' . addcslashes(trim($q), '\\%_') . '%';
}

const SEARCH_WHERE = 'WHERE LOWER(title) LIKE LOWER(?) OR artist_lc LIKE LOWER(?)';

// 検索（曲名・名義の部分一致）。$offset 件目から $limit 件
function search_tracks(string $query, int $limit, int $offset = 0): array
{
    $like = like_pattern($query);
    return trim($query) === '' ? [] : tracks_query(SEARCH_WHERE, [$like, $like], $limit, $offset);
}

function search_count(string $query): int
{
    if (trim($query) === '') {
        return 0;
    }
    $like = like_pattern($query);
    $stmt = db()->prepare('SELECT COUNT(*) FROM tracks ' . SEARCH_WHERE);
    $stmt->execute([$like, $like]);
    return (int) $stmt->fetchColumn();
}

// 検索語がアーティスト名と一致するときの内訳（アーティストページの件数と同じ数え方）。一致しなければ null
// 戻り値: ['name' => いちばん多い表記, 'main' => 主名義の曲数, 'participation' => 参加作品の曲数]
function search_artist_breakdown(string $query): ?array
{
    $stmt = db()->prepare('SELECT artist, COUNT(*) c FROM tracks WHERE artist_lc = LOWER(?) GROUP BY artist ORDER BY c DESC');
    $stmt->execute([trim($query)]);
    $rows = $stmt->fetchAll();
    if (!$rows) {
        return null;
    }
    return ['name' => $rows[0]['artist'], 'main' => array_sum(array_column($rows, 'c')), 'participation' => count(tracks_with_participation(trim($query)))];
}

// sitemap 用。楽曲 ID を一覧と同じ並び（新しい順）で $offset 件目から $limit 件
function track_ids(int $offset, int $limit): array
{
    $stmt = db()->prepare('SELECT id FROM tracks ORDER BY ' . LIST_ORDER . ' LIMIT ? OFFSET ?');
    $stmt->execute([$limit, $offset]);
    return $stmt->fetchAll(PDO::FETCH_COLUMN);
}

function track_count(): int
{
    return (int) db()->query('SELECT COUNT(*) FROM tracks')->fetchColumn();
}

// sitemap 用。アーティストページは大文字小文字を区別しないので、表記違いは1つにまとめ、いちばん多い表記を返す
function artist_names(): array
{
    $rows = db()->query('SELECT artist FROM tracks GROUP BY artist ORDER BY COUNT(*) DESC, artist')->fetchAll(PDO::FETCH_COLUMN);
    $names = [];
    foreach ($rows as $name) {
        $names[mb_strtolower($name)] ??= $name;
    }
    return array_values($names);
}

// 日付ページのピック用。Wikipedia に作品の記事が見つかっている（紹介文の下調べで記事名が分かった）作品の id
function wiki_track_ids(array $ids): array
{
    if (!$ids) {
        return [];
    }
    $stmt = db()->prepare('SELECT track_id FROM track_note_drafts WHERE wiki_title IS NOT NULL AND track_id IN ('
        . implode(',', array_fill(0, count($ids), '?')) . ')');
    $stmt->execute(array_values($ids));
    return $stmt->fetchAll(PDO::FETCH_COLUMN);
}

// 日付ページのピック用。アーティストごとの作品数（キーは小文字の名前。アーティストページと同じく大文字小文字を区別しない）
function artist_track_counts(array $names): array
{
    if (!$names) {
        return [];
    }
    $stmt = db()->prepare('SELECT artist_lc, COUNT(*) FROM tracks WHERE artist_lc IN ('
        . implode(',', array_fill(0, count($names), 'LOWER(?)')) . ') GROUP BY artist_lc');
    $stmt->execute(array_values($names));
    return array_map('intval', $stmt->fetchAll(PDO::FETCH_KEY_PAIR));
}

function tracks_query(string $where, array $params, int $limit, int $offset = 0): array
{
    $cols = implode(', ', array_map(fn($c) => "`{$c}`", LIST_COLUMNS));
    $stmt = db()->prepare("SELECT {$cols} FROM tracks {$where} ORDER BY " . LIST_ORDER . ' LIMIT ? OFFSET ?');
    $stmt->execute([...$params, $limit, $offset]);
    return array_map(fn($row) => decode_row('tracks', $row), $stmt->fetchAll());
}
