<?php
// PHP 版サイトの共通部品（Next.js 版の lib/utils.ts と components/*.tsx からの移植）。
// HTML の構造とクラス名は Next.js 版と同じにする（public/assets/site.css は Next.js 版の CSS を接頭辞付きで移したもの）

const SITE_ORIGIN = 'https://releasetune.com';
const GA_ID = 'G-3SDZ478Y78';

function h($s): string
{
    return htmlspecialchars((string) $s, ENT_QUOTES | ENT_SUBSTITUTE, 'UTF-8');
}

// サイト内の URL。初期ドメインの /releasetune/ のようにサブフォルダで動かすときも同じコードで動くよう、
// 入口（index.php）の置き場所を先頭に付ける
function u(string $path): string
{
    static $base = null;
    $base ??= rtrim(str_replace('\\', '/', dirname($_SERVER['SCRIPT_NAME'] ?? '/')), '/');
    return $base . $path;
}

// JavaScript の encodeURIComponent と同じ（rawurlencode は ! ' ( ) * も変換するので戻す）
function encode_uri_component(string $s): string
{
    return strtr(rawurlencode($s), ['%21' => '!', '%2A' => '*', '%27' => "'", '%28' => '(', '%29' => ')']);
}

// アーティストページの URL。名前に「/」があると %2F になり、ヘテムルの Apache が 404 を返す
// （.htaccess では変えられない設定）ので、その名前だけクエリ文字列で渡す
function artist_url(string $name): string
{
    return str_contains($name, '/') ? u('/artist?name=' . encode_uri_component($name)) : u('/artist/' . encode_uri_component($name));
}

function today_mmdd(): string
{
    return date('m-d');
}

function current_year(): int
{
    return (int) date('Y');
}

function years_ago(string $releaseDate): int
{
    return current_year() - (int) substr($releaseDate, 0, 4);
}

function format_date_ja(string $releaseDate): string
{
    [$y, $m, $d] = explode('-', $releaseDate);
    return $y . '年' . (int) $m . '月' . (int) $d . '日';
}

function parse_mmdd(string $mmdd): array
{
    [$m, $d] = explode('-', $mmdd);
    return [(int) $m, (int) $d];
}

// SNS（シェア文・カード画像）用の曲名。Apple Music が付ける末尾の「 - Single」は外す（「 - EP」は残す）
function social_title(string $title): string
{
    return preg_replace('/ - Single$/u', '', $title);
}

// 注目曲の選び方。Next.js 版の JavaScript（hash = (hash * 31 + charCode) | 0）と同じ 32 ビットの計算にして、同じ曲を選ぶ
function featured_index(string $mmdd, int $count): int
{
    if ($count === 0) {
        return 0;
    }
    $hash = 0;
    foreach (str_split($mmdd) as $ch) {
        $hash = ($hash * 31 + ord($ch)) & 0xFFFFFFFF;
        if ($hash >= 0x80000000) {
            $hash -= 0x100000000;
        }
    }
    return abs($hash) % $count;
}

// ── 部品 ──────────────────────────────────────────────

// components/Jacket.tsx。画像を読めなければ ♪ の代替表示にする（site.js の rtJacketError）
function jacket(?string $src, string $title, int $size = 68, bool $fullWidth = false): string
{
    $box = "var(--jacket-size, {$size}px)";
    $container = $fullWidth
        ? 'width:100%;aspect-ratio:1/1;position:relative;border-radius:4px;overflow:hidden;background:linear-gradient(135deg, #c8a84b33 0%, #1e1e1e 100%)'
        : "width:{$box};height:{$box};flex-shrink:0;border-radius:4px;overflow:hidden;position:relative";
    $fallback = $container . ';display:flex;align-items:center;justify-content:center;font-size:'
        . ($fullWidth ? '4rem' : "calc({$box} * 0.3)") . ';color:#c8a84bcc';
    if (!$src) {
        return '<div style="' . h($fallback) . '">♪</div>';
    }
    return '<div style="' . h($container) . '" data-fallback-style="' . h($fallback) . '">'
        . '<img alt="' . h($title) . '" loading="lazy" decoding="async" src="' . h($src) . '"'
        . ' style="position:absolute;height:100%;width:100%;left:0;top:0;right:0;bottom:0;object-fit:cover;color:transparent"'
        . ' onerror="rtJacketError(this)"></div>';
}

