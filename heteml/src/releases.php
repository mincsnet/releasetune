<?php
// 作品の見せ方の決まり（2026-11-01 ユーザー決定、tasks/todo.md の Phase 2）:
// - 作品の種類（シングル・EP・アルバム）
// - 同じ曲の別盤（feat. 違い・リミックス・Type 違い・ジャケ違い・リマスターなど）を1つにまとめる。ライブ・カバー・アルバムとシングルはまとめない
// - 同じアーティストが同じ日にまとめて配信した作品（昔のシングルの一括配信など）を日付ページで1枠に畳む
// - 日付ページの「ピック」（最大10作品）の選び方
// データは消さず、表示のときにまとめる

require_once __DIR__ . '/site.php';
require_once __DIR__ . '/tracks.php';

// ── 作品の種類 ──────────────────────────────────────────

// Apple の作品名の末尾（- Single・- EP）で判定し、末尾がなければ収録曲数で決める。
// 無作為200件の調査（2026-11-01）で、末尾「- Single」は1〜3曲、「- EP」は4〜6曲、末尾なしは97%が7曲以上だった
function release_kind(array $t): string
{
    if (preg_match('/-\s*Single$/u', $t['title'])) {
        return 'single';
    }
    if (preg_match('/-\s*EP$/u', $t['title'])) {
        return 'ep';
    }
    $count = $t['track_count'] ?? null;
    return $count !== null && $count <= 3 ? 'single' : 'album';
}

// 「シングル」「EP」「アルバム・11曲」（曲数が分からないアルバムは「アルバム」）
function release_kind_label(array $t): string
{
    $kind = release_kind($t);
    if ($kind === 'album') {
        return 'アルバム' . (!empty($t['track_count']) ? "・{$t['track_count']}曲" : '');
    }
    return $kind === 'ep' ? 'EP' : 'シングル';
}

// 種類のラベルを横に出す場所（一括配信の一覧）で使う短い作品名（末尾の「- Single」「- EP」と「(Original Cover Art)」を外す）
function short_title(string $title): string
{
    return trim(preg_replace(['/\s*-\s*(?:Single|EP)$/u', '/\s*[\(\[]Original Cover Art[\)\]]/u'], '', $title));
}

// ── 同じ曲の別盤 ────────────────────────────────────────

// 括弧の中にあれば「同じ曲の別の盤」とみなす言葉（小文字・NFKC にした曲名に当てる）
const VERSION_VARIANT_PATTERN = '/(?<![\p{L}\p{N}])(?:feat\.?|ft\.?|featuring|with|type[\s\-]?[a-z0-9]{1,2}|通常盤|初回(?:限定|生産)?盤[a-z]?|劇場盤'
    . '|(?:期間(?:生産)?)?限定盤[a-z]?|special edition|deluxe|original cover art|remaster(?:ed)?|リマスター|instrumental|inst\.?'
    . '|off vocal|karaoke|カラオケ|(?:re)?mix|version|ver\.?|edit|dub|acoustic)(?![\p{L}])/u';

// ライブ盤・カバーは別の作品として扱う（「Original Cover Art」はジャケ違いなので先に外して判定する）
const VERSION_SEPARATE_PATTERN = '/(?<![a-z])live(?![a-z])|ライブ|ライヴ|(?<![a-z])covers?(?![a-z])|カバー/u';

function version_normalize(string $s): string
{
    return mb_strtolower(Normalizer::normalize($s, Normalizer::FORM_KC) ?: $s);
}

