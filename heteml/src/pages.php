<?php
// 各ページ（Next.js 版の app/*/page.tsx と components/*PageClient.tsx・TrackDetailClient.tsx からの移植）

require_once __DIR__ . '/site.php';
require_once __DIR__ . '/tracks.php';

function page_wrap(string $content): string
{
    return '<div style="min-height:100vh;background:var(--bg)">' . site_header() . $content . '</div>';
}

// ── 日付ページ（トップと /date/MM-DD） ───────────────────────

function is_valid_mmdd(string $mmdd): bool
{
    if (!preg_match('/^\d{2}-\d{2}$/', $mmdd)) {
        return false;
    }
    [$m, $d] = parse_mmdd($mmdd);
    return $m >= 1 && $m <= 12 && $d >= 1 && $d <= 31;
}

// 前日・翌日（うるう年の 2024 年で数える。2月29日も前後に進める）
function shift_mmdd(string $mmdd, int $delta): string
{
    return (new DateTimeImmutable('2024-' . $mmdd))->modify(($delta > 0 ? '+' : '') . $delta . ' day')->format('m-d');
}

function page_home(): void
{
    $mmdd = today_mmdd();
    // トップはデビュー記念日を出さない（Next.js 版と同じ）
    render_page(basic_meta(SITE_TITLE, SITE_DESCRIPTION), page_wrap(date_body($mmdd, tracks_by_mmdd($mmdd), $mmdd, [])));
}

function page_date(string $mmdd): void
{
    if (!is_valid_mmdd($mmdd)) {
        page_not_found();
        return;
    }
    [$month, $day] = parse_mmdd($mmdd);
    $tracks = tracks_by_mmdd($mmdd);
    $title = "{$month}月{$day}日のリリース楽曲";
    $description = $tracks
        ? "{$month}月{$day}日にリリースされた" . count($tracks) . '曲をご紹介。'
            . implode('、', array_map(fn($t) => "{$t['artist']}「{$t['title']}」", array_slice($tracks, 0, 3))) . 'など。'
        : "{$month}月{$day}日にリリースされた楽曲を年代を超えてご紹介します。";
    $url = SITE_ORIGIN . "/date/{$mmdd}";
    $meta = ['title' => page_title($title), 'tags' => [
        ['name', 'description', $description],
        ['link', 'canonical', $url],
        ['property', 'og:title', $title],
        ['property', 'og:description', $description],
        ['property', 'og:url', $url],
        ['name', 'twitter:card', 'summary_large_image'],
        ['name', 'twitter:title', $title],
        ['name', 'twitter:description', $description],
    ]];
    render_page($meta, page_wrap(date_body($mmdd, $tracks, today_mmdd(), debuts_by_mmdd($mmdd, $tracks))));
}

