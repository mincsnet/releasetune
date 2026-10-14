<?php
// YouTube 動画IDの検索（app/api/cron/new-releases/route.ts・fetch_youtube.py と同じ規則）

require_once __DIR__ . '/http.php';

function youtube_is_japanese(string $text): bool
{
    return (bool) preg_match('/[\x{3040}-\x{30FF}\x{4E00}-\x{9FFF}]/u', $text);
}

function youtube_clean_title(string $title): string
{
    return trim(preg_replace('/\s*[-–]\s*(Single|EP|Album|Maxi Single|CD|DVD).*$/iu', '', $title));
}

// 戻り値: ['id' => 動画ID, 'verified' => 公式らしいか] または null（API キーなし・失敗・0件）
function youtube_search(string $title, string $artist): ?array
{
    $apiKey = config('youtube_api_key');
    if ($apiKey === '') {
        return null;
    }
    $qTitle = youtube_clean_title($title);
    $hasJa = youtube_is_japanese($title) || youtube_is_japanese($artist);
    $query = $hasJa ? "{$artist} {$qTitle} 公式" : "{$artist} {$qTitle} official";

    $url = 'https://www.googleapis.com/youtube/v3/search?' . http_build_query([
        'part' => 'snippet', 'q' => $query, 'type' => 'video', 'maxResults' => '5',
        'regionCode' => 'JP', 'relevanceLanguage' => 'ja', 'key' => $apiKey,
    ], '', '&', PHP_QUERY_RFC3986);
    $res = http_request('GET', $url);
    if ($res['status'] !== 200) {
        return null;
    }
    $items = http_json($res)['items'] ?? [];
    if (!$items) {
        return null;
    }
    $officialKw = ['official', '公式', 'vevo', mb_strtolower($artist)];
    foreach ($items as $item) {
        $channel = mb_strtolower((string) ($item['snippet']['channelTitle'] ?? ''));
        $vidTitle = mb_strtolower((string) ($item['snippet']['title'] ?? ''));
        foreach ($officialKw as $kw) {
            if ($kw !== '' && (str_contains($channel, $kw) || str_contains($vidTitle, $kw))) {
                return ['id' => $item['id']['videoId'], 'verified' => true];
            }
        }
    }
    return ['id' => $items[0]['id']['videoId'], 'verified' => false];
}
