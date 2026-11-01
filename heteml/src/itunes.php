<?php
// iTunes Lookup API（作品 ID から作品の情報を引く）。新着 cron と bin/ の一括補完で使う

require_once __DIR__ . '/http.php';

// 1回の Lookup に渡す件数（200件で約1秒・約200KB、2026-10-24 実測）
const ITUNES_LOOKUP_BATCH = 200;

// Apple の URL（…/album/曲名/1526094901?i=…&uo=4）の作品 ID。取れなければ id
// （ほぼ id と同じだが、違う曲が1件ある。2026-10-24 調査）
function itunes_album_id(array $row): string
{
    return preg_match('#/album/(?:[^/?]+/)?(\d+)#', (string) ($row['apple'] ?? ''), $m) ? $m[1] : (string) $row['id'];
}

// 作品 ID の一覧（ITUNES_LOOKUP_BATCH 件まで）→ [作品 ID => Lookup の作品の結果]。
// 照合は作品 ID の一致だけ（返ってこなかった作品は入らない）。呼び出しに失敗したら null
function itunes_lookup_collections(array $albumIds): ?array
{
    $res = http_request('GET', 'https://itunes.apple.com/lookup?country=jp&id=' . implode(',', array_unique($albumIds)), [], null, 60);
    $data = $res['status'] === 200 ? http_json($res) : null;
    if (!is_array($data) || !isset($data['results'])) {
        return null;
    }
    $out = [];
    foreach ($data['results'] as $item) {
        if (($item['wrapperType'] ?? '') === 'collection') {
            $out[(string) $item['collectionId']] = $item;
        }
    }
    return $out;
}
