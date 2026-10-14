<?php
// サイトの入口。.htaccess が「実在するファイル以外のすべての URL」をここに回す。URL は Next.js 版と同じ

// 手元の開発サーバー（php -S ... heteml/public/index.php）では、実在するファイル（CSS・JS・api/*.php）はそのまま返す
if (PHP_SAPI === 'cli-server' && is_file(__DIR__ . parse_url($_SERVER['REQUEST_URI'], PHP_URL_PATH))) {
    return false;
}

require_once __DIR__ . '/../src/bootstrap.php';
require_once __DIR__ . '/../src/pages.php';

$uri = $_SERVER['REQUEST_URI'] ?? '/';
$path = rawurldecode(parse_url($uri, PHP_URL_PATH) ?? '/');
$base = rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
if ($base !== '' && str_starts_with($path, $base)) {
    $path = substr($path, strlen($base));
}
$path = $path === '' ? '/' : $path;

// 末尾の「/」は外した URL へ転送する（Next.js 版と同じ 308）
if ($path !== '/' && str_ends_with($path, '/')) {
    $query = parse_url($uri, PHP_URL_QUERY);
    header('Location: ' . u(rtrim($path, '/')) . ($query ? "?{$query}" : ''), true, 308);
    exit;
}

try {
    if ($path === '/') {
        page_home();
    } elseif (preg_match('#^/date/([^/]+)$#', $path, $m)) {
        page_date($m[1]);
    } elseif (preg_match('#^/track/([^/]+)/opengraph-image$#', $path, $m)) {
        require_once __DIR__ . '/../src/og_image.php';
        og_image($m[1]);
    } elseif (preg_match('#^/track/([^/]+)$#', $path, $m)) {
        page_track($m[1]);
    } elseif (preg_match('#^/artist/(.+)$#s', $path, $m)) {
        page_artist($m[1]);
    } elseif ($path === '/artist' && isset($_GET['name']) && is_string($_GET['name']) && $_GET['name'] !== '') {
        // 名前に「/」を含むアーティスト（site.php の artist_url）
        page_artist($_GET['name']);
    } elseif ($path === '/search') {
        page_search(is_string($_GET['q'] ?? null) ? $_GET['q'] : '');
    } elseif ($path === '/terms' || $path === '/privacy') {
        page_legal(substr($path, 1));
    } else {
        page_not_found();
    }
} catch (Throwable $e) {
    error_log('[site] ' . $e);
    http_response_code(500);
    header('Content-Type: text/html; charset=utf-8');
    echo '<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><title>Release Tune</title></head>',
        '<body style="background:#0f0f0f;color:#b3b3b3;font-family:sans-serif;text-align:center;padding:80px 20px">',
        '<p>ただいま表示できません。時間をおいて再度お試しください。</p></body></html>';
}