function date_body(string $mmdd, array $tracks, string $today, array $debuts): string
{
    [$month, $day] = parse_mmdd($mmdd);
    [$pm, $pd] = parse_mmdd(shift_mmdd($mmdd, -1));
    [$nm, $nd] = parse_mmdd(shift_mmdd($mmdd, 1));
    $featured = $tracks ? $tracks[featured_index($mmdd, count($tracks))] : null;
    $others = array_values(array_filter($tracks, fn($t) => $t['id'] !== ($featured['id'] ?? null)));

    // ナビゲーション（前日・翌日・カレンダー。カレンダーの中身は site.js が作る）
    $html = '<div class="dp-nav" data-cal-nav data-mmdd="' . h($mmdd) . '"><div class="dp-navRow">'
        . '<button class="dp-navBtn" data-href="' . h(u('/date/' . shift_mmdd($mmdd, -1))) . '"'
        . ga_attrs('navigate_date', ['date' => shift_mmdd($mmdd, -1)]) . '><span class="dp-navArrow">◀</span> ' . "{$pm}月{$pd}日" . '</button>'
        . '<button class="dp-dateToggle" data-cal-toggle><div class="dp-dateToggleEyebrow">ON THIS DAY</div>'
        . '<div class="dp-dateToggleDate">' . "{$month}月{$day}日" . '</div><div class="dp-dateToggleHint" data-cal-hint>タップで日付選択</div></button>'
        . '<button class="dp-navBtn" data-href="' . h(u('/date/' . shift_mmdd($mmdd, 1))) . '"'
        . ga_attrs('navigate_date', ['date' => shift_mmdd($mmdd, 1)]) . '>' . "{$nm}月{$nd}日" . ' <span class="dp-navArrow">▶</span></button>'
        . '</div>';
    if ($mmdd !== $today) {
        $html .= '<div class="dp-backToday" data-cal-back><button class="dp-navBtn dp-navBtnAccent" data-href="' . h(u('/')) . '">今日に戻る</button></div>';
    }
    $html .= '</div>';

    // デビュー記念日
    if ($debuts) {
        $html .= '<div class="dp-debuts">';
        foreach ($debuts as $d) {
            $html .= '<a class="dp-debutLink" href="' . h(artist_url($d['artist'])) . '"><div class="dp-debut"><span class="dp-debutIcon">🎂</span>'
                . '<div class="dp-debutText"><span class="dp-debutArtist">' . h($d['artist']) . '</span><span class="dp-debutLabel"> のデビュー記念日</span>'
                . ($d['debutTrack'] !== '' ? '<span class="dp-debutTrack">「' . h($d['debutTrack']) . '」</span>' : '')
                . '<span class="dp-debutYears">' . (current_year() - (int) substr($d['debutDate'], 0, 4)) . '周年</span></div>'
                . '<span class="dp-debutChevron">›</span></div></a>';
        }
        $html .= '</div>';
    }

    $html .= '<div class="dp-content">';
    if ($featured) {
        $f = $featured;
        $years = years_ago($f['release_date']);
        $html .= '<div class="dp-featured"><a class="dp-featuredJacket" href="' . h(u('/track/' . $f['id'])) . '"' . view_track_ga($f) . '>'
            . jacket($f['jacket'], $f['title'], 68, true) . '</a><div>'
            . '<div class="dp-featuredHead"><a class="dp-plainLink" href="' . h(u('/track/' . $f['id'])) . '"><h2 class="dp-featuredTitle">' . h($f['title']) . '</h2></a>'
            . '<div class="dp-featuredArtist">' . h($f['artist']) . '</div><div class="dp-featuredMeta"><span class="dp-featuredDate">' . format_date_ja($f['release_date']) . '</span>'
            . ($years > 0 ? '<span class="dp-yearsBadge">' . $years . '年前</span>' : '') . '</div></div>'
            . (!empty($f['note']) ? '<p class="dp-featuredNote">' . h($f['note']) . '</p>' : '')
            . svc_grid($f);
        if (!empty($f['youtube_id']) && !empty($f['youtube_verified'])) {
            $html .= '<div class="dp-mv"><div class="dp-mvLabel">MV / 公式動画</div><div class="dp-mvFrame">'
                . '<iframe src="https://www.youtube.com/embed/' . h($f['youtube_id']) . '?rel=0" title="' . h($f['title'] . ' - ' . $f['artist']) . '"'
                . ' allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen class="dp-mvIframe"></iframe></div></div>';
        }
        $html .= '<a class="dp-detailLink" href="' . h(u('/track/' . $f['id'])) . '">詳細を見る →</a></div></div>';

        if ($others) {
            $html .= '<div class="dp-others"><div class="dp-othersHeading">' . "{$month}月{$day}日にリリースされた他の楽曲" . '</div>'
                . '<div class="dp-othersCount">' . count($others) . ' TRACKS</div><div class="dp-othersList">';
            $prevYear = null;
            foreach ($others as $i => $t) {
                $year = substr($t['release_date'], 0, 4);
                $html .= '<div class="dp-othersItem">' . ($year !== $prevYear ? year_header('dp', $year) : '')
                    . '<div class="dp-card" style="animation-delay:' . ($i * 70) . 'ms">'
                    . '<a href="' . h(u('/track/' . $t['id'])) . '">' . jacket($t['jacket'], $t['title'], 68) . '</a>'
                    . '<div class="dp-cardBody"><a class="dp-plainLink" href="' . h(u('/track/' . $t['id'])) . '"' . view_track_ga($t) . '><div class="dp-cardTitle">' . h($t['title']) . '</div></a>'
                    . '<a class="dp-cardArtist" href="' . h(artist_url($t['artist'])) . '">' . h($t['artist']) . '</a>'
                    . (!empty($t['note']) ? '<div class="dp-cardNote">' . h($t['note']) . '</div>' : '')
                    . track_svc_links($t) . '</div></div></div>';
                $prevYear = $year;
            }
            $html .= '</div></div>';
        }
    } else {
        $html .= '<div class="dp-empty"><div class="dp-emptyIcon">♪</div><div class="dp-emptyTitle">この日のデータはまだありません</div>'
            . '<div class="dp-emptyHint">前日・翌日ボタンで他の日付をご覧ください</div></div>';
    }
    $html .= '<div class="dp-about"><span class="dp-aboutBrand">Release Tune</span>　その日にリリースされた楽曲を年代を超えてご紹介します。</div></div>';
    return $html;
}

