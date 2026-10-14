<?php
// 楽曲ページの SNS カード画像（1200×630）。Next.js 版の app/track/[id]/opengraph-image.tsx を PHP の GD で再現する。
// X のカードは画像とドメインしか表示しないので、画像だけで日付・曲名・年数が伝わるようにする。
// 作った画像は cache/og/ に保存し、1日たったら作り直す（「◯年前」や曲名の修正を反映するため）

require_once __DIR__ . '/http.php';
require_once __DIR__ . '/site.php';
require_once __DIR__ . '/tracks.php';

const OG_W = 1200;
const OG_H = 630;
const OG_JACKET = 502;
const OG_GOLD = [0xc8, 0xa8, 0x4b];
const OG_TAGLINE = '今日はあの曲のリリース日';
const OG_CACHE_SEC = 86400;

function og_image(string $id): void
{
    $track = track_by_id($id);
    if (!$track) {
        http_response_code(404);
        header('Content-Type: text/plain; charset=utf-8');
        echo 'Not found';
        return;
    }
    $dir = __DIR__ . '/../cache/og';
    $file = $dir . '/' . preg_replace('/[^0-9A-Za-z_-]/', '_', $id) . '.png';
    if (!is_file($file) || filemtime($file) < time() - OG_CACHE_SEC) {
        if (!is_dir($dir)) {
            mkdir($dir, 0755, true);
        }
        $png = og_render($track);
        file_put_contents($file . '.tmp', $png);
        rename($file . '.tmp', $file);
    }
    header('Content-Type: image/png');
    header('Cache-Control: public, max-age=86400, s-maxage=86400, stale-while-revalidate=86400');
    readfile($file);
}

// 曲名の長さに応じて文字サイズと最大行数を決める（全角1文字=1、半角=0.55で数える。Next.js 版と同じ）
function og_title_style(string $title): array
{
    $width = 0;
    foreach (mb_str_split($title) as $c) {
        $width += mb_ord($c) < 0x2000 ? 0.55 : 1;
    }
    if ($width <= 7) return [72, 2];
    if ($width <= 14) return [64, 2];
    if ($width <= 18) return [52, 2];
    return [44, 3];
}

