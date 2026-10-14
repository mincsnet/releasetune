<?php
// Spotify Web API（Client Credentials flow）。lib/spotify.ts と同じ規則で直リンクを探す。
// cron の new_releases（新着のみ）と spotify_backfill（既存曲の補完）で共有する。

require_once __DIR__ . '/http.php';

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
    $res = http_request('POST', 'https://accounts.spotify.com/api/token', [
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
    return $releaseDate !== null && $releaseDate !== '' && ($item['album']['release_date'] ?? null) === $releaseDate;
}

// 一致する曲が見つからなければ url は null（検索結果の先頭を代わりに採用すると、無関係な曲の直リンクが入るため。
// 呼び出し側は検索URLのままにしておく）。429（QUOTA_EXCEEDED）なら retry_after に Retry-After の秒数が入り、
// 呼び出し側はそこで打ち切る（これ以上呼んでも無駄なため）
function spotify_search(string $token, string $title, string $artist, ?string $releaseDate): array
{
    // Apple Music の作品名に付く「 - Single」「 - EP」が残っていると Spotify の検索結果が0件になる
    $title = preg_replace('/\s+-\s+(Single|EP)$/iu', '', $title);
    $queries = [
        "track:\"{$title}\" artist:\"{$artist}\"",
        "track:{$title} artist:{$artist}",
        "{$artist} {$title}",
    ];
    foreach ($queries as $query) {
        $url = 'https://api.spotify.com/v1/search?' . http_build_query([
            'q' => $query, 'type' => 'track', 'market' => 'JP', 'limit' => '10',
        ], '', '&', PHP_QUERY_RFC3986);
        // Accept-Language を付けないとアーティスト名がローマ字表記（星野源 → Gen Hoshino）で返り、
        // DB（Apple Musicの日本語表記）と一致しなくなる
        $res = http_request('GET', $url, ["Authorization: Bearer {$token}", 'Accept-Language: ja']);
        if ($res['status'] === 429) {
            return ['url' => null, 'retry_after' => (int) ($res['headers']['retry-after'] ?? 5)];
        }
        if ($res['status'] !== 200) {
            continue;
        }
        foreach (http_json($res)['tracks']['items'] ?? [] as $item) {
            $link = $item['external_urls']['spotify'] ?? null;
            if ($link && spotify_is_same_track($item, $title, $artist, $releaseDate)) {
                return ['url' => $link, 'retry_after' => null];
            }
        }
    }
    return ['url' => null, 'retry_after' => null];
}