// 同じ曲の別盤なら同じ値になるキー。曲名から飾り（- Single・括弧の中の feat. や Type-A など）を外し、
// アーティスト名・アルバムかどうか・ライブかどうかと組み合わせる
function version_key(array $t): string
{
    $s = preg_replace('/\s*-\s*(?:single|ep)$/u', '', version_normalize($t['title']));
    // 内側の括弧から順に外す（「(<Type-A>)」「(【劇場盤】)」は中を外したあと空の括弧も外す）
    do {
        $prev = $s;
        $s = preg_replace_callback('/\s*[\(\[<【]([^\(\)\[\]<>【】]*)[\)\]>】]/u',
            fn($m) => trim($m[1]) === '' || preg_match(VERSION_VARIANT_PATTERN, $m[1]) ? '' : $m[0], $s);
    } while ($s !== $prev);
    // 括弧なしで末尾に付く「夏のFree&Easy Type-A」
    $s = trim(preg_replace(['/\s+type[\s\-]?[a-z0-9]{1,2}$/u', '/\s+/u'], ['', ' '], $s));
    $separate = preg_match(VERSION_SEPARATE_PATTERN, str_replace('original cover art', '', version_normalize($t['title'])));
    return implode("\t", [
        $s !== '' ? $s : version_normalize($t['title']),
        preg_replace('/\s+/u', '', version_normalize($t['artist'])),
        release_kind($t) === 'album' ? 'album' : 'single',
        $separate ? 'live' : '',
    ]);
}

// 曲名から分かる盤の違いのラベル（断定できる言葉だけ。「再発」は曲名からは分からないので付けない）
function version_labels(array $t): array
{
    $s = version_normalize($t['title']);
    $labels = [];
    foreach ([
        'ライブ'           => '/(?<![a-z])live(?![a-z])|ライブ|ライヴ/u',
        'リマスター'       => '/remaster|リマスター/u',
        'リミックス'       => '/(?<![a-z])(?:re)?mix(?![a-z])/u',
        'アコースティック' => '/acoustic|アコースティック/u',
        'インスト'         => '/instrumental|(?<![a-z])inst\.|off vocal|karaoke|カラオケ/u',
    ] as $label => $pattern) {
        if (preg_match($pattern, $s)) {
            $labels[] = $label;
        }
    }
    return $labels;
}

// 代表にする1件: 飾りの少ない（曲名の短い）もの → Spotify の直リンクがあるもの → 古いもの → id 順
function version_rank(array $t): array
{
    return [mb_strlen($t['title']), str_contains((string) $t['spotify'], '/search') || empty($t['spotify']) ? 1 : 0, $t['release_date'], $t['id']];
}

// 一覧（並び順はそのまま）を、同じ曲の別盤ごとにまとめる。
// 戻り値: [['track' => 代表, 'versions' => [ほかの盤...]], ...]（代表がいちばん先に出てくる位置に置く）
function group_versions(array $tracks): array
{
    $groups = [];
    foreach ($tracks as $t) {
        $groups[version_key($t)][] = $t;
    }
    $firstPos = [];
    foreach ($tracks as $i => $t) {
        $firstPos[version_key($t)] ??= $i;
    }
    $units = [];
    foreach ($groups as $key => $members) {
        usort($members, fn($a, $b) => version_rank($a) <=> version_rank($b));
        $units[$firstPos[$key]] = ['track' => array_shift($members), 'versions' => $members];
    }
    ksort($units);
    return array_values($units);
}

// 楽曲ページの「ほかのバージョン」（同じアーティストの作品 $byArtist から、同じ曲の別盤を発売日の新しい順に）
function other_versions(array $t, array $byArtist): array
{
    $key = version_key($t);
    return array_values(array_filter($byArtist, fn($o) => $o['id'] !== $t['id'] && version_key($o) === $key));
}

// ── 同じアーティストの他のリリース記念日 ─────────────────────

const ANNIVERSARY_MAX = 5;

// 次にリリース記念日が来る日（今日を含む）と、その日で何周年か。2月29日はうるう年にだけ来る
function next_anniversary(string $releaseDate, DateTimeImmutable $today): array
{
    [$y, $m, $d] = array_map('intval', explode('-', $releaseDate));
    for ($year = (int) $today->format('Y'); ; $year++) {
        if (checkdate($m, $d, $year) && sprintf('%04d-%02d-%02d', $year, $m, $d) >= $today->format('Y-m-d')) {
            return ['date' => new DateTimeImmutable(sprintf('%04d-%02d-%02d', $year, $m, $d)), 'years' => $year - $y];
        }
    }
}