function og_render(array $track): string
{
    $title = social_title($track['title']);
    $years = years_ago($track['release_date']);
    $date = format_date_ja($track['release_date']) . 'リリース';
    $badge = $years > 0 ? "{$years}年前" : '';
    [$titleSize, $titleLines] = og_title_style($title);

    $tmp = sys_get_temp_dir() . '/rt-og-' . getmypid();
    @mkdir($tmp);
    $sans = og_load_fonts('Noto Sans JP', [500, 700], $title . $track['artist'] . $date . $badge . OG_TAGLINE . '♪…', $tmp);
    $logo = og_load_fonts('Zen Old Mincho', [700], 'ReleaseTun', $tmp);

    $im = imagecreatetruecolor(OG_W, OG_H);
    imagefill($im, 0, 0, imagecolorallocate($im, 0x0f, 0x0f, 0x0f));

    // 左: ジャケット（取得できなければ ♪ の代替表示）
    $jy = (OG_H - OG_JACKET) / 2;
    $jacket = og_load_jacket($track['jacket'] ?? null);
    if ($jacket) {
        imagecopy($im, $jacket, 64, $jy, 0, 0, OG_JACKET, OG_JACKET);
    } else {
        og_placeholder($im, 64, $jy, $sans[500]);
    }
    og_round_corners($im, 64, $jy, OG_JACKET, 8);

    // 右: 上に日付・曲名・アーティスト・年数、下にロゴとキャッチコピー（上下に振り分け）
    $x0 = 64 + OG_JACKET + 60;
    $colW = OG_W - 64 - $x0;
    $logoH = og_line_height($logo[700], 36);
    $tagH = og_line_height($sans[500], 20);
    $bottomTop = $jy + OG_JACKET - ($logoH + 6 + $tagH);

    $white = imagecolorallocate($im, 0xff, 0xff, 0xff);
    $sub = imagecolorallocate($im, 0xb3, 0xb3, 0xb3);
    $gold = imagecolorallocate($im, ...OG_GOLD);
    $mute = imagecolorallocate($im, 0x6a, 0x6a, 0x6a);
    $ink = imagecolorallocate($im, 0x0f, 0x0f, 0x0f);

    // 想定より長くなってもロゴに重ならないよう、はみ出す分は描かない
    $y = $jy;
    $y = og_text_block($im, $sans[500], 30, normal_lh: true, color: $gold, x: $x0, y: $y, w: $colW, text: $date, maxLines: 1, limitY: $bottomTop);
    $y = og_text_block($im, $sans[700], $titleSize, lh: 1.25, color: $white, x: $x0, y: $y + 16, w: $colW, text: $title, maxLines: $titleLines, limitY: $bottomTop);
    $y = og_text_block($im, $sans[500], 32, lh: 1.35, color: $sub, x: $x0, y: $y + 16, w: $colW, text: $track['artist'], maxLines: 2, limitY: $bottomTop);
    if ($badge !== '') {
        $bh = og_line_height($sans[700], 30) + 8;
        $by = $y + 24;
        if ($by + $bh <= $bottomTop) {
            $bw = og_text_width($sans[700], 30, $badge) + 44;
            og_pill($im, $x0, $by, $bw, $bh, $gold);
            og_draw_line($im, $sans[700], 30, $ink, $x0 + 22, $by + 4, og_line_height($sans[700], 30), $badge);
        }
    }

    // ロゴ（文字間 3.6、Release と Tune の間 12）
    $lx = $x0;
    foreach ([['Release', $gold], ['Tune', $sub]] as $i => [$word, $color]) {
        if ($i > 0) {
            $lx += 12;
        }
        foreach (str_split($word) as $ch) {
            og_draw_line($im, $logo[700], 36, $color, $lx, $bottomTop, $logoH, $ch);
            $lx += og_advance($logo[700], 36, $ch) + 3.6;
        }
    }
    og_draw_line($im, $sans[500], 20, $mute, $x0, $bottomTop + $logoH + 6, $tagH, OG_TAGLINE);

    ob_start();
    imagepng($im);
    $png = ob_get_clean();
    array_map('unlink', glob("{$tmp}/*") ?: []);
    @rmdir($tmp);
    return $png;
}

// ── フォント ────────────────────────────────────────────

// Google Fonts から、画像に使う文字だけを含むフォントを取得する（日本語フォント全体は数MBあるため）。
// GD はファイルのパスでフォントを受け取るので一時ファイルに書く。戻り値 [太さ => ['path', 'asc', 'desc']]
function og_load_fonts(string $family, array $weights, string $text, string $tmp): array
{
    $chars = implode('', array_unique(mb_str_split($text)));
    $url = 'https://fonts.googleapis.com/css2?family=' . str_replace(' ', '+', $family) . ':wght@' . implode(';', $weights) . '&text=' . rawurlencode($chars);
    $css = http_request('GET', $url)['body'];
    preg_match_all("/font-weight: (\\d+);\\s*src: url\\((.+?)\\) format\\('(?:truetype|opentype)'\\)/", $css, $m, PREG_SET_ORDER);
    if (count($m) !== count($weights)) {
        throw new RuntimeException("フォントを取得できません: {$family}");
    }
    $fonts = [];
    foreach ($m as [, $weight, $src]) {
        $path = "{$tmp}/" . md5($family . $weight) . '.ttf';
        file_put_contents($path, http_request('GET', $src)['body']);
        $fonts[(int) $weight] = ['path' => $path] + og_font_metrics($path);
    }
    return $fonts;
}