// ── デビュー記念日（debut_artists.csv。Next.js 版と同じく単純にカンマで区切る） ──

function debut_db(): array
{
    static $db = null;
    if ($db !== null) {
        return $db;
    }
    $db = [];
    $lines = @file(__DIR__ . '/../data/debut_artists.csv', FILE_IGNORE_NEW_LINES) ?: [];
    $header = array_map('trim', explode(',', array_shift($lines) ?? ''));
    foreach ($lines as $line) {
        $cols = explode(',', $line);
        $row = [];
        foreach ($header as $i => $name) {
            $row[$name] = trim($cols[$i] ?? '');
        }
        if (($row['artist'] ?? '') !== '' && ($row['debut_date'] ?? '') !== '') {
            $db[$row['artist']] = ['artist' => $row['artist'], 'debutDate' => $row['debut_date'], 'debutTrack' => $row['debut_track'] ?? ''];
        }
    }
    return $db;
}

function debuts_by_mmdd(string $mmdd, array $tracks): array
{
    return array_values(array_filter(debut_db(), fn($d) => substr($d['debutDate'], 5) === $mmdd));
}

// ── 楽曲詳細 ────────────────────────────────────────────

// meta description 用に max 字以内へ縮める。途中に句点があればそこで切る
function summarize(string $text, int $max): string
{
    if (mb_strlen($text) <= $max) {
        return $text;
    }
    $cut = mb_substr($text, 0, $max);
    $end = mb_strrpos($cut, '。');
    return $end !== false && $end >= $max / 3 ? mb_substr($cut, 0, $end + 1) : mb_substr($cut, 0, $max - 1) . '…';
}