// 楽曲ページの「{アーティスト}の他のリリース記念日」。次に記念日が来る順に最大 ANNIVERSARY_MAX 件。
// 同じ曲の別盤は1件にまとめ、この曲の別盤（「ほかのバージョン」に出るもの）は除く。日付はなるべくばらけるよう、
// まず日付ごとに1件ずつ選んでから残りで埋める。周年が1年未満（今年のリリースで記念日がまだ来ていない）のものは出さない。
// 戻り値: [['track' => ..., 'date' => 次の記念日, 'years' => 周年], ...]
function other_anniversaries(array $t, array $candidates, DateTimeImmutable $today): array
{
    $key = version_key($t);
    $items = [];
    foreach (group_versions($candidates) as $unit) {
        $o = $unit['track'];
        if ($o['id'] === $t['id'] || version_key($o) === $key) {
            continue;
        }
        $next = next_anniversary($o['release_date'], $today);
        if ($next['years'] >= 1) {
            $items[] = ['track' => $o] + $next;
        }
    }
    // 近い順。同じ日なら周年の大きい（古い）ものから
    usort($items, fn($a, $b) => [$a['date'], $a['track']['release_date']] <=> [$b['date'], $b['track']['release_date']]);
    $picked = $rest = [];
    foreach ($items as $item) {
        $day = $item['date']->format('Y-m-d');
        if (!isset($picked[$day])) {
            $picked[$day] = $item;
        } else {
            $rest[] = $item;
        }
    }
    $result = array_slice(array_values($picked), 0, ANNIVERSARY_MAX);
    if (count($result) < ANNIVERSARY_MAX) {
        $result = array_merge($result, array_slice($rest, 0, ANNIVERSARY_MAX - count($result)));
        usort($result, fn($a, $b) => [$a['date'], $a['track']['release_date']] <=> [$b['date'], $b['track']['release_date']]);
    }
    return $result;
}

// ── 一括配信 ────────────────────────────────────────────

// 同じアーティストが同じ発売日にこの数以上の作品（別盤をまとめた後の数）を出していたら、日付ページで1枠に畳む。
// 昔のシングルを配信開始の日にまとめて出したもの（松本伊代 2007-10-31 の24枚など）が一覧を占めないように
const BATCH_MIN = 5;

function batch_key(array $t): string
{
    return mb_strtolower($t['artist']) . "\t" . $t['release_date'];
}

// まとめた作品の一覧から、一括配信に当たるもののキー => 件数
function batch_keys(array $units): array
{
    $counts = array_count_values(array_map(fn($u) => batch_key($u['track']), $units));
    return array_filter($counts, fn($n) => $n >= BATCH_MIN);
}

// 一括配信の作品を1枠（['batch' => [...units], 'artist', 'release_date']）にまとめる。枠は最初に出てくる位置に置く
function fold_batches(array $units, array $batchKeys): array
{
    $out = [];
    $slot = [];
    foreach ($units as $u) {
        $key = batch_key($u['track']);
        if (!isset($batchKeys[$key])) {
            $out[] = $u;
        } elseif (isset($slot[$key])) {
            $out[$slot[$key]]['batch'][] = $u;
        } else {
            $slot[$key] = count($out);
            $out[] = ['batch' => [$u], 'artist' => $u['track']['artist'], 'release_date' => $u['track']['release_date']];
        }
    }
    return $out;
}

// 「シングル24」「シングル28・EP2」（種類ごとの数）
function batch_kind_summary(array $batch): string
{
    $counts = array_count_values(array_map(fn($u) => preg_replace('/・.*$/u', '', release_kind_label($u['track'])), $batch));
    return implode('・', array_map(fn($k, $n) => "{$k}{$n}", array_keys($counts), $counts));
}

// ── デビュー記念日（debut_artists.csv） ──