// フォントの縦の寸法（hhea の ascender・descender を 1em あたりの比にしたもの）。行の高さ「normal」の計算に使う
function og_font_metrics(string $path): array
{
    $data = file_get_contents($path);
    $tables = [];
    $num = unpack('n', $data, 4)[1];
    for ($i = 0; $i < $num; $i++) {
        $rec = unpack('a4tag/Nsum/Noffset/Nlength', $data, 12 + 16 * $i);
        $tables[$rec['tag']] = $rec['offset'];
    }
    $upm = unpack('n', $data, $tables['head'] + 18)[1];
    $s16 = fn($off) => (($v = unpack('n', $data, $off)[1]) >= 0x8000 ? $v - 0x10000 : $v);
    return ['asc' => $s16($tables['hhea'] + 4) / $upm, 'desc' => -$s16($tables['hhea'] + 6) / $upm];
}

function og_line_height(array $font, float $px): float
{
    return ($font['asc'] + $font['desc']) * $px;
}

// GD の文字サイズはポイント（96dpi）なので、ピクセルから換算する
function og_pt(float $px): float
{
    return $px * 72 / 96;
}

function og_text_width(array $font, float $px, string $text): float
{
    $b = imagettfbbox(og_pt($px), 0, $font['path'], $text);
    return max($b[2], $b[4]) - min($b[0], $b[6]);
}

// 1文字の送り幅（字形の幅ではなく、次の文字までの幅）。基準の文字を前に置いた幅の差で測る
function og_advance(array $font, float $px, string $ch): float
{
    $b1 = imagettfbbox(og_pt($px), 0, $font['path'], 'R' . $ch . 'R');
    $b0 = imagettfbbox(og_pt($px), 0, $font['path'], 'RR');
    return ($b1[2] - $b1[0]) - ($b0[2] - $b0[0]);
}

// 1行を描く。$top は行の上端、$lineH は行の高さ（文字は行の中で上下中央、ベースラインは ascender の位置）
function og_draw_line($im, array $font, float $px, int $color, float $x, float $top, float $lineH, string $text): void
{
    $content = ($font['asc'] + $font['desc']) * $px;
    $baseline = $top + ($lineH - $content) / 2 + $font['asc'] * $px;
    imagettftext($im, og_pt($px), 0, (int) round($x), (int) round($baseline), $color, $font['path'], $text);
}

// 折り返して描き、次の要素の上端を返す。日本語は1文字ずつ、英数字は単語ごとに折り返し、
// 最大行数を超える分は最後の行を「…」で切る（Next.js 版の lineClamp と同じ）
function og_text_block($im, array $font, float $px, int $color, float $x, float $y, float $w, string $text, int $maxLines,
                       float $limitY, float $lh = 0, bool $normal_lh = false): float
{
    $lineH = $normal_lh ? og_line_height($font, $px) : $lh * $px;
    preg_match_all('/[\x{0021}-\x{024F}]+\s*|\s+|./u', $text, $m);
    $lines = [''];
    foreach ($m[0] as $tok) {
        $cur = end($lines);
        if ($cur !== '' && og_text_width($font, $px, rtrim($cur . $tok)) > $w) {
            $lines[] = ltrim($tok);
        } else {
            $lines[count($lines) - 1] .= $tok;
        }
        // 1語だけで幅を超える場合は文字単位で分ける
        while (og_text_width($font, $px, rtrim(end($lines))) > $w && mb_strlen(end($lines)) > 1) {
            $last = array_pop($lines);
            $cut = mb_strlen($last) - 1;
            while ($cut > 1 && og_text_width($font, $px, mb_substr($last, 0, $cut)) > $w) {
                $cut--;
            }
            array_push($lines, mb_substr($last, 0, $cut), mb_substr($last, $cut));
        }
    }
    if (count($lines) > $maxLines) {
        $lines = array_slice($lines, 0, $maxLines);
        $last = rtrim($lines[$maxLines - 1]);
        while ($last !== '' && og_text_width($font, $px, $last . '…') > $w) {
            $last = mb_substr($last, 0, -1);
        }
        $lines[$maxLines - 1] = rtrim($last) . '…';
    }
    foreach ($lines as $line) {
        if ($y + $lineH > $limitY) {
            break;
        }
        og_draw_line($im, $font, $px, $color, $x, $y, $lineH, rtrim($line));
        $y += $lineH;
    }
    return $y;
}