// クリック時に GA4 のイベントを送る属性（site.js が拾う）
function ga_attrs(string $event, array $params): string
{
    return ' data-ga="' . h($event) . '" data-ga-params="' . h(json_encode($params, JSON_UNESCAPED_UNICODE)) . '"';
}

function view_track_ga(array $t): string
{
    return ga_attrs('view_track', ['track_id' => $t['id'], 'track_title' => $t['title'], 'artist' => $t['artist']]);
}

const ICON_PATHS = [
    'spotify' => 'M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.840c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.160 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z',
    'apple' => 'M23.994 6.124a9.23 9.23 0 00-.24-2.19c-.317-1.31-1.062-2.31-2.18-3.043a5.022 5.022 0 00-1.877-.726 10.496 10.496 0 00-1.564-.15c-.05-.003-.098-.01-.146-.013H5.991c-.05.003-.098.01-.146.013-.5.03-1.002.07-1.47.16A5.065 5.065 0 002.42.87C1.327 1.602.583 2.6.24 3.913A9.77 9.77 0 00.005 6.122C0 6.220-.002 6.318 0 6.416v11.19c.002.09.006.18.012.27.06 1.04.28 2.02.79 2.920a5.06 5.06 0 002.87 2.28c.98.33 1.99.43 3.02.45.14.01.28.01.42.01h10.88c.14 0 .28 0 .42-.01 1.03-.02 2.04-.12 3.02-.45a5.06 5.06 0 002.87-2.28c.51-.9.73-1.88.79-2.92.006-.09.01-.18.012-.27V6.416c.002-.098 0-.196-.005-.292zM12 17.5c-3.038 0-5.5-2.462-5.5-5.5S8.962 6.5 12 6.5s5.5 2.462 5.5 5.5-2.462 5.5-5.5 5.5zm6.5-9.75a1.25 1.25 0 110-2.5 1.25 1.25 0 010 2.5zM12 8.5a3.5 3.5 0 100 7 3.5 3.5 0 000-7z',
    'youtube' => 'M23.495 6.205a3.007 3.007 0 00-2.088-2.088c-1.87-.501-9.396-.501-9.396-.501s-7.507-.01-9.396.501A3.007 3.007 0 00.527 6.205a31.247 31.247 0 00-.522 5.805 31.247 31.247 0 00.522 5.783 3.007 3.007 0 002.088 2.088c1.868.502 9.396.502 9.396.502s7.506 0 9.396-.502a3.007 3.007 0 002.088-2.088 31.247 31.247 0 00.5-5.783 31.247 31.247 0 00-.5-5.805zM9.609 15.601V8.408l6.264 3.602z',
    'amazon' => 'M.045 18.02c.072-.116.187-.124.348-.022 3.636 2.11 7.594 3.166 11.87 3.166 2.852 0 5.668-.533 8.447-1.595l.315-.14c.138-.06.234-.1.293-.13.226-.088.39-.046.525.13.12.174.09.336-.12.48-.256.19-.6.41-1.006.654-1.244.743-2.640 1.316-4.185 1.726a17.617 17.617 0 01-10.951-.577 17.77 17.77 0 01-5.43-3.35c-.1-.105-.12-.2-.1-.32zm7.647-2.38c-.25-.15-.19-.356.12-.405l.35-.028c1.020-.097 2.070-.105 3.12-.025.62.047 1.25.12 1.87.218l.35.066c.167.044.23.155.197.33-.02.082-.065.136-.14.165a.336.336 0 01-.216.01 16.458 16.458 0 00-3.36-.348 15.916 15.916 0 00-2.29.217zm8.535-9.622c.57.022 1.01.204 1.32.544.3.34.45.78.44 1.318l-.01.123c-.02.247-.07.5-.15.756-.3.97-.87 1.773-1.71 2.41-.84.636-1.76.965-2.77.988-.48.01-.9-.107-1.27-.35-.37-.24-.62-.57-.76-.98-.14-.41-.14-.85.01-1.31.15-.47.43-.87.84-1.19.41-.32.9-.52 1.46-.6a4.773 4.773 0 011.56.03l.55.12.06-.35c.04-.2.05-.41.05-.62 0-.44-.11-.79-.33-1.05-.22-.26-.54-.39-.97-.39-.34 0-.63.08-.88.24a1.18 1.18 0 00-.5.66l-.05.16c-.05.17-.16.25-.33.25h-.74c-.19 0-.28-.1-.28-.3 0-.01.01-.04.02-.09.14-.63.47-1.12 1-1.46.52-.34 1.14-.51 1.86-.49zm-1.31 5.11c.33 0 .64-.08.93-.23.29-.15.52-.38.69-.69.17-.31.26-.66.26-1.060l-.01-.16-.48-.11a3.52 3.52 0 00-.98-.06c-.43.04-.79.19-1.07.45-.29.26-.43.58-.43.97 0 .33.1.59.3.78.2.19.47.28.8.28v-.17z',
];