function debut_db(): array
{
    static $db = null;
    if ($db !== null) {
        return $db;
    }
    $db = [];
    // 「"」で囲んだ値（「Love, Day After Tomorrow」のようにカンマを含む作品名など）を読めるよう、CSV として読む
    $fh = @fopen(__DIR__ . '/../data/debut_artists.csv', 'r');
    if (!$fh) {
        return $db;
    }
    $header = array_map('trim', fgetcsv($fh, null, ',', '"', '') ?: []);
    while (($cols = fgetcsv($fh, null, ',', '"', '')) !== false) {
        $row = [];
        foreach ($header as $i => $name) {
            $row[$name] = trim($cols[$i] ?? '');
        }
        if (($row['artist'] ?? '') !== '' && ($row['debut_date'] ?? '') !== '') {
            $db[$row['artist']] = ['artist' => $row['artist'], 'debutDate' => $row['debut_date'], 'debutTrack' => $row['debut_track'] ?? ''];
        }
    }
    fclose($fh);
    return $db;
}

function debuts_by_mmdd(string $mmdd): array
{
    return array_values(array_filter(debut_db(), fn($d) => substr($d['debutDate'], 5) === $mmdd));
}

// デビュー記念日の一覧にある、そのアーティストのデビュー日に出た作品か（シェア文をデビュー用にする・ピックで加点）
function is_debut_track(array $t): bool
{
    return (debut_db()[$t['artist']]['debutDate'] ?? null) === $t['release_date'];
}

// ── 日付ページのピック ─────────────────────────────────────

const PICK_MAX = 10;

// ピックの点数（調整しやすいようにここにまとめる）。人気の数値は持っていないので、持っている事実だけで付ける
const PICK_WEIGHTS = [
    // キリのいい周年 => 点
    'anniversary'     => [50 => 40, 40 => 35, 30 => 35, 25 => 30, 20 => 30, 15 => 20, 10 => 25, 5 => 20],
    'debut_track'     => 40,  // デビュー記念日の一覧にある、デビュー日の作品
    'wiki'            => 25,  // Wikipedia に作品の記事がある（紹介文の下調べ track_note_drafts で見つかったもの）
    'note'            => 10,  // 紹介文がある
    'debut_artist'    => 10,  // デビュー記念日の一覧にいるアーティスト（よく知られた人を集めた一覧）
    'artist_size'     => 4,   // サイトにあるそのアーティストの作品数の log2 × この点
    'artist_size_max' => 20,
    'spotify_direct'  => 3,   // Spotify で曲を特定できている（新着は追加時に直リンクが付くので、人気の目安としては弱くする）
    'youtube_mv'      => 8,   // 公式動画がある
    'single'          => 5,   // シングル・EP（「あの曲」として思い出しやすい）
    'batch'           => -30, // 一括配信の作品（発売日が本来の日でない可能性が高い）
    'this_year'       => -10, // 今年の作品
];

// 運営者が日付ごとに先頭に固定する作品（heteml/data/picks.csv。mmdd,track_id。# で始まる行は説明）
function pinned_picks(string $mmdd): array
{
    $ids = [];
    foreach (@file(__DIR__ . '/../data/picks.csv', FILE_IGNORE_NEW_LINES | FILE_SKIP_EMPTY_LINES) ?: [] as $line) {
        $cols = array_map('trim', explode(',', $line));
        if ($cols[0] === $mmdd && ($cols[1] ?? '') !== '') {
            $ids[] = $cols[1];
        }
    }
    return $ids;
}

