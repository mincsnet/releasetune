<?php
// テーブルと列の一覧（API で受け付ける列の許可リストを兼ねる）と、DB ⇄ API の値の変換。
// API の返す値の形は Supabase（PostgREST）と同じにする（手元のスクリプトを書き換えずに済むように）:
//   真偽値は true/false、JSON 列はオブジェクト/配列、日時は "2026-09-30T04:15:55.885318+00:00"

const TABLES = [
    'tracks' => [
        'pk' => 'id',
        'columns' => [
            'id' => 'text', 'title' => 'text', 'artist' => 'text', 'release_date' => 'date', 'mmdd' => 'text',
            'jacket' => 'text', 'note' => 'text', 'note_verified' => 'bool',
            'spotify' => 'text', 'apple' => 'text', 'amazon' => 'text', 'youtube' => 'text',
            'youtube_id' => 'text', 'youtube_verified' => 'bool',
            'note_long' => 'text', 'note_source_title' => 'text', 'note_source_url' => 'text',
        ],
    ],
    'track_note_drafts' => [
        'pk' => 'track_id',
        'columns' => [
            'track_id' => 'text', 'status' => 'text', 'wiki_title' => 'text', 'wiki_url' => 'text',
            'wiki_revid' => 'int', 'source_text' => 'text', 'note_short' => 'text', 'note_long' => 'text',
            'facts' => 'json', 'issues' => 'json', 'batch_id' => 'text', 'review_required' => 'bool',
            'reviewer_comment' => 'text', 'updated_at' => 'timestamp',
        ],
    ],
];

function table_def(string $table): array
{
    if (!isset(TABLES[$table])) {
        throw new InvalidArgumentException("使えないテーブルです: {$table}");
    }
    return TABLES[$table];
}

function column_type(string $table, string $column): string
{
    $cols = table_def($table)['columns'];
    if (!isset($cols[$column])) {
        throw new InvalidArgumentException("使えない列です: {$table}.{$column}");
    }
    return $cols[$column];
}

// DB の1行 → API で返す形
function decode_row(string $table, array $row): array
{
    $out = [];
    foreach ($row as $col => $v) {
        $out[$col] = decode_value(column_type($table, $col), $v);
    }
    return $out;
}

function decode_value(string $type, $v)
{
    if ($v === null) {
        return null;
    }
    switch ($type) {
        case 'bool':
            return (bool) $v;
        case 'int':
            return (int) $v;
        case 'json':
            // 空のオブジェクト {} が空配列 [] に化けないよう、オブジェクトのまま扱う
            return json_decode($v, false, 512, JSON_THROW_ON_ERROR);
        case 'timestamp':
            return format_timestamp($v);
        default:
            return $v;
    }
}

// API で受け取った値 → DB に入れる値
function encode_value(string $type, $v)
{
    if ($v === null) {
        return null;
    }
    switch ($type) {
        case 'bool':
            if (is_string($v)) {
                $v = strtolower($v) === 'true';
            }
            return $v ? 1 : 0;
        case 'int':
            return (int) $v;
        case 'json':
            return json_encode($v, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_THROW_ON_ERROR);
        case 'timestamp':
            return (new DateTimeImmutable((string) $v))->setTimezone(new DateTimeZone('UTC'))->format('Y-m-d H:i:s.u');
        default:
            return is_scalar($v) ? (string) $v : json_encode($v, JSON_UNESCAPED_UNICODE);
    }
}

// MySQL の "2026-09-30 04:15:55.885310"（UTC）→ PostgreSQL と同じ "2026-09-30T04:15:55.88531+00:00"
// （秒未満の末尾の0は付けず、0なら秒未満ごと省く）
function format_timestamp(string $v): string
{
    [$date, $time] = explode(' ', $v);
    if (strpos($time, '.') !== false) {
        [$sec, $frac] = explode('.', $time);
        $frac = rtrim($frac, '0');
        $time = $frac === '' ? $sec : "{$sec}.{$frac}";
    }
    return "{$date}T{$time}+00:00";
}
