<?php
// robots.txt と sitemap（索引 ＋ 区分ごとの子 sitemap）。
// クロール指示書 Phase 1（2026-11-09 Muse 承認）: 載せるのは優先するページだけ。外したページも 200 のまま・noindex なし・内部リンクもそのまま。
//   sitemap-dates.xml    トップ・/about・366日（全件）
//   sitemap-artists.xml  アーティスト。2曲以上、または優先する楽曲を持つ組だけ
//   sitemap-notes.xml    紹介文のある楽曲
//   sitemap-picks.xml    日付ページのピック（注目曲を含む）に選ばれている楽曲
//   sitemap-recent.xml   リリース日が直近90日の楽曲
// 楽曲は上の順で最初に当てはまった区分にだけ載せる（同じ URL を二重に載せない）。以前の sitemap-tracks-N.xml は 404。
// URL は常に本番（SITE_ORIGIN）。<lastmod> は実際に内容が変わった日時が分かるもの（紹介文のある楽曲）にだけ付ける（推測の日付を書かない）

require_once __DIR__ . '/site.php';
require_once __DIR__ . '/tracks.php';
require_once __DIR__ . '/releases.php';

// 「直近の楽曲」の日数（リリース日が今日を含めてこの日数以内）
const SITEMAP_RECENT_DAYS = 90;

// 楽曲の子 sitemap の名前 => 区分（sitemap_track_sections のキー）
const SITEMAP_TRACK_FILES = ['sitemap-notes.xml' => 'notes', 'sitemap-picks.xml' => 'picks', 'sitemap-recent.xml' => 'recent'];

// /robots.txt・/sitemap.xml・/sitemap-*.xml の振り分け（index.php から呼ぶ）
function sitemap_route(string $path): void
{
    $file = ltrim($path, '/');
    if ($path === '/robots.txt') {
        robots_txt();
    } elseif ($path === '/sitemap.xml') {
        sitemap_index();
    } elseif ($path === '/sitemap-dates.xml') {
        sitemap_dates();
    } elseif ($path === '/sitemap-artists.xml') {
        sitemap_artists();
    } elseif (isset(SITEMAP_TRACK_FILES[$file])) {
        sitemap_tracks(SITEMAP_TRACK_FILES[$file]);
    } else {
        page_not_found();
    }
}

function robots_txt(): void
{
    header('Content-Type: text/plain; charset=utf-8');
    echo "User-agent: *\nAllow: /\n\nSitemap: " . SITE_ORIGIN . "/sitemap.xml\n";
}

function sitemap_index(): void
{
    $files = array_merge(['sitemap-dates.xml', 'sitemap-artists.xml'], array_keys(SITEMAP_TRACK_FILES));
    sitemap_output('sitemapindex', 'sitemap', array_map(fn($f) => SITE_ORIGIN . "/{$f}", $files));
}

// トップ・このサイトについてと 366 日（2月29日を含む）
function sitemap_dates(): void
{
    $urls = [SITE_ORIGIN . '/', SITE_ORIGIN . '/about'];
    for ($d = new DateTimeImmutable('2024-01-01'); $d->format('Y') === '2024'; $d = $d->modify('+1 day')) {
        $urls[] = SITE_ORIGIN . '/date/' . $d->format('m-d');
    }
    sitemap_output('urlset', 'url', $urls);
}

// 2曲以上のアーティストと、1曲だけでもその曲が優先する楽曲（紹介文・ピック・直近90日）のアーティスト。作品数の多い順
function sitemap_artists(): void
{
    $ids = array_merge(...array_map('array_keys', array_values(sitemap_track_sections())));
    $priorityArtists = array_flip(track_artists_lc(array_map('strval', $ids)));
    $urls = [];
    foreach (artist_name_counts() as $lc => $a) {
        if ($a['count'] >= 2 || isset($priorityArtists[$lc])) {
            $urls[] = SITE_ORIGIN . artist_path($a['name']);
        }
    }
    sitemap_output('urlset', 'url', $urls);
}

function sitemap_tracks(string $section): void
{
    $urls = [];
    foreach (sitemap_track_sections()[$section] as $id => $lastmod) {
        $urls[] = ['loc' => SITE_ORIGIN . '/track/' . encode_uri_component((string) $id), 'lastmod' => $lastmod];
    }
    sitemap_output('urlset', 'url', $urls);
}

// 区分 => [楽曲 id => lastmod（UTC の 'Y-m-d H:i:s' か null）]。1曲は最初に当てはまった区分にだけ入る
function sitemap_track_sections(): array
{
    static $sections = null;
    if ($sections !== null) {
        return $sections;
    }
    $notes = note_track_lastmods();   // 公開の新しい順。lastmod は紹介文の公開・リリース日の修正の新しいほう
    $picks = array_diff_key(array_fill_keys(sitemap_pick_ids(), null), $notes);
    $recent = array_diff_key(array_fill_keys(recent_track_ids(SITEMAP_RECENT_DAYS), null), $notes, $picks);
    return $sections = ['notes' => $notes, 'picks' => $picks, 'recent' => $recent];
}

// ピックの楽曲 id（pick_track_ids。366日分の日付ページを組み立てるので数秒かかる）。
// cache/sitemap/picks-{今日}.json に1日1回だけ作って使い回す（ピックは周年の点数が年で変わるほか、紹介文などのデータでも変わる）
function sitemap_pick_ids(): array
{
    $dir = __DIR__ . '/../cache/sitemap';
    $file = $dir . '/picks-' . date('Y-m-d') . '.json';
    $ids = is_file($file) ? json_decode((string) file_get_contents($file), true) : null;
    if (!is_array($ids)) {
        $ids = array_map('strval', array_keys(pick_track_ids()));
        if (!is_dir($dir)) {
            mkdir($dir, 0755, true);
        }
        file_put_contents($file . '.tmp', json_encode($ids));
        rename($file . '.tmp', $file);
        foreach (glob($dir . '/picks-*.json') ?: [] as $old) {
            if ($old !== $file) {
                @unlink($old);
            }
        }
    }
    return $ids;
}

// $urls の要素は URL の文字列か ['loc' => URL, 'lastmod' => UTC の 'Y-m-d H:i:s' か null]
function sitemap_output(string $root, string $item, array $urls): void
{
    header('Content-Type: application/xml; charset=utf-8');
    echo '<?xml version="1.0" encoding="UTF-8"?>', "\n", '<', $root, ' xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">', "\n";
    foreach ($urls as $url) {
        $loc = is_array($url) ? $url['loc'] : $url;
        $lastmod = is_array($url) && $url['lastmod'] !== null
            ? '<lastmod>' . (new DateTimeImmutable($url['lastmod'], new DateTimeZone('UTC')))->format('c') . '</lastmod>' : '';
        echo '<', $item, '><loc>', htmlspecialchars($loc, ENT_XML1 | ENT_QUOTES, 'UTF-8'), '</loc>', $lastmod, '</', $item, ">\n";
    }
    echo '</', $root, ">\n";
}