function page_track(string $id): void
{
    $t = track_by_id($id);
    if (!$t) {
        page_not_found();
        return;
    }
    $mmdd = $t['mmdd'];
    [$month, $day] = parse_mmdd($mmdd);
    $years = years_ago($t['release_date']);
    $note = $t['note_long'] ?: $t['note'];
    $description = $note ? summarize($note, 120)
        : format_date_ja($t['release_date']) . 'リリース' . ($years > 0 ? "（{$years}年前）" : '') . "。{$t['artist']}の楽曲「{$t['title']}」。";
    $socialTitle = social_title($t['title']) . ' — ' . $t['artist'];
    $url = SITE_ORIGIN . "/track/{$id}";
    $image = SITE_ORIGIN . "/track/{$id}/opengraph-image";
    $meta = ['title' => page_title($t['title'] . ' — ' . $t['artist']), 'tags' => [
        ['name', 'description', $description],
        ['link', 'canonical', $url],
        ['property', 'og:title', $socialTitle],
        ['property', 'og:description', $description],
        ['property', 'og:url', $url],
        ['property', 'og:image:alt', '楽曲のリリース情報'],
        ['property', 'og:image:type', 'image/png'],
        ['property', 'og:image', $image],
        ['property', 'og:image:width', '1200'],
        ['property', 'og:image:height', '630'],
        ['property', 'og:type', 'music.song'],
        ['name', 'twitter:card', 'summary_large_image'],
        ['name', 'twitter:title', $socialTitle],
        ['name', 'twitter:description', $description],
        ['name', 'twitter:image:alt', '楽曲のリリース情報'],
        ['name', 'twitter:image:type', 'image/png'],
        ['name', 'twitter:image', $image],
        ['name', 'twitter:image:width', '1200'],
        ['name', 'twitter:image:height', '630'],
    ]];
    $siblings = array_values(array_filter(tracks_by_mmdd($mmdd), fn($s) => $s['id'] !== $t['id']));

    // シェア文は押した時点の日付で site.js が作る（リリース日の当日は周年を先頭に出す）
    $share = ' data-share-id="' . h($t['id']) . '" data-share-title="' . h($t['title']) . '" data-share-artist="' . h($t['artist']) . '" data-share-date="' . h($t['release_date']) . '"';
    $html = '<div class="td-page"><a class="td-back" href="' . h(u("/date/{$mmdd}")) . '">← ' . "{$month}月{$day}日のリリース一覧" . '</a>'
        . '<div class="td-hero"><div class="td-jacket">' . jacket($t['jacket'], $t['title'], 68, true) . '</div><div>'
        . '<div class="td-head"><h1 class="td-title">' . h($t['title']) . '</h1>'
        . '<a class="td-artist" href="' . h(artist_url($t['artist'])) . '">' . h($t['artist']) . '</a>'
        . '<div class="td-meta"><span class="td-date">' . format_date_ja($t['release_date']) . '</span>'
        . ($years > 0 ? '<span class="td-yearsBadge">' . $years . '年前</span>' : '') . '</div></div>';
    if ($note) {
        $html .= '<div class="td-note"><p class="td-noteText">' . h($note) . '</p>'
            . (!empty($t['note_source_url']) ? '<p class="td-noteSource">出典: <a href="' . h($t['note_source_url']) . '" target="_blank" rel="noopener noreferrer">Wikipedia「' . h($t['note_source_title']) . '」</a></p>' : '')
            . '</div>';
    }
    $html .= '<div class="td-section"><div class="td-sectionLabel">試聴・再生</div>' . svc_grid($t) . '</div>';
    if (!empty($t['youtube_id']) && !empty($t['youtube_verified'])) {
        $html .= '<div class="td-section"><div class="td-mvLabel">MV / 公式動画</div><div class="td-mvFrame">'
            . '<iframe src="https://www.youtube.com/embed/' . h($t['youtube_id']) . '?rel=0" title="' . h($t['title'] . ' - ' . $t['artist']) . '"'
            . ' allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture" allowfullscreen class="td-mvIframe"></iframe></div></div>';
    }
    $html .= '<div class="td-share"' . $share . '><div class="td-sectionLabel">シェア</div><div class="td-shareBtns">'
        . '<button class="td-shareBtn" data-share="x"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M18.244 2.25h3.308l-7.227 8.26 8.502 11.24H16.17l-4.714-6.231-5.401 6.231H2.747l7.73-8.835L1.254 2.25H8.08l4.261 5.636 5.903-5.636zm-1.161 17.52h1.833L7.084 4.126H5.117z"></path></svg>X でシェア</button>'
        . '<button class="td-shareBtn" data-share="threads"><svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor"><path d="M12.186 24h-.007c-3.581-.024-6.334-1.205-8.184-3.509C2.35 18.44 1.5 15.586 1.472 12.01v-.017c.03-3.579.879-6.43 2.525-8.482C5.845 1.205 8.6.024 12.18 0h.014c2.746.02 5.043.725 6.826 2.098 1.677 1.29 2.858 3.13 3.509 5.467l-2.04.569c-.505-1.808-1.343-3.233-2.487-4.234-1.19-1.036-2.868-1.587-4.9-1.6-2.832.019-4.952.965-6.475 2.898-1.426 1.806-2.168 4.298-2.196 7.405.028 3.11.77 5.6 2.196 7.405 1.522 1.93 3.64 2.876 6.467 2.895 2.256-.028 3.9-.605 5.072-1.744 1.346-1.31 1.895-3.256 1.895-5.457 0-.144-.005-.287-.016-.43h-7.019v-2.016h9.115c.028.29.044.585.044.883 0 2.9-.74 5.406-2.41 7.03C17.42 23.278 15.127 24 12.186 24z"></path></svg>Threads でシェア</button>'
        . '</div></div></div></div>';

    if ($siblings) {
        $html .= '<div class="td-siblings"><div class="td-siblingsHeading">' . "{$month}月{$day}日にリリースされた他の楽曲" . '</div><div class="td-siblingsList">';
        $prevYear = null;
        foreach ($siblings as $i => $s) {
            $year = substr($s['release_date'], 0, 4);
            $html .= '<div class="td-siblingsItem">' . ($year !== $prevYear ? year_header('td', $year) : '')
                . '<a class="td-sibLink" href="' . h(u('/track/' . $s['id'])) . '"' . view_track_ga($s) . '><div class="td-sib" style="animation-delay:' . ($i * 60) . 'ms">'
                . jacket($s['jacket'], $s['title'], 48) . '<div class="td-sibBody"><div class="td-sibTitle">' . h($s['title']) . '</div><div class="td-sibArtist">' . h($s['artist']) . '</div></div>'
                . '<span class="td-sibChevron">›</span></div></a></div>';
            $prevYear = $year;
        }
        $html .= '</div></div>';
    }
    $html .= '</div>';
    render_page($meta, page_wrap($html));
}

