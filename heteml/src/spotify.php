<?php
// Spotify Web API（Client Credentials flow）。lib/spotify.ts と同じ規則で直リンクを探す。
// cron の new_releases（新着のみ）と spotify_backfill（既存曲の補完）で共有する。
// 問い合わせはすべて spotify_request を通す: 間隔をあけて送り、数を数え、429 なら停止が解けるまでの日時をファイルに残す。
// 呼び出し側は spotify_blocked_until() を見て、止められている間は1回も問い合わせない。

require_once __DIR__ . '/http.php';

// 問い合わせの間隔の下限（連続で送らない。2026-11-02 に1日の件数を増やしたら 299曲目で 429・約24時間の停止になった）
const SPOTIFY_MIN_INTERVAL_MS = 1000;
// 停止が解けた直後ちょうどに送らないよう、Retry-After の時刻からさらに空ける
const SPOTIFY_RESUME_MARGIN_SEC = 300;

// 手元の検証で模擬サーバーに向けるときだけ環境変数で差し替える
function spotify_api_base(): string
{
    return getenv('SPOTIFY_API_BASE') ?: 'https://api.spotify.com';
}

function spotify_accounts_base(): string
{
    return getenv('SPOTIFY_ACCOUNTS_BASE') ?: 'https://accounts.spotify.com';
}

function spotify_block_file(): string
{
    return config('log_dir') . '/spotify_blocked_until.json';
}

// 429 で止められている間は、問い合わせを再開してよい時刻（UNIX 時刻）。止められていなければ null
function spotify_blocked_until(): ?int
{
    $data = json_decode((string) @file_get_contents(spotify_block_file()), true);
    $resumeAt = is_array($data) ? (int) ($data['resumeAt'] ?? 0) : 0;
    return $resumeAt > time() ? $resumeAt : null;
}

function spotify_save_block(int $retryAfter): void
{
    $now = time();
    file_put_contents(spotify_block_file(), json_encode([
        'blockedAt'  => date('c', $now),
        'retryAfter' => $retryAfter,
        'until'      => date('c', $now + $retryAfter),
        'resumeAt'   => $now + $retryAfter + SPOTIFY_RESUME_MARGIN_SEC,
        'resume'     => date('c', $now + $retryAfter + SPOTIFY_RESUME_MARGIN_SEC),
    ], JSON_UNESCAPED_SLASHES) . "\n", LOCK_EX);
}

// この実行での問い合わせの集計（cron のログに出す）。quotaExceededAtRequest は 429 が返った問い合わせが何回目か
function &spotify_stats(): array
{
    static $stats = ['requests' => 0, 'byEndpoint' => [], 'byStatus' => [], 'quotaExceededAtRequest' => null, 'retryAfter' => null];
    return $stats;
}

// $endpoint はログの内訳の名前（token・search）
function spotify_request(string $endpoint, string $method, string $url, array $headers, ?string $body = null): array
{
    static $lastAt = 0.0;
    $wait = $lastAt + SPOTIFY_MIN_INTERVAL_MS / 1000 - microtime(true);
    if ($wait > 0) {
        usleep((int) ($wait * 1e6));
    }
    $res = http_request($method, $url, $headers, $body);
    $lastAt = microtime(true);
    $stats = &spotify_stats();
    $stats['requests']++;
    $stats['byEndpoint'][$endpoint] = ($stats['byEndpoint'][$endpoint] ?? 0) + 1;
    $stats['byStatus'][(string) $res['status']] = ($stats['byStatus'][(string) $res['status']] ?? 0) + 1;
    if ($res['status'] === 429 && $stats['quotaExceededAtRequest'] === null) {
        $stats['quotaExceededAtRequest'] = $stats['requests'];
        $stats['retryAfter'] = (int) ($res['headers']['retry-after'] ?? 5);
        spotify_save_block($stats['retryAfter']);
    }
    return $res;
}

function spotify_token(): ?string
{
    static $token = null;
    static $expiresAt = 0;
    if ($token !== null && $expiresAt > time()) {
        return $token;
    }
    $id = config('spotify_client_id');
    $secret = config('spotify_client_secret');
    if ($id === '' || $secret === '') {
        return null;
    }
    $res = spotify_request('token', 'POST', spotify_accounts_base() . '/api/token', [
        'Content-Type: application/x-www-form-urlencoded',
        'Authorization: Basic ' . base64_encode("{$id}:{$secret}"),
    ], 'grant_type=client_credentials');
    $data = http_json($res);
    if ($res['status'] !== 200 || empty($data['access_token'])) {
        return null;
    }
    $token = $data['access_token'];
    $expiresAt = time() + (int) $data['expires_in'] - 60;
    return $token;
}