// 1作品の点数と内訳（['score' => 点, 'reasons' => ['10周年 +25', ...]]）
function pick_score(array $u, array $ctx): array
{
    $t = $u['track'];
    $w = PICK_WEIGHTS;
    $years = years_ago($t['release_date']);
    $parts = [];
    if (isset($w['anniversary'][$years])) {
        $parts["{$years}周年"] = $w['anniversary'][$years];
    }
    if (is_debut_track($t)) {
        $parts['デビュー作'] = $w['debut_track'];
    }
    if (isset($ctx['wiki'][$t['id']])) {
        $parts['Wikipedia'] = $w['wiki'];
    }
    if (!empty($t['note'])) {
        $parts['紹介文'] = $w['note'];
    }
    if (isset(debut_db()[$t['artist']])) {
        $parts['デビュー一覧'] = $w['debut_artist'];
    }
    $size = $ctx['artistSize'][mb_strtolower($t['artist'])] ?? 1;
    if ($size > 1) {
        $parts["作品数{$size}"] = (int) min($w['artist_size_max'], round(log($size, 2) * $w['artist_size']));
    }
    if (!empty($t['spotify']) && !str_contains($t['spotify'], '/search')) {
        $parts['Spotify'] = $w['spotify_direct'];
    }
    if (!empty($t['youtube_id']) && !empty($t['youtube_verified'])) {
        $parts['公式動画'] = $w['youtube_mv'];
    }
    if (release_kind($t) !== 'album') {
        $parts['シングル'] = $w['single'];
    }
    if (isset($ctx['batch'][batch_key($t)])) {
        $parts['一括配信'] = $w['batch'];
    }
    if ($years <= 0) {
        $parts['今年'] = $w['this_year'];
    }
    return ['score' => array_sum($parts), 'reasons' => array_map(fn($k, $v) => $k . ' ' . sprintf('%+d', $v), array_keys($parts), $parts)];
}

// 日付ページの組み立て（同じ日付ならページ・カード画像・構造化データで同じ結果を使う）。
// 戻り値: ['picks' => [unit + score・reasons・pinned]（1件目が注目曲）, 'rest' => [unit か一括配信の枠]（発売日の新しい順）, 'count' => 作品数]
function day_view(string $mmdd, array $tracks): array
{
    static $cache = [];
    if (isset($cache[$mmdd])) {
        return $cache[$mmdd];
    }
    $units = group_versions($tracks);
    $ctx = [
        'batch'      => batch_keys($units),
        'wiki'       => array_flip(wiki_track_ids(array_column($tracks, 'id'))),
        'artistSize' => artist_track_counts(array_unique(array_column($tracks, 'artist'))),
    ];
    $pinned = array_flip(pinned_picks($mmdd));
    $scored = [];
    foreach ($units as $i => $u) {
        $isPinned = isset($pinned[$u['track']['id']]);
        $scored[] = $u + pick_score($u, $ctx) + ['pinned' => $isPinned, 'order' => $isPinned ? $pinned[$u['track']['id']] : PHP_INT_MAX, 'pos' => $i];
    }
    // 固定 → 点数の高い順 → 古い順（同点なら長く聴かれてきた曲を先に）
    usort($scored, fn($a, $b) => [$a['order'], -$a['score'], $a['track']['release_date'], $a['pos']] <=> [$b['order'], -$b['score'], $b['track']['release_date'], $b['pos']]);
    // 同じアーティストはピックに1作品まで（固定したものは除く）
    $picks = [];
    $artists = [];
    foreach ($scored as $u) {
        $artist = mb_strtolower($u['track']['artist']);
        if (count($picks) < PICK_MAX && ($u['pinned'] || !isset($artists[$artist]))) {
            $picks[] = $u;
            $artists[$artist] = true;
        }
    }
    $picked = array_flip(array_map(fn($u) => $u['track']['id'], $picks));
    $rest = array_values(array_filter($units, fn($u) => !isset($picked[$u['track']['id']])));
    return $cache[$mmdd] = ['picks' => $picks, 'rest' => fold_batches($rest, $ctx['batch']), 'count' => count($units)];
}

// 日付ページの注目曲（ピックの1件目）
function featured_track(string $mmdd, array $tracks): ?array
{
    return day_view($mmdd, $tracks)['picks'][0]['track'] ?? null;
}

// 366日（2月29日を含む）のピック（注目曲を含む）に選ばれている作品の id（cron/spotify_backfill.php の優先順に使う）
function pick_track_ids(): array
{
    $ids = [];
    for ($d = new DateTimeImmutable('2024-01-01'); $d->format('Y') === '2024'; $d = $d->modify('+1 day')) {
        $mmdd = $d->format('m-d');
        foreach (day_view($mmdd, tracks_by_mmdd($mmdd))['picks'] as $u) {
            $ids[$u['track']['id']] = true;
        }
    }
    return $ids;
}
