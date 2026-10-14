<?php
// 手元のスクリプト（scripts/notes/common.py の sb_select / sb_upsert / sb_update）が DB を読み書きする窓口。
// ヘテムルの MySQL は外部から接続できないため、この API を経由する。読み書きできるので専用のトークンで守る。
//
// 本文（JSON）:
//   {"op": "select", "table": "tracks", "params": {"select": "id,title", "mmdd": "eq.10-14", "order": "id.asc", "limit": "1000", "offset": "0"}}
//   {"op": "upsert", "table": "track_note_drafts", "rows": [...], "on_conflict": "track_id"}
//   {"op": "update", "table": "tracks", "filters": {"id": "eq.123"}, "patch": {"spotify": "https://..."}}

require_once __DIR__ . '/../../src/bootstrap.php';
require_once __DIR__ . '/../../src/api.php';
require_once __DIR__ . '/../../src/rest.php';

api_run(config('db_api_token'), function (stdClass $req) {
    $table = (string) ($req->table ?? '');
    table_def($table);
    switch ($req->op ?? '') {
        case 'select':
            return rest_select($table, rest_object_to_array($req->params ?? new stdClass(), 'params'));
        case 'upsert':
            if (!is_array($req->rows ?? null)) {
                throw new InvalidArgumentException('rows は配列で指定してください');
            }
            return ['count' => rest_upsert($table, $req->rows, (string) ($req->on_conflict ?? ''))];
        case 'update':
            return ['count' => rest_update($table, rest_object_to_array($req->filters ?? new stdClass(), 'filters'), $req->patch ?? null)];
        default:
            throw new InvalidArgumentException('op は select / upsert / update のどれかです');
    }
});