// ── アーティスト ─────────────────────────────────────────

function page_artist(string $name): void
{
    $tracks = tracks_by_artist($name);
    if (!$tracks) {
        page_not_found();
        return;
    }
    $count = count($tracks);
    $jacketSrc = '';
    foreach ($tracks as $t) {
        if (!empty($t['jacket'])) {
            $jacketSrc = $t['jacket'];
            break;
        }
    }
    $title = page_title($name);
    $description = "{$name}のリリース楽曲一覧。{$count}曲を収録。";
    $tags = [['name', 'description', $description], ['property', 'og:title', $title], ['property', 'og:description', $description]];
    if ($jacketSrc) {
        $tags[] = ['property', 'og:image', $jacketSrc];
    }
    array_push($tags, ['name', 'twitter:card', 'summary_large_image'], ['name', 'twitter:title', $title], ['name', 'twitter:description', $description]);
    if ($jacketSrc) {
        $tags[] = ['name', 'twitter:image', $jacketSrc];
    }
    // デビュー日は表示名（URL の名前）で引く（Next.js 版と同じ）
    $debut = debut_db()[$name] ?? null;

    $html = '<div class="ap-page"><div class="ap-hero"><div class="ap-avatar">'
        . ($jacketSrc ? jacket($jacketSrc, $name, 120) : '<div class="ap-avatarFallback">♪</div>') . '</div><div>'
        . '<h1 class="ap-name">' . h($name) . '</h1>';
    if ($debut) {
        $html .= '<div class="ap-debut"><span class="ap-debutLabel">デビュー</span> ' . h(str_replace('-', '.', $debut['debutDate']))
            . ($debut['debutTrack'] !== '' ? '<span class="ap-debutTrack">「' . h($debut['debutTrack']) . '」</span>' : '') . '</div>';
    }
    $html .= '<div class="ap-count">' . $count . ' TRACKS</div></div></div>'
        . '<div class="ap-tracks"><div class="ap-tracksHeading">リリース楽曲一覧</div><div class="ap-list">';
    $prevYear = null;
    foreach ($tracks as $i => $t) {
        $year = substr($t['release_date'], 0, 4);
        [$m, $d] = parse_mmdd($t['mmdd']);
        $html .= '<div class="ap-listItem">' . ($year !== $prevYear ? year_header('ap', $year) : '')
            . '<div class="ap-card" style="animation-delay:' . min($i * 40, 600) . 'ms">'
            . '<a href="' . h(u('/track/' . $t['id'])) . '"' . view_track_ga($t) . '>' . jacket($t['jacket'], $t['title'], 60) . '</a>'
            . '<div class="ap-cardBody"><a class="ap-plainLink" href="' . h(u('/track/' . $t['id'])) . '"' . view_track_ga($t) . '><div class="ap-cardTitle">' . h($t['title']) . '</div></a>'
            . '<a class="ap-plainLink" href="' . h(u('/date/' . $t['mmdd'])) . '"><div class="ap-cardDate">' . format_date_ja($t['release_date'])
            . '<span class="ap-cardDateLink">' . "{$m}月{$d}日のリリース →" . '</span></div></a>'
            . track_svc_links($t) . '</div></div></div>';
        $prevYear = $year;
    }
    $html .= '</div></div></div>';
    render_page(['title' => $title, 'tags' => $tags], page_wrap($html));
}

