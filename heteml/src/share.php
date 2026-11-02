<?php
// X に投稿する文面（cron/buffer_schedule.php の予約投稿）。
// 楽曲ページの「X でシェア」と同じ文面にするため、public/assets/site.js の artistHashtag・SHARE_TEMPLATES・xLength・buildShareText を移した。
// 片方を直したらもう片方も直すこと

require_once __DIR__ . '/releases.php';

// site.js の SHARE_TEMPLATES の楽曲の分と同じ（説明もそちら。artist はアーティストページ用なので持たない）
const SHARE_TEMPLATES = [
    'debut'       => '今日は {artist} のデビュー記念日🎂 {years}年前の「{title}」から始まりました。',
    'anniversary' => '{years}年前の今日 {date} は、{work}のリリース日🎂 {years}周年です。当時、どこで誰と聴いていましたか？',
    'today'       => '今日 {date} は {work}のリリース日。{year}年から{years}年。久しぶりに聴き直しませんか？',
    'other'       => '{fullDate}リリースの {work}。あれから{years}年、久しぶりに聴き直しませんか？',
    'thisYear'    => '{fullDate}リリースの {work}。',
];
const SHARE_ANNIVERSARIES = [5, 10, 15, 20, 25, 30, 40, 50];
const X_MAX_LENGTH = 280;
const X_URL_LENGTH = 23;

// 共演名義は1つのタグにすると別の言葉になるので作らない
function artist_hashtag(string $artist): ?string
{
    if (preg_match('/[&＆、,，×\/／]| x |feat\.|featuring/iu', $artist)) {
        return null;
    }
    $tag = preg_replace('/[^\p{L}\p{M}\p{N}_]/u', '', $artist);
    return preg_match('/\p{L}/u', $tag) ? $tag : null;
}

// X の文字数の数え方（日本語・絵文字は2、ラテン文字などは1。URL は呼び出し側で23として足す）
function x_length(string $text): int
{
    $n = 0;
    foreach (mb_str_split($text) as $ch) {
        $cp = mb_ord($ch);
        $n += $cp <= 0x10ff || ($cp >= 0x2000 && $cp <= 0x200d) || ($cp >= 0x2010 && $cp <= 0x201f) || ($cp >= 0x2032 && $cp <= 0x2037) ? 1 : 2;
    }
    return $n;
}

// URL を23字として数えた投稿の文字数（上限 X_MAX_LENGTH）
function x_post_length(string $text): int
{
    $urls = '~https?://\S+~';
    return x_length(preg_replace($urls, '', $text)) + preg_match_all($urls, $text) * X_URL_LENGTH;
}

// $today（YYYY-MM-DD）の日付でテンプレートを選んで文面を作る。X の上限を超えるときは曲名を「…」で縮める
function share_text(array $t, string $today, array $tags): string
{
    [$y, $m, $d] = array_map('intval', explode('-', $t['release_date']));
    [$ty, $tm, $td] = array_map('intval', explode('-', $today));
    $years = $ty - $y;
    $key = $years <= 0 ? 'thisYear'
        : ($tm !== $m || $td !== $d ? 'other'
        : (is_debut_track($t) ? 'debut'
        : (in_array($years, SHARE_ANNIVERSARIES, true) ? 'anniversary' : 'today')));
    $url = 'https://releasetune.com/track/' . $t['id'];
    $tagLine = implode(' ', array_map(fn($tag) => '#' . $tag, $tags));
    $title = mb_str_split(preg_replace('/ - Single$/', '', $t['title']));
    $isAlbum = release_kind($t) === 'album';
    for ($len = count($title); ; $len--) {
        $shortTitle = implode('', array_slice($title, 0, $len)) . ($len < count($title) ? '…' : '');
        $vals = [
            'date' => "{$m}月{$d}日", 'fullDate' => "{$y}年{$m}月{$d}日", 'year' => $y, 'years' => $years,
            'artist' => $t['artist'], 'title' => $shortTitle,
            'work' => $t['artist'] . ($isAlbum ? 'のアルバム' : '') . '「' . $shortTitle . '」',
        ];
        $body = preg_replace_callback('/\{(\w+)\}/', fn($mt) => (string) $vals[$mt[1]], SHARE_TEMPLATES[$key]);
        $text = $body . "\n\n" . $tagLine . "\n";
        if (x_length($text) + X_URL_LENGTH <= X_MAX_LENGTH || $len <= 1) {
            return $text . $url;
        }
    }
}

// X でシェアするときのタグ（site.js と同じく、アーティスト名と ReleaseTune）
function x_share_tags(array $t): array
{
    $tag = artist_hashtag($t['artist']);
    return $tag !== null ? [$tag, 'ReleaseTune'] : ['ReleaseTune'];
}