// 配信サービスのアイコン。曲の数だけ同じ SVG を埋め込むと日付ページが 500KB を超えるので、
// ページ先頭で1回だけ <symbol> として定義し（icon_defs）、各ボタンは <use> で参照する（見た目は同じ）
function icon_defs(): string
{
    $out = '<svg width="0" height="0" style="position:absolute" aria-hidden="true">';
    foreach (ICON_PATHS as $name => $d) {
        $out .= '<symbol id="i-' . $name . '" viewBox="0 0 24 24"><path d="' . $d . '"></path></symbol>';
    }
    return $out . '</svg>';
}

function icon(string $name, int $s): string
{
    return '<svg width="' . $s . '" height="' . $s . '" viewBox="0 0 24 24" fill="currentColor"><use href="#i-' . $name . '"></use></svg>';
}

// components/SvcLinks.tsx。YouTube Music は動画IDがあれば music.youtube.com の直リンクを優先する
function svc_items(array $t): array
{
    $yt = !empty($t['youtube_id']) ? 'https://music.youtube.com/watch?v=' . $t['youtube_id'] : ($t['youtube'] ?? null);
    return array_values(array_filter([
        !empty($t['spotify']) ? ['href' => $t['spotify'], 'color' => '#1DB954', 'icon' => 'spotify', 'label' => 'Spotify'] : null,
        !empty($t['apple']) ? ['href' => $t['apple'], 'color' => '#fc3c44', 'icon' => 'apple', 'label' => 'Apple Music'] : null,
        !empty($t['amazon']) ? ['href' => $t['amazon'], 'color' => '#00A8E1', 'icon' => 'amazon', 'label' => 'Amazon Music'] : null,
        $yt ? ['href' => $yt, 'color' => '#FF0000', 'icon' => 'youtube', 'label' => 'YouTube Music'] : null,
    ]));
}

function svc_link(array $item, array $t, bool $large): string
{
    return '<a href="' . h($item['href']) . '" target="_blank" rel="noopener noreferrer" class="c-svc' . ($large ? ' c-svc-large' : '') . '"'
        . ga_attrs('click_streaming', ['service' => $item['label'], 'track_title' => $t['title'], 'artist' => $t['artist']]) . '>'
        . '<span style="color:' . $item['color'] . ';display:flex;align-items:center">' . icon($item['icon'], $large ? 14 : 12) . '</span>'
        . h($item['label']) . '</a>';
}

function svc_grid(array $t): string
{
    return '<div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">'
        . implode('', array_map(fn($i) => svc_link($i, $t, true), svc_items($t))) . '</div>';
}

function track_svc_links(array $t): string
{
    return '<div style="display:flex;gap:6px;flex-wrap:wrap">'
        . implode('', array_map(fn($i) => svc_link($i, $t, false), svc_items($t))) . '</div>';
}

// 一覧の年見出し（発売年が変わるところに入れる）
function year_header(string $prefix, string $year): string
{
    return '<div class="' . $prefix . '-yearHeader"><span class="' . $prefix . '-yearLabel">' . h($year) . '</span>'
        . '<div class="' . $prefix . '-yearRule"></div>'
        . '<span class="' . $prefix . '-yearAgo">' . (current_year() - (int) $year) . '年前</span></div>';
}