// ── 図形・画像 ──────────────────────────────────────────

function og_pill($im, float $x, float $y, float $w, float $h, int $color): void
{
    $r = $h / 2;
    imagefilledrectangle($im, (int) ($x + $r), (int) $y, (int) ($x + $w - $r), (int) ($y + $h), $color);
    imagefilledellipse($im, (int) ($x + $r), (int) ($y + $r), (int) $h, (int) $h, $color);
    imagefilledellipse($im, (int) ($x + $w - $r), (int) ($y + $r), (int) $h, (int) $h, $color);
}

// 角を丸める（角の外側を背景色で塗る）
function og_round_corners($im, int $x, int $y, int $size, int $r): void
{
    $bg = imagecolorallocate($im, 0x0f, 0x0f, 0x0f);
    for ($i = 0; $i < $r; $i++) {
        for ($j = 0; $j < $r; $j++) {
            if (($r - $i - 0.5) ** 2 + ($r - $j - 0.5) ** 2 > $r * $r) {
                foreach ([[$x + $i, $y + $j], [$x + $size - 1 - $i, $y + $j], [$x + $i, $y + $size - 1 - $j], [$x + $size - 1 - $i, $y + $size - 1 - $j]] as [$px, $py]) {
                    imagesetpixel($im, $px, $py, $bg);
                }
            }
        }
    }
}

// ジャケットを取得して 502×502 にする（正方形でなければ中央を切り抜く）。取得できなければ null
function og_load_jacket(?string $url)
{
    if (!$url) {
        return null;
    }
    $res = http_request('GET', $url);
    $src = $res['status'] === 200 ? @imagecreatefromstring($res['body']) : false;
    if (!$src) {
        return null;
    }
    $w = imagesx($src);
    $h = imagesy($src);
    $s = min($w, $h);
    $dst = imagecreatetruecolor(OG_JACKET, OG_JACKET);
    imagecopyresampled($dst, $src, 0, 0, (int) (($w - $s) / 2), (int) (($h - $s) / 2), OG_JACKET, OG_JACKET, $s, $s);
    return $dst;
}

// ジャケットがないときの代替表示（金色から濃い灰色への斜めのグラデーションに ♪）
function og_placeholder($im, int $x, int $y, array $font): void
{
    $from = [0x0f + (0xc8 - 0x0f) * 0.2, 0x0f + (0xa8 - 0x0f) * 0.2, 0x0f + (0x4b - 0x0f) * 0.2];
    $to = [0x1e, 0x1e, 0x1e];
    for ($k = 0; $k <= 2 * (OG_JACKET - 1); $k++) {
        $t = $k / (2 * (OG_JACKET - 1));
        $c = imagecolorallocate($im, ...array_map(fn($a, $b) => (int) round($a + ($b - $a) * $t), $from, $to));
        $i0 = max(0, $k - (OG_JACKET - 1));
        $i1 = min($k, OG_JACKET - 1);
        imageline($im, $x + $i0, $y + $k - $i0, $x + $i1, $y + $k - $i1, $c);
    }
    $note = imagecolorallocatealpha($im, ...[...OG_GOLD, (int) round(127 * 0.2)]);
    $w = og_text_width($font, 160, '♪');
    $lineH = og_line_height($font, 160);
    og_draw_line($im, $font, 160, $note, $x + (OG_JACKET - $w) / 2, $y + (OG_JACKET - $lineH) / 2, $lineH, '♪');
}
