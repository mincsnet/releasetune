<?php
// 第1段階（サイトはまだ Vercel）の間だけ、Vercel のサイト（lib/tracks.ts）がデータを読む窓口。読み取り専用。
// 第2段階で PHP 版のページが src/tracks.php を直接使うようになったら削除する。
//
// 本文（JSON）: {"fn": "by_mmdd" | "by_id" | "by_artist" | "search", "arg": "10-14", "limit": 50}

require_once __DIR__ . '/../../src/bootstrap.php';
require_once __DIR__ . '/../../src/api.php';
require_once __DIR__ . '/../../src/tracks.php';

api_run(config('read_api_token'), function (stdClass $req) {
    $arg = (string) ($req->arg ?? '');
    switch ($req->fn ?? '') {
        case 'by_mmdd':
            return tracks_by_mmdd($arg);
        case 'by_id':
            return track_by_id($arg);
        case 'by_artist':
            return tracks_by_artist($arg);
        case 'search':
            return search_tracks($arg, (int) ($req->limit ?? 50));
        default:
            throw new InvalidArgumentException('fn は by_mmdd / by_id / by_artist / search のどれかです');
    }
});