// 空白も除く（Spotifyの日本語表記は「星野 源」のように姓名の間に空白が入ることがある）
function spotify_normalize(string $s): string
{
    $s = Normalizer::normalize($s, Normalizer::FORM_KC);
    return preg_replace('/[\s\p{Z}\x{FEFF}]+/u', '', mb_strtolower($s));
}

function spotify_artist_match(array $spotifyArtists, string $queryArtist): bool
{
    $q = spotify_normalize($queryArtist);
    foreach ($spotifyArtists as $a) {
        $n = spotify_normalize((string) ($a['name'] ?? ''));
        if ($n !== '' && (str_contains($q, $n) || str_contains($n, $q))) {
            return true;
        }
    }
    return false;
}

// 曲名が近いだけでは別アーティストの同名曲を拾うため、アーティスト名か発売日のどちらかの一致を必須にする。
// アーティスト名は Accept-Language: ja で日本語表記を受け取って比べるが、日本語表記が登録されていない
// アーティストもいるため、発売日（Spotifyで日まで分かる場合 YYYY-MM-DD のみ）の一致でも同じ曲とみなす。
// $item は検索結果の曲（発売日は album.release_date）かアルバム（発売日は release_date）
function spotify_is_same_track(array $item, string $title, string $artist, ?string $releaseDate): bool
{
    $titleNorm = spotify_normalize($title);
    $spTitle = spotify_normalize((string) ($item['name'] ?? ''));
    if ($spTitle === '' || !(str_contains($titleNorm, $spTitle) || str_contains($spTitle, $titleNorm))) {
        return false;
    }
    if (spotify_artist_match($item['artists'] ?? [], $artist)) {
        return true;
    }
    $spDate = $item['album']['release_date'] ?? $item['release_date'] ?? null;
    return $releaseDate !== null && $releaseDate !== '' && $spDate === $releaseDate;
}

// 一致する曲が見つからなければ url は null（検索結果の先頭を代わりに採用すると、無関係な曲の直リンクが入るため。
// 呼び出し側は検索URLのままにしておく）。429（QUOTA_EXCEEDED）なら retry_after に Retry-After の秒数が入り、
// 呼び出し側はそこで打ち切る（これ以上呼んでも無駄なため）。
// アルバム（$isAlbum。src/releases.php の release_kind）はまずアルバムとして探してアルバムへの直リンクにし、
// 見つからなければ曲として探す（作品名と同じ名前の収録曲につながる）。
// $pass: all は全部の検索、first は最初の厳密な検索（曲名とアーティスト名を引用符で指定）の1回だけ、rest は first 以外の残り。
// 戻り値の step は、全部の検索のうち何番目で見つかったか（1 が最初の厳密な検索）
function spotify_search(string $token, string $title, string $artist, ?string $releaseDate, bool $isAlbum = false, string $pass = 'all'): array
{
    // Apple Music の作品名に付く「 - Single」「 - EP」が残っていると Spotify の検索結果が0件になる
    $title = preg_replace('/\s+-\s+(Single|EP)$/iu', '', $title);
    $plan = [];
    foreach ($isAlbum ? ['album', 'track'] : ['track'] as $type) {
        foreach (["{$type}:\"{$title}\" artist:\"{$artist}\"", "{$type}:{$title} artist:{$artist}", "{$artist} {$title}"] as $query) {
            $plan[] = [$type, $query];
        }
    }
    $offset = $pass === 'rest' ? 1 : 0;
    $plan = $pass === 'first' ? array_slice($plan, 0, 1) : array_slice($plan, $offset);
    foreach ($plan as $i => [$type, $query]) {
        $url = spotify_api_base() . '/v1/search?' . http_build_query([
            'q' => $query, 'type' => $type, 'market' => 'JP', 'limit' => '10',
        ], '', '&', PHP_QUERY_RFC3986);
        // Accept-Language を付けないとアーティスト名がローマ字表記（星野源 → Gen Hoshino）で返り、
        // DB（Apple Musicの日本語表記）と一致しなくなる
        $res = spotify_request('search', 'GET', $url, ["Authorization: Bearer {$token}", 'Accept-Language: ja']);
        if ($res['status'] === 429) {
            return ['url' => null, 'retry_after' => (int) ($res['headers']['retry-after'] ?? 5), 'step' => null];
        }
        if ($res['status'] !== 200) {
            continue;
        }
        foreach (http_json($res)["{$type}s"]['items'] ?? [] as $item) {
            $link = is_array($item) ? ($item['external_urls']['spotify'] ?? null) : null; // 結果に null が混ざることがある
            if ($link && spotify_is_same_track($item, $title, $artist, $releaseDate)) {
                return ['url' => $link, 'retry_after' => null, 'step' => $i + 1 + $offset];
            }
        }
    }
    return ['url' => null, 'retry_after' => null, 'step' => null];
}