function site_header(): string
{
    return '<header class="hd-header"><a class="hd-logo" href="' . h(u('/')) . '"><span class="hd-logoRelease">Release</span><span class="hd-logoTune">Tune</span></a>'
        . '<div style="display:flex;align-items:center;gap:12px"><span class="hd-tagline">今日はあの曲のリリース日</span>'
        . '<a href="' . h(u('/search')) . '" class="c-searchBtn" aria-label="楽曲・アーティストを検索">'
        . '<svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>'
        . '</a></div></header>';
}

function site_footer(): string
{
    $a = 'font-size:0.72rem;color:#555;text-decoration:none';
    return '<footer style="border-top:1px solid #2a2a2a;padding:20px;text-align:center;display:flex;align-items:center;justify-content:center;gap:20px;flex-wrap:wrap">'
        . '<span style="font-size:0.72rem;color:#444">© 2026 Release Tune</span>'
        . '<a href="' . h(u('/terms')) . '" style="' . $a . '">利用規約</a>'
        . '<a href="' . h(u('/privacy')) . '" style="' . $a . '">プライバシーポリシー</a>'
        . '<a href="https://x.com/releasetune" target="_blank" rel="noopener noreferrer" style="' . $a . '">X @releasetune</a>'
        . '</footer>';
}

// ── ページ全体 ────────────────────────────────────────────

// $meta: title（ページ名。null ならサイト名だけ）, description, その他は <meta> にそのまま出す [[属性名, 名前, 値], ...]。
// Next.js 版の metadata の出力と同じ項目・順番にする（pages.php の各ページが組み立てる）
function render_page(array $meta, string $body, int $status = 200): void
{
    http_response_code($status);
    header('Content-Type: text/html; charset=utf-8');
    // 初期ドメイン（試験公開）や手元では検索エンジンに載せない
    if (!in_array($_SERVER['HTTP_HOST'] ?? '', ['releasetune.com', 'www.releasetune.com'], true)) {
        header('X-Robots-Tag: noindex');
    }
    $css = u('/assets/site.css') . '?v=' . filemtime(__DIR__ . '/../public/assets/site.css');
    $js = u('/assets/site.js') . '?v=' . filemtime(__DIR__ . '/../public/assets/site.js');
    $tags = '';
    foreach ($meta['tags'] as [$attr, $name, $value]) {
        $tags .= $attr === 'link'
            ? '<link rel="' . h($name) . '" href="' . h($value) . '">'
            : '<meta ' . $attr . '="' . h($name) . '" content="' . h($value) . '">';
    }
    echo '<!DOCTYPE html><html lang="ja"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">',
        '<title>', h($meta['title']), '</title>', $tags,
        '<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>',
        '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Noto+Sans+JP:wght@400;500;700&amp;family=Zen+Old+Mincho:wght@700&amp;display=swap">',
        '<link rel="stylesheet" href="', h($css), '">',
        '<script async src="https://www.googletagmanager.com/gtag/js?id=', GA_ID, '"></script>',
        "<script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}gtag('js',new Date());gtag('config','", GA_ID, "');</script>",
        '<script src="', h($js), '" defer></script>',
        '</head><body>', icon_defs(), $body, site_footer(), '</body></html>';
}

// サイト名だけのページ（トップ・検索・規約など）の metadata。Next.js 版のルート layout の openGraph・twitter を引き継ぐ形
function basic_meta(string $title, string $description, bool $noindex = false): array
{
    $tags = $noindex ? [['name', 'robots', 'noindex']] : [];
    array_push($tags,
        ['name', 'description', $description],
        ['property', 'og:title', $title],
        ['property', 'og:description', $description],
        ['property', 'og:site_name', 'Release Tune'],
        ['property', 'og:locale', 'ja_JP'],
        ['property', 'og:type', 'website'],
        ['name', 'twitter:card', 'summary_large_image'],
        ['name', 'twitter:title', $title],
        ['name', 'twitter:description', $description],
    );
    return ['title' => $title, 'tags' => $tags];
}

const SITE_TITLE = 'Release Tune — 今日はあの曲のリリース日';
const SITE_DESCRIPTION = '今日この日にリリースされた楽曲を、年代を超えてご紹介します。';

function page_title(string $title): string
{
    return $title . ' — Release Tune';
}