// ── 検索 ────────────────────────────────────────────────

function page_search(string $query): void
{
    $query = trim($query);
    $results = $query !== '' ? search_tracks($query, 50) : [];
    $searchIcon = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="var(--text-mute)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" class="sp-fieldIcon"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>';
    $html = '<div class="sp-page"><form class="sp-form" action="' . h(u('/search')) . '" method="get" data-search-form><div class="sp-field">' . $searchIcon
        . '<input type="text" name="q" value="' . h($query) . '" placeholder="楽曲タイトル・アーティスト名で検索..." autofocus class="sp-input">'
        . '<button type="submit" class="sp-submit' . ($query !== '' ? ' sp-submitActive' : '') . '"' . ($query === '' ? ' disabled' : '') . '>検索</button>'
        . '</div></form>';
    if ($query !== '') {
        $html .= '<div class="sp-summary">' . ($results
            ? '「<span class="sp-queryText">' . h($query) . '</span>」の検索結果：<span class="sp-resultCount">' . count($results) . ' 件</span>'
                . (count($results) >= 50 ? '<span class="sp-limitNote">（上位50件を表示）</span>' : '')
            : '「<span class="sp-queryText">' . h($query) . '</span>」に一致する楽曲が見つかりませんでした') . '</div>';
        if ($results) {
            $html .= '<div class="sp-list">';
            foreach ($results as $i => $t) {
                $years = years_ago($t['release_date']);
                [$m, $d] = parse_mmdd($t['mmdd']);
                $html .= '<div class="sp-card" style="animation-delay:' . min($i * 30, 400) . 'ms">'
                    . '<a href="' . h(u('/track/' . $t['id'])) . '"' . view_track_ga($t) . '>' . jacket($t['jacket'], $t['title'], 60) . '</a>'
                    . '<div class="sp-cardBody"><a class="sp-plainLink" href="' . h(u('/track/' . $t['id'])) . '"' . view_track_ga($t) . '><div class="sp-cardTitle">' . h($t['title']) . '</div></a>'
                    . '<a class="sp-plainLink" href="' . h(artist_url($t['artist'])) . '"><div class="sp-cardArtist">' . h($t['artist']) . '</div></a>'
                    . '<div class="sp-cardMeta"><span class="sp-cardDate">' . format_date_ja($t['release_date']) . '</span>'
                    . ($years > 0 ? '<span class="sp-yearsBadge">' . $years . '年前</span>' : '')
                    . '<a class="sp-plainLink" href="' . h(u('/date/' . $t['mmdd'])) . '"><span class="sp-cardDateLink">' . "{$m}月{$d}日のリリース →" . '</span></a></div>'
                    . track_svc_links($t) . '</div></div>';
            }
            $html .= '</div>';
        } else {
            $html .= '<div class="sp-placeholder"><div class="sp-noneIcon">♪</div><div class="sp-noneTitle">別のキーワードで試してみてください</div>'
                . '<div class="sp-placeholderHint">例：アーティスト名、楽曲タイトルの一部</div></div>';
        }
    } else {
        $html .= '<div class="sp-placeholder"><div class="sp-introIcon">🎵</div><div class="sp-introTitle">楽曲タイトルやアーティスト名を入力してください</div>'
            . '<div class="sp-placeholderHint">32,000曲以上のデータから検索できます</div></div>';
    }
    $html .= '</div>';
    render_page(basic_meta(page_title('楽曲・アーティスト検索'), 'Release Tuneの楽曲・アーティストを検索できます。'), page_wrap($html));
}

