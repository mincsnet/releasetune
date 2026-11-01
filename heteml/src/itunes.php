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

// 作品 ID の一覧 → [作品 ID => 収録曲（Lookup の曲の結果）の配列]。entity=song を付けると作品ごとに収録曲が返る
// （アルバム200作品で約17秒・約5MB、2026-11-01 実測。件数の多い一括補完では1回の件数を減らして呼ぶ）。
// 呼び出しに失敗したら null
function itunes_lookup_songs(array $albumIds): ?array
{
    $res = http_request('GET', 'https://itunes.apple.com/lookup?country=jp&entity=song&limit=200&id=' . implode(',', array_unique($albumIds)), [], null, 60);
    $data = $res['status'] === 200 ? http_json($res) : null;
    if (!is_array($data) || !isset($data['results'])) {
        return null;
    }
    $out = [];
    foreach ($data['results'] as $item) {
        if (($item['wrapperType'] ?? '') === 'track' && ($item['kind'] ?? '') === 'song') {
            $out[(string) $item['collectionId']][] = $item;
        }
    }
    return $out;
}

// 曲名の比較用（全角半角・大文字小文字・空白をそろえる。$stripBrackets なら括弧の中（feat. など）も外す）
function itunes_title_key(string $s, bool $stripBrackets): string
{
    $s = Normalizer::normalize($s, Normalizer::FORM_KC);
    if ($stripBrackets) {
        $s = preg_replace('/\s*[(\[（【][^)\]）】]*[)\]）】]/u', '', $s);
    }
    return preg_replace('/[\s\p{Z}]+/u', '', mb_strtolower($s));
}

// 試聴に使う曲: 曲名が作品名と同じ曲（「A / B」のような両A面は先頭の A）、なければ1枚目の1曲目。
// まず括弧も含めて同じ曲（「VERGE OF LOVE (English Version)」は English Version）、なければ括弧を外して同じ曲
// （「Flamingo (feat. …)」など。インスト・カラオケは除く）。
// 例: アルバム「朝顔」は5曲目の「朝顔」、「Flamingo / TEENAGE RIOT - Single」は1曲目の「Flamingo」。試聴のない曲は選ばない
function itunes_preview_song(array $songs, string $title): ?array
{
    $songs = array_values(array_filter($songs, fn($s) => !empty($s['previewUrl'])));
    if (!$songs) {
        return null;
    }
    usort($songs, fn($a, $b) => [$a['discNumber'] ?? 1, $a['trackNumber'] ?? 0] <=> [$b['discNumber'] ?? 1, $b['trackNumber'] ?? 0]);
    $head = explode(' / ', preg_replace('/\s+-\s+(Single|EP)$/iu', '', $title))[0];
    foreach ([false, true] as $strip) {
        $want = itunes_title_key($head, $strip);
        foreach ($songs as $s) {
            $name = (string) ($s['trackName'] ?? '');
            if ($strip && preg_match('/instrumental|inst\.|off vocal|karaoke|カラオケ/iu', $name)) {
                continue;
            }
            if ($want !== '' && itunes_title_key($name, $strip) === $want) {
                return $s;
            }
        }
    }
    return $songs[0];
}
