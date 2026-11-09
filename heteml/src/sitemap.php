<?php
// robots.txt と sitemap（索引 ＋ 日付・アーティスト・紹介文のある楽曲・楽曲の子 sitemap）。
// URL は常に本番（SITE_ORIGIN）。<lastmod> は実際に内容が変わった日時が分かるもの（紹介文のある楽曲）にだけ付ける（推測の日付を書かない）

require_once __DIR__ . '/site.php';
require_once __DIR__ . '/tracks.php';

// 楽曲の子 sitemap 1ファイルあたりの件数（上限は 50,000）
const SITEMAP_TRACKS_PER_FILE = 10000;

// /robots.txt・/sitemap.xml・/sitemap-*.xml の振り分け（index.php から呼ぶ）
function sitemap_route(string $path): void
{
    if ($path === '/robots.txt') {
        robots_txt();
    } elseif ($path === '/sitemap.xml') {
        sitemap_index();
    } elseif ($path === '/sitemap-dates.xml') {
        sitemap_dates();
    } elseif ($path === '/sitemap-artists.xml') {
        sitemap_artists();
    } elseif ($path === '/sitemap-notes.xml') {
        sitemap_notes();
    } elseif (!preg_match('#^/sitemap-tracks-(\d+)\.xml$#', $path, $m) || !sitemap_tracks((int) $m[1])) {
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
    $files = ['sitemap-dates.xml', 'sitemap-artists.xml', 'sitemap-notes.xml'];
    for ($i = 1, $n = (int) ceil(track_count() / SITEMAP_TRACKS_PER_FILE); $i <= $n; $i++) {
        $files[] = "sitemap-tracks-{$i}.xml";
    }
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

function sitemap_artists(): void
{
    sitemap_output('urlset', 'url', array_map(fn($name) => SITE_ORIGIN . artist_path($name), artist_names()));
}

// 紹介文のある楽曲（公開の新しい順）。<lastmod> は紹介文の公開・リリース日の修正の新しいほう（note_track_lastmods）
function sitemap_notes(): void
{
    $urls = [];
    foreach (note_track_lastmods() as $id => $lastmod) {
        $urls[] = ['loc' => SITE_ORIGIN . '/track/' . encode_uri_component((string) $id), 'lastmod' => $lastmod];
    }
    sitemap_output('urlset', 'url', $urls);
}

// 紹介文のない楽曲。1 から数える。範囲外は 404
function sitemap_tracks(int $page): bool
{
    $ids = $page >= 1 ? track_ids(($page - 1) * SITEMAP_TRACKS_PER_FILE, SITEMAP_TRACKS_PER_FILE) : [];
    if (!$ids) {
        return false;
    }
    sitemap_output('urlset', 'url', array_map(fn($id) => SITE_ORIGIN . '/track/' . encode_uri_component($id), $ids));
    return true;
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