// ── 利用規約・プライバシーポリシー ───────────────────────────

function legal_section(string $title, string $body): string
{
    return '<section style="margin-bottom:36px"><h2 style="font-family:var(--font-display);font-size:1rem;font-weight:700;color:var(--text-pri);margin-bottom:12px;padding-bottom:8px;border-bottom:1px solid var(--border)">'
        . h($title) . '</h2><div style="font-size:0.88rem;color:var(--text-sec);line-height:1.9;display:flex;flex-direction:column;gap:10px">' . $body . '</div></section>';
}

function page_legal(string $kind): void
{
    $x = '<a href="https://x.com/releasetune" target="_blank" rel="noopener noreferrer" style="color:var(--gold)">@releasetune</a>';
    if ($kind === 'terms') {
        $title = '利用規約';
        $description = 'Release Tuneの利用規約です。';
        $sections = [
            ['1. はじめに', '<p>本利用規約（以下「本規約」）は、ReleaseTune運営事務局（以下「当サービス」）が提供するウェブサービス「Release Tune」の利用条件を定めるものです。ユーザーは本サービスを利用することで、本規約に同意したものとみなします。</p>'],
            ['2. サービスの概要', '<p>本サービスは、指定した日付にリリースされた音楽作品の情報を提供するウェブサービスです。表示される楽曲情報・ジャケット画像・各音楽配信サービスへのリンクは、Apple iTunes Search API等の公開APIを通じて取得・表示しています。</p><p>本サービスは情報提供を目的としており、音楽の販売・配信は行っておりません。</p>'],
            ['3. 知的財産権', '<p>本サービスに表示される楽曲タイトル・アーティスト名・ジャケット画像等の著作権・商標権は、各権利者（レコード会社・アーティスト・Apple Inc.等）に帰属します。</p><p>ジャケット画像はApple iTunes Search APIより提供されるものであり、各Apple Musicコンテンツへのリンクと組み合わせて表示しています。</p><p>本サービスのシステム・デザイン・コードに関する権利は当サービスに帰属します。</p>'],
            ['4. 免責事項', '<p>当サービスは以下の事項について責任を負いません。</p><ul><li>表示される楽曲情報（リリース日・アーティスト名・タイトル等）の正確性・完全性</li><li>外部の音楽配信サービスの仕様変更・サービス終了によるリンク切れや機能停止</li><li>本サービスの利用によって生じた損害</li><li>本サービスの一時的な停止・終了</li></ul>'],
            ['5. 禁止事項', '<p>ユーザーは以下の行為を行ってはなりません。</p><ul><li>本サービスのデータを無断で大量収集・転載・二次利用する行為</li><li>本サービスのシステムに過度な負荷をかける行為</li><li>本サービスの運営を妨害する行為</li><li>その他、法令または公序良俗に反する行為</li></ul>'],
            ['6. 外部サービスについて', '<p>本サービスに掲載されているApple Music・Spotify・Amazon Music・YouTubeへのリンクは、各サービスの利用規約に従ってご利用ください。これらの外部サービスの利用に関して、当サービスは一切の責任を負いません。</p><p>Music data provided by Apple Music / iTunes.</p>'],
            ['7. 規約の変更', '<p>当サービスは必要に応じて本規約を変更することがあります。変更後の規約は本ページに掲載した時点から効力を生じます。重要な変更がある場合はX（@releasetune）にてお知らせします。</p>'],
            ['8. お問い合わせ', '<p>本規約に関するお問い合わせは、X（旧Twitter）アカウント ' . $x . ' のダイレクトメッセージにてお受けします。</p>'],
        ];
    } else {
        $title = 'プライバシーポリシー';
        $description = 'Release Tuneのプライバシーポリシーです。';
        $sections = [
            ['1. 基本方針', '<p>ReleaseTune運営事務局（以下「当サービス」）は、ユーザーの個人情報の保護を重要な責務と認識し、適切な取り扱いに努めます。</p>'],
            ['2. 収集する情報', '<p>当サービスでは、以下の情報を収集することがあります。</p><ul><li>アクセスログ（IPアドレス、ブラウザ情報、閲覧ページ、参照元URLなど）</li><li>Google Analyticsによるアクセス解析データ（Cookieを通じた匿名の行動情報）</li></ul><p>当サービスは、氏名・メールアドレス・電話番号などの個人を直接特定できる情報を収集しません。</p>'],
            ['3. 情報の利用目的', '<p>収集した情報は以下の目的に限り利用します。</p><ul><li>サービスの改善・機能向上</li><li>アクセス状況の把握・分析</li><li>不正アクセスの検知・防止</li></ul>'],
            ['4. Google Analytics について', '<p>当サービスはGoogleが提供するアクセス解析ツール「Google Analytics」を使用しています。Google Analyticsはトラフィックデータの収集のためにCookieを使用します。このトラフィックデータは匿名で収集されており、個人を特定するものではありません。</p><p>Cookieを無効にすることでデータ収集を拒否できます。詳細は<a href="https://policies.google.com/privacy" target="_blank" rel="noopener noreferrer" style="color:var(--gold)">Googleのプライバシーポリシー</a>をご参照ください。</p>'],
            ['5. 外部サービスへのリンクについて', '<p>当サービスにはApple Music・Spotify・Amazon Music・YouTubeなどの外部サービスへのリンクが含まれています。これらの外部サービスにおける個人情報の取り扱いについては、各サービスのプライバシーポリシーをご確認ください。</p>'],
            ['6. Cookieの使用について', '<p>当サービスはGoogle AnalyticsのためにCookieを使用しています。Cookieはブラウザの設定から無効にすることができますが、一部の機能が利用できなくなる場合があります。</p>'],
            ['7. プライバシーポリシーの変更', '<p>当サービスは必要に応じて本プライバシーポリシーを変更することがあります。変更後のポリシーは本ページに掲載した時点から効力を生じます。</p>'],
            ['8. お問い合わせ', '<p>プライバシーに関するお問い合わせは、X（旧Twitter）アカウント ' . $x . ' のダイレクトメッセージにてお受けします。</p>'],
        ];
    }
    $html = '<div style="max-width:680px;margin:0 auto;padding:40px 20px 80px">'
        . '<h1 style="font-family:var(--font-display);font-size:1.6rem;font-weight:700;color:var(--text-pri);margin-bottom:8px">' . $title . '</h1>'
        . '<p style="font-size:0.78rem;color:var(--text-mute);margin-bottom:40px">最終更新日：2026年4月</p>'
        . implode('', array_map(fn($s) => legal_section($s[0], $s[1]), $sections))
        . '<div style="margin-top:48px;padding-top:24px;border-top:1px solid var(--border)"><a href="' . h(u('/')) . '" style="font-size:0.8rem;color:var(--text-mute);text-decoration:none">← トップページに戻る</a></div></div>';
    render_page(basic_meta(page_title($title), $description), page_wrap($html));
}

// ── 404 ─────────────────────────────────────────────────

function page_not_found(): void
{
    $html = '<div style="min-height:100vh;background:var(--bg);display:flex;align-items:center;justify-content:center;flex-direction:column;gap:16px;padding:20px;text-align:center">'
        . '<div style="font-size:3rem;color:var(--text-mute)">♪</div>'
        . '<h1 style="font-family:var(--font-display);font-size:1.4rem;color:var(--text-pri)">ページが見つかりません</h1>'
        . '<p style="font-size:0.84rem;color:var(--text-sec)">URLが正しいかご確認ください</p>'
        . '<a href="' . h(u('/date/' . today_mmdd())) . '" style="margin-top:8px;padding:8px 20px;border-radius:4px;border:1px solid var(--gold);color:var(--gold);text-decoration:none;font-size:0.84rem;font-weight:600">今日のリリースを見る</a></div>';
    render_page(basic_meta(SITE_TITLE, SITE_DESCRIPTION, true), $html, 404);
}
